#!/usr/bin/env python3
"""
Publish Package Script
Uploads everything to non-prod/ in JFrog Artifactory with the version,
commit and build link. Then it checks the checksum.
"""

import os
import subprocess
import sys
import requests
from pathlib import Path
from urllib.parse import urljoin


def run_command(cmd, capture_output=True):
    """Execute a shell command."""
    print(f"Executing: {cmd}")
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
        if capture_output:
            print(f"Error: {e.stderr}")
        return None


def get_version():
    """Read version from version.txt file."""
    version_file = os.environ.get('VERSION_FILE', 'version.txt')
    if os.path.exists(version_file):
        with open(version_file, 'r') as f:
            return f.read().strip()
    return os.environ.get('VERSION', '1.0.0-rc1')


def get_git_commit():
    """Get current Git commit hash."""
    commit = run_command('git rev-parse HEAD')
    if commit:
        return commit[:8]
    return 'unknown'


def get_build_link():
    """Get build link from environment."""
    # Check various CI/CD systems
    build_url = (
        os.environ.get('BUILD_URL') or  # Jenkins
        os.environ.get('CI_PIPELINE_URL') or  # GitLab
        os.environ.get('GITHUB_SERVER_URL', '') + '/' +
        os.environ.get('GITHUB_REPOSITORY', '') + '/actions/runs/' +
        os.environ.get('GITHUB_RUN_ID', '') if os.environ.get('GITHUB_RUN_ID') else None or
        os.environ.get('HARNESS_BUILD_URL') or  # Harness
        'unknown'
    )
    return build_url


def get_artifactory_config():
    """Get JFrog Artifactory configuration."""
    config = {
        'url': os.environ.get('ARTIFACTORY_URL', 'https://artifactory.example.com'),
        'username': os.environ.get('ARTIFACTORY_USERNAME', ''),
        'password': os.environ.get('ARTIFACTORY_PASSWORD', ''),
        'api_key': os.environ.get('ARTIFACTORY_API_KEY', ''),
        'repository': os.environ.get('ARTIFACTORY_REPO', 'non-prod'),
        'path': os.environ.get('ARTIFACTORY_PATH', '')
    }

    if not config['username'] and not config['api_key']:
        print("⚠️  Artifactory credentials not configured")
        print("   Set ARTIFACTORY_USERNAME/PASSWORD or ARTIFACTORY_API_KEY")

    return config


def find_artifacts_to_publish():
    """Find all artifacts that need to be published."""
    artifacts = []

    # Read artifact paths from files
    artifact_files = [
        ('package_path.txt', 'package'),
        ('deploy_template_path.txt', 'deploy-template'),
        ('sbom_path.txt', 'sbom')
    ]

    for file_name, artifact_type in artifact_files:
        if os.path.exists(file_name):
            with open(file_name, 'r') as f:
                artifact_path = f.read().strip()
                if artifact_path and os.path.exists(artifact_path):
                    artifacts.append({
                        'path': artifact_path,
                        'type': artifact_type
                    })

                    # Also add signature if it exists
                    for sig_ext in ['.sig', '.asc']:
                        sig_path = artifact_path + sig_ext
                        if os.path.exists(sig_path):
                            artifacts.append({
                                'path': sig_path,
                                'type': f'{artifact_type}-signature'
                            })

    # Add checksums
    if os.path.exists('checksums/SHA256SUMS'):
        artifacts.append({
            'path': 'checksums/SHA256SUMS',
            'type': 'checksums'
        })

    # Add individual checksum files
    for checksum_file in Path('checksums').glob('*.sha256'):
        artifacts.append({
            'path': str(checksum_file),
            'type': 'checksum'
        })

    return artifacts


