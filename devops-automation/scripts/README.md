# CI/CD Package and Publish Scripts

This directory contains Python scripts for the **App Package and Publish** CI/CD pipeline workflow.

## Scripts Overview

| # | Script | Description | Key Features |
|---|--------|-------------|--------------|
| 1 | [set_version.py](set_version.py) | Sets the build version | Reads Git tags, PR labels, generates semantic version (e.g., 1.1.20-rc1) |
| 2 | [package_app.py](package_app.py) | Builds the application package | Supports Java (JAR/WAR), Node (npm), Python (wheel), .NET (zip), Go |
| 3 | [package_deploy_template.py](package_deploy_template.py) | Packages deployment templates | Supports Helm charts, Kubernetes manifests, install scripts |
| 4 | [checksum.py](checksum.py) | Creates SHA-256 checksums | Generates checksums for all packages and verifies them |
| 5 | [create_sbom.py](create_sbom.py) | Generates Software Bill of Materials | Black Duck or CycloneDX SBOM listing all components |
| 6 | [sign_package.py](sign_package.py) | Signs packages cryptographically | Cosign or GPG signing of packages, templates, and SBOM |
| 7 | [publish_package.py](publish_package.py) | Publishes to JFrog Artifactory | Uploads with version, commit, build link metadata and verifies checksums |

## Prerequisites

### Python
- Python 3.7+
- Required packages: `requests`, `pyyaml`

```bash
pip install requests pyyaml
```

### Tools (Optional, based on project type)
- **Maven/Gradle**: For Java projects
- **Node.js/npm**: For Node.js projects
- **Python build tools**: For Python projects (`pip install build`)
- **Helm**: For Kubernetes deployments
- **Cosign**: For package signing
- **Black Duck**: For SBOM generation (enterprise)

## Environment Variables

### Required for All Pipelines

| Variable | Description | Example |
|----------|-------------|---------|
| `VERSION_FILE` | Path to version file | `version.txt` (default) |
| `APP_NAME` | Application name | `my-app` |
| `PROJECT_NAME` | Project name for scanning | `my-project` |

### Version Management (set_version.py)

| Variable | Description | Example |
|----------|-------------|---------|
| `PR_LABEL` | PR label (major/minor/patch) | `minor` |
| `BRANCH_NAME` | Branch name (fallback) | `feature/new-feature` |
| `BUILD_NUMBER` | CI build number | `123` |
| `HARNESS_ACCOUNT_ID` | Harness account (if using Harness) | `abc123` |

### Artifactory (publish_package.py)

| Variable | Description | Required |
|----------|-------------|----------|
| `ARTIFACTORY_URL` | JFrog Artifactory URL | ✅ Yes |
| `ARTIFACTORY_USERNAME` | Username for auth | One of these |
| `ARTIFACTORY_PASSWORD` | Password for auth | One of these |
| `ARTIFACTORY_API_KEY` | API key for auth | One of these |
| `ARTIFACTORY_REPO` | Repository name | No (default: `non-prod`) |
| `ARTIFACTORY_PATH` | Custom path in repo | No |

### Package Signing (sign_package.py)

| Variable | Description | Required |
|----------|-------------|----------|
| `COSIGN_KEY` | Path to Cosign private key | No |
| `COSIGN_PASSWORD` | Password for Cosign key | No |
| `COSIGN_GENERATE_KEY` | Generate key if missing | No (default: `false`) |
| `GPG_KEY_ID` | GPG key ID (fallback) | No |
| `INSTALL_COSIGN` | Install Cosign if missing | No (default: `false`) |

### SBOM Generation (create_sbom.py)

| Variable | Description | Required |
|----------|-------------|----------|
| `USE_BLACKDUCK` | Use Black Duck for SBOM | No (default: `false`) |
| `BLACKDUCK_URL` | Black Duck server URL | If using Black Duck |
| `BLACKDUCK_TOKEN` | Black Duck API token | If using Black Duck |

## Usage

### Running Individual Scripts

Each script can be run standalone:

