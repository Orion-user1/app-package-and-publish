#!/usr/bin/env python3
"""
Semantic Version Generator
Generates version from Git tags: MAJOR.MINOR.PATCH-rcBUILD

Logic:
  - Reads latest Git tag (e.g., v1.2.4)
  - Increments based on PR_LABEL or BRANCH_NAME:
    major/release/* → 2.0.0-rc123
    minor/feature/* → 1.3.0-rc123
    patch/hotfix/*  → 1.2.5-rc123
  - Exports to: version.txt, $HARNESS_ENV, output.txt

Usage:
  export PR_LABEL=minor BUILD_NUMBER=123
  python3 set_version.py
"""

import os
import re
import subprocess
import sys


def run_command(cmd, capture_output=True):
    """Execute a shell command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture_output,
            text=True,
            check=True
        )
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {cmd}")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def get_latest_git_tag():
    """Get latest Git tag or default to 1.0.0 if none exist."""
    try:
        tag = run_command("git describe --tags --abbrev=0")
        if not tag:
            print("ℹ️  No Git tags found. Using default version 1.0.0")
            print("   💡 To create a tag: git tag v1.0.0 && git push origin v1.0.0")
            return "1.0.0"
        return tag
    except:
        print("ℹ️  No Git tags found. Using default version 1.0.0")
        print("   💡 To create a tag: git tag v1.0.0 && git push origin v1.0.0")
        return "1.0.0"


def parse_version(version_str):
    """Parse version string (v1.2.4) into (major, minor, patch)."""
    version_str = version_str.lstrip('v')
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)', version_str)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    return 1, 0, 0


def get_pr_label():
    """
    Determine version increment from PR_LABEL or BRANCH_NAME.
    Priority: PR_LABEL > BRANCH_NAME detection > default 'patch'
    Branch patterns: hotfix/* → patch, feature/* → minor, release/* → major
    """
    pr_label = os.environ.get('PR_LABEL', '')
    branch_name = os.environ.get('BRANCH_NAME', '')

    if not pr_label and branch_name:
        branch_lower = branch_name.lower()
        if 'hotfix' in branch_lower:
            pr_label = 'patch'
        elif 'feature' in branch_lower:
            pr_label = 'minor'
        elif 'release' in branch_lower:
            pr_label = 'major'

    return pr_label.lower() if pr_label else 'patch'


def increment_version(major, minor, patch, label):
    """
    Apply SemVer increment rules:
    - major → (major+1, 0, 0)  - Breaking changes
    - minor → (major, minor+1, 0)  - New features
    - patch → (major, minor, patch+1)  - Bug fixes
    """
    if label in ['major', 'breaking']:
        return major + 1, 0, 0
    elif label in ['minor', 'feature']:
        return major, minor + 1, 0
    else:
        return major, minor, patch + 1


def get_build_number():
    """Get build number from environment."""
    return os.environ.get('BUILD_NUMBER', os.environ.get('CI_BUILD_NUMBER', '1'))


def main():
    """Generate semantic version and export to files/environment."""
    print("Setting version...")

    latest_tag = get_latest_git_tag()
    print(f"Latest Git tag: {latest_tag}")

    major, minor, patch = parse_version(latest_tag)
    pr_label = get_pr_label()
    print(f"PR label/type: {pr_label}")

    new_major, new_minor, new_patch = increment_version(major, minor, patch, pr_label)

    build_number = get_build_number()
    version = f"{new_major}.{new_minor}.{new_patch}-rc{build_number}"

    print(f"New version: {version}")

    # Export version to file for subsequent steps
    version_file = os.environ.get('VERSION_FILE', 'version.txt')
    with open(version_file, 'w') as f:
        f.write(version)

    # Export to environment for Harness
    print(f"Exported VERSION={version}")
    if os.environ.get('HARNESS_ACCOUNT_ID'):
        run_command(f'echo "VERSION={version}" >> $HARNESS_ENV', capture_output=False)

    # Also set as output variable
    with open(os.environ.get('GITHUB_OUTPUT', 'output.txt'), 'a') as f:
        f.write(f"version={version}\n")

    print(f"✅ Version set successfully: {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
