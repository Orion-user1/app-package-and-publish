#!/usr/bin/env python3
"""
Package Deploy Template Script
Packages the Helm chart for OpenShift, or the install scripts for VM,
with the same version.
"""

import os
import subprocess
import sys
import yaml
from pathlib import Path


def run_command(cmd, capture_output=False):
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
        if capture_output:
            return result.stdout.strip()
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {cmd}")
        print(f"Error: {e.stderr if capture_output else ''}")
        sys.exit(1)


def get_version():
    """Read version from version.txt file."""
    version_file = os.environ.get('VERSION_FILE', 'version.txt')
    if os.path.exists(version_file):
        with open(version_file, 'r') as f:
            return f.read().strip()
    return os.environ.get('VERSION', '1.0.0-rc1')


def detect_deployment_type():
    """Detect the type of deployment based on files present."""
    current_dir = Path('.')

    if (current_dir / 'helm').exists() or (current_dir / 'charts').exists():
        return 'helm'
    elif (current_dir / 'kubernetes').exists() or (current_dir / 'k8s').exists():
        return 'kubernetes'
    elif (current_dir / 'deploy').exists() or (current_dir / 'deployment').exists():
        return 'scripts'
    elif (current_dir / 'ansible').exists():
        return 'ansible'
    else:
        print("⚠️  No deployment templates found")
        return 'none'


def package_helm_chart(version):
    """Package Helm chart with version."""
    print("Packaging Helm chart...")

    # Find Helm chart directory
    helm_dirs = []
    for possible_dir in ['helm', 'charts', 'chart']:
        if Path(possible_dir).exists():
            helm_dirs.append(Path(possible_dir))

    if not helm_dirs:
        print("❌ No Helm chart directory found")
        sys.exit(1)

    helm_dir = helm_dirs[0]

    # Find Chart.yaml
    chart_yaml_path = None
    if (helm_dir / 'Chart.yaml').exists():
        chart_yaml_path = helm_dir / 'Chart.yaml'
    else:
        # Look for subdirectories
        for subdir in helm_dir.iterdir():
            if subdir.is_dir() and (subdir / 'Chart.yaml').exists():
                chart_yaml_path = subdir / 'Chart.yaml'
                helm_dir = subdir
                break

    if not chart_yaml_path:
        print("❌ Chart.yaml not found")
        sys.exit(1)

    # Update Chart.yaml with new version
    with open(chart_yaml_path, 'r') as f:
        chart_data = yaml.safe_load(f)

    chart_data['version'] = version
    chart_data['appVersion'] = version

    with open(chart_yaml_path, 'w') as f:
        yaml.dump(chart_data, f, default_flow_style=False)

    print(f"Updated Chart.yaml with version {version}")

    # Package the Helm chart
    chart_name = chart_data.get('name', 'app')
    output_dir = Path('dist')
    output_dir.mkdir(exist_ok=True)

    run_command(f'helm package {helm_dir} -d {output_dir}')

    package_path = output_dir / f"{chart_name}-{version}.tgz"

    if package_path.exists():
        print(f"✅ Helm chart packaged: {package_path}")
        return str(package_path)
    else:
        print("❌ Helm package not created")
        sys.exit(1)


def package_kubernetes_manifests(version):
    """Package Kubernetes manifests as tarball."""
    print("Packaging Kubernetes manifests...")

    k8s_dirs = []
    for possible_dir in ['kubernetes', 'k8s']:
        if Path(possible_dir).exists():
            k8s_dirs.append(possible_dir)

    if not k8s_dirs:
        print("❌ No Kubernetes directory found")
        sys.exit(1)

    k8s_dir = k8s_dirs[0]
    app_name = os.environ.get('APP_NAME', 'app')

    output_dir = Path('dist')
    output_dir.mkdir(exist_ok=True)

    package_path = output_dir / f"{app_name}-k8s-{version}.tar.gz"

    run_command(f'tar -czf {package_path} -C {k8s_dir} .')

    print(f"✅ Kubernetes manifests packaged: {package_path}")
    return str(package_path)


def package_deployment_scripts(version):
    """Package deployment scripts as tarball."""
    print("Packaging deployment scripts...")

    deploy_dirs = []
    for possible_dir in ['deploy', 'deployment', 'install', 'scripts']:
        if Path(possible_dir).exists():
            deploy_dirs.append(possible_dir)

    if not deploy_dirs:
        print("⚠️  No deployment scripts found, creating minimal package")
        deploy_dir = Path('deploy')
        deploy_dir.mkdir(exist_ok=True)

        # Create a basic install script
        with open(deploy_dir / 'install.sh', 'w') as f:
            f.write(f"""#!/bin/bash
# Installation script for version {version}
echo "Installing application version {version}..."
# Add your installation steps here
""")
        deploy_dirs.append(deploy_dir)

    deploy_dir = deploy_dirs[0]
    app_name = os.environ.get('APP_NAME', 'app')

    output_dir = Path('dist')
    output_dir.mkdir(exist_ok=True)

    package_path = output_dir / f"{app_name}-deploy-{version}.tar.gz"

    run_command(f'tar -czf {package_path} -C {deploy_dir} .')

    print(f"✅ Deployment scripts packaged: {package_path}")
    return str(package_path)


def package_ansible(version):
    """Package Ansible playbooks as tarball."""
    print("Packaging Ansible playbooks...")

    ansible_dir = Path('ansible')
    if not ansible_dir.exists():
        print("❌ Ansible directory not found")
        sys.exit(1)

    app_name = os.environ.get('APP_NAME', 'app')

    output_dir = Path('dist')
    output_dir.mkdir(exist_ok=True)

    package_path = output_dir / f"{app_name}-ansible-{version}.tar.gz"

    run_command(f'tar -czf {package_path} -C {ansible_dir} .')

    print(f"✅ Ansible playbooks packaged: {package_path}")
    return str(package_path)


def main():
    """Main function to package deployment templates."""
    print("Packaging deployment templates...")

    version = get_version()
    print(f"Version: {version}")

    deployment_type = detect_deployment_type()
    print(f"Deployment type: {deployment_type}")

    package_handlers = {
        'helm': package_helm_chart,
        'kubernetes': package_kubernetes_manifests,
        'scripts': package_deployment_scripts,
        'ansible': package_ansible,
        'none': package_deployment_scripts  # Fallback to scripts
    }

    if deployment_type in package_handlers:
        package_path = package_handlers[deployment_type](version)

        # Save package path for subsequent steps
        with open('deploy_template_path.txt', 'w') as f:
            f.write(package_path)

        print(f"✅ Deployment template packaged successfully: {package_path}")
        return 0
    else:
        print(f"❌ Unsupported deployment type: {deployment_type}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
