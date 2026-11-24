#!/usr/bin/env python3
"""
Sign Package Script
Cosign signs the package, the template and the SBOM.
"""

import os
import subprocess
import sys
from pathlib import Path


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
        sys.exit(1)


def check_cosign_installed():
    """Check if cosign is installed."""
    result = subprocess.run(
        'cosign version',
        shell=True,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"✅ Cosign is installed: {result.stdout.strip()}")
        return True
    else:
        print("⚠️  Cosign is not installed")
        return False


def install_cosign():
    """Install cosign if not present."""
    print("Installing cosign...")

    system = os.name
    if system == 'posix':
        # Linux/Mac
        install_cmd = """
        curl -O -L "https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64"
        mv cosign-linux-amd64 /usr/local/bin/cosign
        chmod +x /usr/local/bin/cosign
        """
    elif system == 'nt':
        # Windows
        print("Please install cosign manually from: https://github.com/sigstore/cosign/releases")
        return False
    else:
        print(f"Unsupported OS: {system}")
        return False

    result = subprocess.run(install_cmd, shell=True, capture_output=True)
    return result.returncode == 0


def get_signing_key():
    """Get or generate signing key for cosign."""
    key_path = os.environ.get('COSIGN_KEY', 'cosign.key')
    password = os.environ.get('COSIGN_PASSWORD', '')

    if os.path.exists(key_path):
        print(f"✅ Using existing signing key: {key_path}")
        return key_path, password

    print("⚠️  No signing key found")

    # Check if we should generate a key
    if os.environ.get('COSIGN_GENERATE_KEY', '').lower() == 'true':
        print("Generating new cosign key pair...")

        # Set password for key generation
        env = os.environ.copy()
        env['COSIGN_PASSWORD'] = password if password else 'changeme'

        result = subprocess.run(
            'cosign generate-key-pair',
            shell=True,
            capture_output=True,
            text=True,
            env=env
        )

        if result.returncode == 0 and os.path.exists('cosign.key'):
            print("✅ Key pair generated successfully")
            return 'cosign.key', env['COSIGN_PASSWORD']
        else:
            print("❌ Failed to generate key pair")
            return None, None

    return None, None


def find_artifacts_to_sign():
    """Find all artifacts that need to be signed."""
    artifacts = []

    # Read artifact paths from files
    artifact_files = [
        ('package_path.txt', 'Application package'),
        ('deploy_template_path.txt', 'Deployment template'),
        ('sbom_path.txt', 'SBOM')
    ]

    for file_name, description in artifact_files:
        if os.path.exists(file_name):
            with open(file_name, 'r') as f:
                artifact_path = f.read().strip()
                if artifact_path and os.path.exists(artifact_path):
                    artifacts.append({
                        'path': artifact_path,
                        'description': description
                    })
                    print(f"  Found {description}: {artifact_path}")

    # Also check for checksums
    if os.path.exists('checksums/SHA256SUMS'):
        artifacts.append({
            'path': 'checksums/SHA256SUMS',
            'description': 'Checksum file'
        })
        print(f"  Found Checksum file: checksums/SHA256SUMS")

    return artifacts


def sign_artifact_with_cosign(artifact_path, key_path, password):
    """Sign an artifact using cosign."""
    print(f"  Signing: {artifact_path}")

    # Set up environment with password
    env = os.environ.copy()
    if password:
        env['COSIGN_PASSWORD'] = password

    # Sign the artifact
    sign_cmd = f'cosign sign-blob --key {key_path} --output-signature {artifact_path}.sig {artifact_path}'

    result = subprocess.run(
        sign_cmd,
        shell=True,
        capture_output=True,
        text=True,
        env=env
    )

    if result.returncode == 0:
        print(f"  ✅ Signature created: {artifact_path}.sig")
        return True
    else:
        print(f"  ❌ Failed to sign: {result.stderr}")
        return False


def sign_artifact_with_gpg(artifact_path):
    """Sign an artifact using GPG as fallback."""
    print(f"  Signing with GPG: {artifact_path}")

    gpg_key = os.environ.get('GPG_KEY_ID', '')

    if not gpg_key:
        print("  ⚠️  No GPG key configured")
        return False

    sign_cmd = f'gpg --detach-sign --armor --default-key {gpg_key} --output {artifact_path}.asc {artifact_path}'

    result = subprocess.run(sign_cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  ✅ GPG signature created: {artifact_path}.asc")
        return True
    else:
        print(f"  ❌ Failed to sign with GPG: {result.stderr}")
        return False


def create_signature_manifest(signed_artifacts):
    """Create a manifest file listing all signatures."""
    output_dir = Path('signatures')
    output_dir.mkdir(exist_ok=True)

    manifest_file = output_dir / 'signatures.txt'

    with open(manifest_file, 'w') as f:
        f.write("# Signature Manifest\n")
        f.write(f"# Generated: {subprocess.run('date', shell=True, capture_output=True, text=True).stdout.strip()}\n\n")

        for artifact in signed_artifacts:
            artifact_name = Path(artifact['path']).name
            f.write(f"{artifact['description']}:\n")
            f.write(f"  File: {artifact_name}\n")

            if artifact.get('signature'):
                sig_name = Path(artifact['signature']).name
                f.write(f"  Signature: {sig_name}\n")

            f.write("\n")

    print(f"\n✅ Signature manifest created: {manifest_file}")
    return str(manifest_file)


def main():
    """Main function to sign packages."""
    print("Signing packages with Cosign...")

    # Find artifacts to sign
    print("\nFinding artifacts to sign...")
    artifacts = find_artifacts_to_sign()

    if not artifacts:
        print("⚠️  No artifacts found to sign")
        return 0

    print(f"\nFound {len(artifacts)} artifact(s) to sign")

    # Check for cosign
    has_cosign = check_cosign_installed()

    if not has_cosign:
        if os.environ.get('INSTALL_COSIGN', '').lower() == 'true':
            has_cosign = install_cosign()
        else:
            print("⚠️  Cosign not available, will try GPG fallback")

    # Get signing key
    key_path, password = None, None
    if has_cosign:
        key_path, password = get_signing_key()

    # Sign each artifact
    print("\nSigning artifacts...")
    signed_artifacts = []
    signature_method = None

    for artifact in artifacts:
        artifact_path = artifact['path']
        success = False

        if has_cosign and key_path:
            success = sign_artifact_with_cosign(artifact_path, key_path, password)
            if success:
                signature_method = 'cosign'
                artifact['signature'] = f"{artifact_path}.sig"

        if not success:
            # Try GPG fallback
            success = sign_artifact_with_gpg(artifact_path)
            if success:
                signature_method = 'gpg'
                artifact['signature'] = f"{artifact_path}.asc"

        if success:
            signed_artifacts.append(artifact)
        else:
            print(f"  ⚠️  Could not sign: {artifact_path}")

    if not signed_artifacts:
        print("\n⚠️  No artifacts were signed")
        print("   This might be acceptable in development, but production builds should be signed")
        return 0

    # Create signature manifest
    manifest_path = create_signature_manifest(signed_artifacts)

    # Save signing info for subsequent steps
    with open('signature_method.txt', 'w') as f:
        f.write(signature_method if signature_method else 'none')

    print(f"\n✅ Successfully signed {len(signed_artifacts)}/{len(artifacts)} artifact(s)")
    print(f"   Method: {signature_method if signature_method else 'none'}")
    print(f"   Manifest: {manifest_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
