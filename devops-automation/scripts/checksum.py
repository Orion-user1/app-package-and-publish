#!/usr/bin/env python3
"""
Checksum Script
Creates a SHA-256 checksum of the package.
"""

import hashlib
import os
import sys
from pathlib import Path


def calculate_sha256(file_path):
    """Calculate SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Error calculating checksum for {file_path}: {e}")
        sys.exit(1)


def find_packages():
    """Find all packages that need checksums."""
    packages = []

    # Read package paths from files
    if os.path.exists('package_path.txt'):
        with open('package_path.txt', 'r') as f:
            package_path = f.read().strip()
            if package_path and os.path.exists(package_path):
                packages.append(package_path)

    if os.path.exists('deploy_template_path.txt'):
        with open('deploy_template_path.txt', 'r') as f:
            deploy_path = f.read().strip()
            if deploy_path and os.path.exists(deploy_path):
                packages.append(deploy_path)

    # Also check common directories
    common_patterns = [
        'target/*.jar',
        'target/*.war',
        'build/libs/*.jar',
        'dist/*.whl',
        'dist/*.tgz',
        'dist/*.tar.gz',
        '*.zip',
        '*.tgz'
    ]

    for pattern in common_patterns:
        for file_path in Path('.').glob(pattern):
            if file_path.is_file() and str(file_path) not in packages:
                packages.append(str(file_path))

    return packages


def create_checksums(packages):
    """Create SHA-256 checksums for all packages."""
    checksums = []

    if not packages:
        print("⚠️  No packages found to create checksums")
        return checksums

    output_dir = Path('checksums')
    output_dir.mkdir(exist_ok=True)

    print(f"Creating checksums for {len(packages)} package(s)...")

    for package in packages:
        print(f"  Calculating checksum for: {package}")
        checksum = calculate_sha256(package)

        package_name = Path(package).name
        checksum_file = output_dir / f"{package_name}.sha256"

        # Write checksum file in standard format
        with open(checksum_file, 'w') as f:
            f.write(f"{checksum}  {package_name}\n")

        print(f"  ✅ {package_name}: {checksum}")

        checksums.append({
            'file': package,
            'checksum': checksum,
            'checksum_file': str(checksum_file)
        })

    return checksums


def create_combined_checksum_file(checksums):
    """Create a combined checksum file with all checksums."""
    if not checksums:
        return None

    combined_file = Path('checksums') / 'SHA256SUMS'

    with open(combined_file, 'w') as f:
        for item in checksums:
            package_name = Path(item['file']).name
            f.write(f"{item['checksum']}  {package_name}\n")

    print(f"\n✅ Combined checksum file created: {combined_file}")
    return str(combined_file)


def verify_checksums(checksums):
    """Verify that checksums were created correctly."""
    print("\nVerifying checksums...")

    all_valid = True
    for item in checksums:
        stored_checksum = item['checksum']
        calculated_checksum = calculate_sha256(item['file'])

        if stored_checksum == calculated_checksum:
            print(f"  ✅ {Path(item['file']).name}: Valid")
        else:
            print(f"  ❌ {Path(item['file']).name}: Invalid!")
            all_valid = False

    return all_valid


def main():
    """Main function to create checksums."""
    print("Creating SHA-256 checksums...")

    packages = find_packages()

    if not packages:
        print("❌ No packages found to checksum")
        return 1

    print(f"Found {len(packages)} package(s) to checksum")

    checksums = create_checksums(packages)

    if not checksums:
        print("❌ Failed to create checksums")
        return 1

    combined_file = create_combined_checksum_file(checksums)

    # Verify the checksums
    if not verify_checksums(checksums):
        print("❌ Checksum verification failed")
        return 1

    # Save checksum info for subsequent steps
    with open('checksum_file.txt', 'w') as f:
        if combined_file:
            f.write(combined_file)

    print(f"\n✅ All checksums created and verified successfully")
    print(f"   Total packages: {len(checksums)}")
    print(f"   Checksum directory: checksums/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