```bash
# 1. Set version
python3 devops-automation/scripts/set_version.py

# 2. Package application
python3 devops-automation/scripts/package_app.py

# 3. Package deployment template
python3 devops-automation/scripts/package_deploy_template.py

# 4. Create checksums
python3 devops-automation/scripts/checksum.py

# 5. Generate SBOM
python3 devops-automation/scripts/create_sbom.py

# 6. Sign packages
python3 devops-automation/scripts/sign_package.py

# 7. Publish to Artifactory
python3 devops-automation/scripts/publish_package.py
```

### Running Full Pipeline

```bash
# Run all steps sequentially
for script in set_version package_app package_deploy_template checksum create_sbom sign_package publish_package; do
    python3 devops-automation/scripts/${script}.py || exit 1
done
```

## Output Files

The scripts create intermediate files to pass data between steps:

| File | Created By | Used By | Description |
|------|------------|---------|-------------|
| `version.txt` | set_version.py | All scripts | Version number |
| `package_path.txt` | package_app.py | checksum, sign, publish | Path to app package |
| `deploy_template_path.txt` | package_deploy_template.py | checksum, sign, publish | Path to deployment template |
| `sbom_path.txt` | create_sbom.py | sign, publish | Path to SBOM file |
| `checksum_file.txt` | checksum.py | publish | Path to checksum manifest |
| `signature_method.txt` | sign_package.py | publish | Signing method used |

## Supported Project Types

### Application Packaging

| Language/Framework | Package Format | Detection Method |
|--------------------|----------------|------------------|
| Java (Maven) | JAR/WAR | `pom.xml` present |
| Java (Gradle) | JAR/WAR | `build.gradle` or `build.gradle.kts` |
| Node.js | `.tgz` (npm) | `package.json` present |
| Python | `.whl` (wheel) | `setup.py` or `pyproject.toml` |
| .NET | `.zip` | `*.csproj` files |
| Go | `.tar.gz` | `go.mod` present |

### Deployment Templates

| Type | Package Format | Detection Method |
|------|----------------|------------------|
| Helm Chart | `.tgz` | `helm/` or `charts/` directory with `Chart.yaml` |
| Kubernetes | `.tar.gz` | `kubernetes/` or `k8s/` directory |
| Scripts | `.tar.gz` | `deploy/` or `deployment/` directory |
| Ansible | `.tar.gz` | `ansible/` directory |

## Error Handling

All scripts:
- Return exit code `0` on success
- Return exit code `1` on failure
- Print clear error messages with `❌` prefix
- Print warnings with `⚠️` prefix
- Print success messages with `✅` prefix

## Security Considerations

1. **Credentials**: Never commit credentials. Use environment variables or CI/CD secrets
2. **Signing Keys**: Store private keys securely (e.g., CI/CD secret manager)
3. **Checksums**: Always verify checksums after upload
4. **SBOM**: Generate SBOM for vulnerability tracking
5. **Signing**: Sign all production packages

## CI/CD Integration

### Harness

```yaml
- step:
    type: Run
    name: Set Version
    identifier: set_version
    spec:
      shell: Bash
      command: |
        python3 devops-automation/scripts/set_version.py
```

### GitHub Actions

```yaml
- name: Set Version
  run: python3 devops-automation/scripts/set_version.py
  env:
    PR_LABEL: ${{ github.event.pull_request.labels[0].name }}
```

### GitLab CI

```yaml
set_version:
  script:
    - python3 devops-automation/scripts/set_version.py
```

## Troubleshooting

### Version Not Set
```bash
# Check git tags
git tag -l

# Manually set version
export VERSION="1.0.0-rc1"
```

### Package Not Found
```bash
# Check build output
ls -la target/ build/libs/ dist/

# Verify project type detection
python3 -c "from pathlib import Path; print([f.name for f in Path('.').glob('*')])"
```

### Artifactory Upload Failed
```bash
# Test connectivity
curl -I $ARTIFACTORY_URL

# Verify credentials
curl -u $ARTIFACTORY_USERNAME:$ARTIFACTORY_PASSWORD $ARTIFACTORY_URL/api/system/ping
```

### Signing Failed
```bash
# Check Cosign
cosign version

# Generate test key
cosign generate-key-pair
```

## Contributing

When modifying scripts:
1. Maintain Python 3.7+ compatibility
2. Add clear logging with emoji prefixes
3. Handle errors gracefully
4. Update this README
5. Test with multiple project types

## License

Internal use only. Part of AEP DevOps automation toolkit.