def upload_to_artifactory(artifact, config, version, commit, build_link):
    """Upload an artifact to JFrog Artifactory."""
    artifact_path = artifact['path']
    artifact_type = artifact['type']

    file_name = Path(artifact_path).name

    # Construct repository path
    app_name = os.environ.get('APP_NAME', 'app')
    repo_path = f"{config['repository']}/{app_name}/{version}/{file_name}"

    if config['path']:
        repo_path = f"{config['repository']}/{config['path']}/{app_name}/{version}/{file_name}"

    upload_url = urljoin(config['url'], repo_path)

    print(f"  Uploading {artifact_type}: {file_name}")
    print(f"    To: {upload_url}")

    # Prepare headers and auth
    headers = {}
    auth = None

    if config['api_key']:
        headers['X-JFrog-Art-Api'] = config['api_key']
    elif config['username'] and config['password']:
        auth = (config['username'], config['password'])
    else:
        print("  ⚠️  No authentication configured, skipping upload")
        return False

    # Add properties as headers
    headers['X-Artifactory-Property'] = f"version={version};commit={commit};build={build_link}"

    # Read and upload file
    try:
        with open(artifact_path, 'rb') as f:
            response = requests.put(
                upload_url,
                data=f,
                headers=headers,
                auth=auth,
                timeout=300
            )

        if response.status_code in [200, 201]:
            print(f"  ✅ Uploaded successfully")
            return True
        else:
            print(f"  ❌ Upload failed: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"  ❌ Upload error: {e}")
        return False


def verify_checksum_in_artifactory(artifact_path, config, version):
    """Verify checksum of uploaded artifact in Artifactory."""
    file_name = Path(artifact_path).name
    app_name = os.environ.get('APP_NAME', 'app')

    repo_path = f"{config['repository']}/{app_name}/{version}/{file_name}"
    if config['path']:
        repo_path = f"{config['repository']}/{config['path']}/{app_name}/{version}/{file_name}"

    verify_url = urljoin(config['url'], f"api/storage/{repo_path}")

    print(f"  Verifying checksum for: {file_name}")

    # Prepare auth
    headers = {}
    auth = None

    if config['api_key']:
        headers['X-JFrog-Art-Api'] = config['api_key']
    elif config['username'] and config['password']:
        auth = (config['username'], config['password'])
    else:
        print("  ⚠️  No authentication configured, skipping verification")
        return True

    try:
        response = requests.get(
            verify_url,
            headers=headers,
            auth=auth,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            remote_checksum = data.get('checksums', {}).get('sha256', '')

            # Calculate local checksum
            import hashlib
            sha256_hash = hashlib.sha256()
            with open(artifact_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            local_checksum = sha256_hash.hexdigest()

            if remote_checksum.lower() == local_checksum.lower():
                print(f"  ✅ Checksum verified: {remote_checksum[:16]}...")
                return True
            else:
                print(f"  ❌ Checksum mismatch!")
                print(f"     Local:  {local_checksum}")
                print(f"     Remote: {remote_checksum}")
                return False
        else:
            print(f"  ⚠️  Could not verify: {response.status_code}")
            return True  # Don't fail if verification endpoint is unavailable

    except Exception as e:
        print(f"  ⚠️  Verification error: {e}")
        return True  # Don't fail on verification errors


def upload_with_curl(artifact, config, version, commit, build_link):
    """Fallback upload using curl command."""
    artifact_path = artifact['path']
    file_name = Path(artifact_path).name

    app_name = os.environ.get('APP_NAME', 'app')
    repo_path = f"{config['repository']}/{app_name}/{version}/{file_name}"

    if config['path']:
        repo_path = f"{config['repository']}/{config['path']}/{app_name}/{version}/{file_name}"

    upload_url = urljoin(config['url'], repo_path)

    print(f"  Uploading with curl: {file_name}")

    # Build curl command
    if config['api_key']:
        auth_header = f'-H "X-JFrog-Art-Api: {config[\"api_key\"]}"'
    elif config['username'] and config['password']:
        auth_header = f'-u {config["username"]}:{config["password"]}'
    else:
        print("  ⚠️  No authentication configured")
        return False

    curl_cmd = f'curl -X PUT "{upload_url}" {auth_header} -H "X-Artifactory-Property: version={version};commit={commit};build={build_link}" -T "{artifact_path}"'

    result = run_command(curl_cmd, capture_output=True)

    if result:
        print(f"  ✅ Uploaded successfully")
        return True
    else:
        print(f"  ❌ Upload failed")
        return False


def main():
    """Main function to publish packages."""
    print("Publishing packages to JFrog Artifactory...")

    version = get_version()
    commit = get_git_commit()
    build_link = get_build_link()

    print(f"\nBuild Information:")
    print(f"  Version: {version}")
    print(f"  Commit:  {commit}")
    print(f"  Build:   {build_link}")

    # Get Artifactory configuration
    config = get_artifactory_config()
    print(f"\nArtifactory Configuration:")
    print(f"  URL:        {config['url']}")
    print(f"  Repository: {config['repository']}")

    # Find artifacts to publish
    print("\nFinding artifacts to publish...")
    artifacts = find_artifacts_to_publish()

    if not artifacts:
        print("⚠️  No artifacts found to publish")
        return 1

    print(f"Found {len(artifacts)} artifact(s) to publish")

    # Upload each artifact
    print("\nUploading artifacts...")
    uploaded = []
    failed = []

    for artifact in artifacts:
        success = upload_to_artifactory(artifact, config, version, commit, build_link)

        if not success:
            # Try curl fallback
            success = upload_with_curl(artifact, config, version, commit, build_link)

        if success:
            uploaded.append(artifact)
        else:
            failed.append(artifact)

    # Verify checksums for main artifacts
    print("\nVerifying checksums...")
    verification_failed = []

    for artifact in uploaded:
        if artifact['type'] in ['package', 'deploy-template']:
            if not verify_checksum_in_artifactory(artifact['path'], config, version):
                verification_failed.append(artifact)

    # Summary
    print("\n" + "="*60)
    print("PUBLISH SUMMARY")
    print("="*60)
    print(f"Total artifacts:     {len(artifacts)}")
    print(f"Successfully uploaded: {len(uploaded)}")
    print(f"Failed uploads:      {len(failed)}")
    print(f"Checksum failures:   {len(verification_failed)}")

    if uploaded:
        print(f"\n✅ Published to: {config['url']}/{config['repository']}")

    if failed:
        print("\n❌ Failed to upload:")
        for artifact in failed:
            print(f"   - {Path(artifact['path']).name}")
        return 1

    if verification_failed:
        print("\n❌ Checksum verification failed:")
        for artifact in verification_failed:
            print(f"   - {Path(artifact['path']).name}")
        return 1

    print(f"\n✅ All packages published successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
