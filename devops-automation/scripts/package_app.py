#!/usr/bin/env python3
"""
Package App Script
Builds the package with that version: JAR for OpenShift or WAR for VM,
a zip for .NET, a wheel for Python, an npm package for Node.
"""

import os
import subprocess
import sys
import json
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


def detect_project_type():
    """Detect the type of project based on files present."""
    current_dir = Path('.')

    if (current_dir / 'pom.xml').exists():
        return 'maven'
    elif (current_dir / 'build.gradle').exists() or (current_dir / 'build.gradle.kts').exists():
        return 'gradle'
    elif (current_dir / 'package.json').exists():
        return 'node'
    elif (current_dir / 'setup.py').exists() or (current_dir / 'pyproject.toml').exists():
        return 'python'
    elif (current_dir / '*.csproj').exists() or list(current_dir.glob('*.csproj')):
        return 'dotnet'
    elif (current_dir / 'go.mod').exists():
        return 'go'
    else:
        print("⚠️  Could not detect project type")
        return 'unknown'


def package_maven(version):
    """Package Maven project as JAR/WAR."""
    print("Packaging Maven project...")
    run_command(f'mvn clean package -DskipTests -Drevision={version}')

    target_dir = Path('target')
    packages = list(target_dir.glob('*.jar')) + list(target_dir.glob('*.war'))

    if packages:
        package_path = packages[0]
        print(f"✅ Package created: {package_path}")
        return str(package_path)
    else:
        print("❌ No package found in target directory")
        sys.exit(1)


def package_gradle(version):
    """Package Gradle project as JAR/WAR."""
    print("Packaging Gradle project...")
    run_command(f'./gradlew clean build -x test -Pversion={version}')

    build_dir = Path('build/libs')
    packages = list(build_dir.glob('*.jar')) + list(build_dir.glob('*.war'))

    if packages:
        package_path = packages[0]
        print(f"✅ Package created: {package_path}")
        return str(package_path)
    else:
        print("❌ No package found in build/libs directory")
        sys.exit(1)


def package_node(version):
    """Package Node.js project as npm package."""
    print("Packaging Node.js project...")

    # Update version in package.json
    with open('package.json', 'r') as f:
        package_data = json.load(f)

    package_data['version'] = version

    with open('package.json', 'w') as f:
        json.dump(package_data, f, indent=2)

    run_command('npm install')
    run_command('npm run build')
    run_command('npm pack')

    packages = list(Path('.').glob('*.tgz'))
    if packages:
        package_path = packages[0]
        print(f"✅ Package created: {package_path}")
        return str(package_path)
    else:
        print("❌ No npm package found")
        sys.exit(1)


def package_python(version):
    """Package Python project as wheel."""
    print("Packaging Python project...")

    run_command('pip install build')
    run_command(f'python -m build')

    dist_dir = Path('dist')
    wheels = list(dist_dir.glob('*.whl'))

    if wheels:
        package_path = wheels[0]
        print(f"✅ Package created: {package_path}")
        return str(package_path)
    else:
        print("❌ No wheel package found")
        sys.exit(1)


def package_dotnet(version):
    """Package .NET project as zip."""
    print("Packaging .NET project...")

    csproj_files = list(Path('.').glob('*.csproj'))
    if not csproj_files:
        print("❌ No .csproj file found")
        sys.exit(1)

    run_command(f'dotnet publish -c Release -p:Version={version}')

    publish_dir = Path('bin/Release')
    run_command(f'zip -r app-{version}.zip {publish_dir}')

    package_path = f'app-{version}.zip'
    print(f"✅ Package created: {package_path}")
    return package_path


def package_go(version):
    """Package Go project as binary."""
    print("Packaging Go project...")

    app_name = os.environ.get('APP_NAME', 'app')
    run_command(f'go build -o {app_name} -ldflags "-X main.version={version}"')

    run_command(f'tar -czf {app_name}-{version}.tar.gz {app_name}')

    package_path = f'{app_name}-{version}.tar.gz'
    print(f"✅ Package created: {package_path}")
    return package_path


def main():
    """Main function to package the application."""
    print("Packaging application...")

    version = get_version()
    print(f"Version: {version}")

    project_type = detect_project_type()
    print(f"Project type: {project_type}")

    package_handlers = {
        'maven': package_maven,
        'gradle': package_gradle,
        'node': package_node,
        'python': package_python,
        'dotnet': package_dotnet,
        'go': package_go
    }

    if project_type in package_handlers:
        package_path = package_handlers[project_type](version)

        # Save package path for subsequent steps
        with open('package_path.txt', 'w') as f:
            f.write(package_path)

        print(f"✅ Application packaged successfully: {package_path}")
        return 0
    else:
        print(f"❌ Unsupported project type: {project_type}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
