#!/usr/bin/env python3
"""
Create SBOM Script
Black Duck creates the SBOM: the list of every component in the package.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime


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


def detect_project_type():
    """Detect the type of project."""
    current_dir = Path('.')

    if (current_dir / 'pom.xml').exists():
        return 'maven'
    elif (current_dir / 'build.gradle').exists() or (current_dir / 'build.gradle.kts').exists():
        return 'gradle'
    elif (current_dir / 'package.json').exists():
        return 'node'
    elif (current_dir / 'requirements.txt').exists() or (current_dir / 'Pipfile').exists():
        return 'python'
    elif list(current_dir.glob('*.csproj')):
        return 'dotnet'
    elif (current_dir / 'go.mod').exists():
        return 'go'
    else:
        return 'unknown'


def run_black_duck_scan():
    """Run Black Duck scan if available."""
    bd_url = os.environ.get('BLACKDUCK_URL')
    bd_token = os.environ.get('BLACKDUCK_TOKEN')

    if not bd_url or not bd_token:
        print("⚠️  Black Duck credentials not configured")
        return None

    print("Running Black Duck scan...")

    # Check if Black Duck detect script is available
    detect_script = 'detect.sh' if os.name != 'nt' else 'detect.ps1'

    if not os.path.exists(detect_script):
        print("Downloading Black Duck detect script...")
        download_cmd = "curl -s -L https://detect.synopsys.com/detect.sh -o detect.sh && chmod +x detect.sh"
        run_command(download_cmd, capture_output=False)

    project_name = os.environ.get('PROJECT_NAME', 'app')
    version = get_version()

    # Run Black Duck scan
    scan_cmd = f"./detect.sh --blackduck.url={bd_url} --blackduck.api.token={bd_token} --detect.project.name={project_name} --detect.project.version.name={version} --detect.risk.report.pdf=true --detect.output.path=blackduck"

    result = run_command(scan_cmd, capture_output=False)

    # Check for SBOM output
    sbom_paths = list(Path('blackduck').glob('**/sbom*.json'))
    if sbom_paths:
        return str(sbom_paths[0])

    return None


def generate_cyclonedx_sbom():
    """Generate SBOM using CycloneDX tools."""
    project_type = detect_project_type()
    print(f"Generating CycloneDX SBOM for {project_type} project...")

    output_dir = Path('sbom')
    output_dir.mkdir(exist_ok=True)

    sbom_file = output_dir / 'sbom.json'

    try:
        if project_type == 'maven':
            # Install CycloneDX Maven plugin if needed
            run_command('mvn org.cyclonedx:cyclonedx-maven-plugin:makeAggregateBom')
            # Move the generated SBOM
            if Path('target/bom.json').exists():
                Path('target/bom.json').rename(sbom_file)
                return str(sbom_file)

        elif project_type == 'node':
            # Install CycloneDX for Node
            run_command('npm install -g @cyclonedx/cyclonedx-npm')
            run_command(f'cyclonedx-npm --output-file {sbom_file}')
            return str(sbom_file)

        elif project_type == 'python':
            # Install CycloneDX for Python
            run_command('pip install cyclonedx-bom')
            run_command(f'cyclonedx-py -o {sbom_file}')
            return str(sbom_file)

        elif project_type == 'dotnet':
            # Install CycloneDX for .NET
            run_command('dotnet tool install --global CycloneDX')
            run_command(f'dotnet CycloneDX . -o {output_dir} -j')
            return str(sbom_file)

    except Exception as e:
        print(f"⚠️  Error generating CycloneDX SBOM: {e}")

    return None


def create_basic_sbom():
    """Create a basic SBOM manually."""
    print("Creating basic SBOM...")

    project_type = detect_project_type()
    version = get_version()
    app_name = os.environ.get('APP_NAME', 'app')

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "version": 1,
        "serialNumber": f"urn:uuid:{os.urandom(16).hex()}",
        "metadata": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tools": [
                {
                    "vendor": "DevOps Automation",
                    "name": "create_sbom.py",
                    "version": "1.0.0"
                }
            ],
            "component": {
                "type": "application",
                "name": app_name,
                "version": version
            }
        },
        "components": []
    }

    # Try to extract dependencies based on project type
    if project_type == 'maven' and Path('pom.xml').exists():
        deps = run_command('mvn dependency:list -DoutputFile=deps.txt', capture_output=False)
        if Path('deps.txt').exists():
            with open('deps.txt', 'r') as f:
                for line in f:
                    if ':' in line and 'compile' in line:
                        parts = line.strip().split(':')
                        if len(parts) >= 4:
                            sbom['components'].append({
                                "type": "library",
                                "group": parts[0],
                                "name": parts[1],
                                "version": parts[3]
                            })

    elif project_type == 'node' and Path('package.json').exists():
        with open('package.json', 'r') as f:
            package_data = json.load(f)
            dependencies = package_data.get('dependencies', {})
            for name, version_spec in dependencies.items():
                sbom['components'].append({
                    "type": "library",
                    "name": name,
                    "version": version_spec.lstrip('^~>=<')
                })

    elif project_type == 'python' and Path('requirements.txt').exists():
        with open('requirements.txt', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '==' in line:
                        name, version = line.split('==')
                        sbom['components'].append({
                            "type": "library",
                            "name": name.strip(),
                            "version": version.strip()
                        })

    output_dir = Path('sbom')
    output_dir.mkdir(exist_ok=True)

    sbom_file = output_dir / 'sbom.json'

    with open(sbom_file, 'w') as f:
        json.dump(sbom, f, indent=2)

    print(f"✅ Basic SBOM created: {sbom_file}")
    print(f"   Components: {len(sbom['components'])}")

    return str(sbom_file)


def validate_sbom(sbom_path):
    """Validate the SBOM file."""
    if not os.path.exists(sbom_path):
        return False

    try:
        with open(sbom_path, 'r') as f:
            sbom_data = json.load(f)

        # Basic validation
        required_fields = ['bomFormat', 'specVersion', 'metadata']
        for field in required_fields:
            if field not in sbom_data:
                print(f"⚠️  SBOM missing required field: {field}")
                return False

        print(f"✅ SBOM validation passed")

        # Print summary
        component_count = len(sbom_data.get('components', []))
        print(f"   Format: {sbom_data.get('bomFormat')}")
        print(f"   Spec Version: {sbom_data.get('specVersion')}")
        print(f"   Components: {component_count}")

        return True

    except json.JSONDecodeError as e:
        print(f"❌ Invalid SBOM JSON: {e}")
        return False


def main():
    """Main function to create SBOM."""
    print("Creating SBOM (Software Bill of Materials)...")

    sbom_path = None

    # Try Black Duck first
    if os.environ.get('USE_BLACKDUCK', '').lower() == 'true':
        sbom_path = run_black_duck_scan()

    # Try CycloneDX tools
    if not sbom_path:
        sbom_path = generate_cyclonedx_sbom()

    # Fallback to basic SBOM
    if not sbom_path:
        print("⚠️  Advanced SBOM tools not available, creating basic SBOM...")
        sbom_path = create_basic_sbom()

    if not sbom_path:
        print("❌ Failed to create SBOM")
        return 1

    # Validate the SBOM
    if not validate_sbom(sbom_path):
        print("❌ SBOM validation failed")
        return 1

    # Save SBOM path for subsequent steps
    with open('sbom_path.txt', 'w') as f:
        f.write(sbom_path)

    print(f"\n✅ SBOM created successfully: {sbom_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
