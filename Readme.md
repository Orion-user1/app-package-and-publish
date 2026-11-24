# 📦 App Package and Publish Pipeline

CI/CD pipeline template for packaging and publishing applications to JFrog Artifactory.

## Overview

This reusable pipeline packages applications, creates SBOMs, signs artifacts, and publishes them to Artifactory with full traceability.

## Pipeline Steps

| # | Step | Description |
|---|------|-------------|
| 1 | **Set Version** | Generates semantic version from Git tags and PR labels (e.g., 1.1.20-rc1) |
| 2 | **Package App** | Builds application package: JAR/WAR (Java), npm (Node), wheel (Python), zip (.NET) |
| 3 | **Package Deploy Template** | Packages Helm charts (OpenShift) or install scripts (VM) with the same version |
| 4 | **Checksum** | Creates SHA-256 checksums for all packages and verifies integrity |
| 5 | **Create SBOM** | Generates Software Bill of Materials listing every component using Black Duck or CycloneDX |
| 6 | **Sign Package** | Cryptographically signs the package, template, and SBOM using Cosign or GPG |
| 7 | **Publish Package** | Uploads everything to non-prod/ in JFrog Artifactory with version, commit, and build link metadata |

## File Structure

```
cicd-app-package-and-publish/
├── pipelines/
│   └── cicd-app-package-and-publish.yaml    # Harness pipeline definition
├── devops-automation/
│   └── scripts/
│       ├── set_version.py                    # Version management
│       ├── package_app.py                    # Application packaging
│       ├── package_deploy_template.py        # Deployment template packaging
│       ├── checksum.py                       # SHA-256 checksum generation
│       ├── create_sbom.py                    # SBOM generation
│       ├── sign_package.py                   # Package signing
│       ├── publish_package.py                # Artifactory publishing
│       └── README.md                         # Detailed script documentation
└── docs/
    └── README.md                             # This file
```

## Prerequisites

### Required Tools
- Python 3.7+
- Git
- Project-specific build tools (Maven, Gradle, npm, etc.)

### Optional Tools
- Helm (for Kubernetes deployments)
- Cosign (for package signing)
- Black Duck (for enterprise SBOM generation)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ARTIFACTORY_URL` | ✅ | JFrog Artifactory server URL |
| `ARTIFACTORY_USERNAME` / `ARTIFACTORY_API_KEY` | ✅ | Authentication credentials |
| `APP_NAME` | ✅ | Application name |
| `PR_LABEL` | ⚠️ | Version increment type (major/minor/patch) |
| `BUILD_NUMBER` | ⚠️ | CI build number |

See [scripts/README.md](../devops-automation/scripts/README.md) for complete environment variable documentation.

## Supported Project Types

### Applications
- ☕ **Java**: Maven (JAR/WAR), Gradle (JAR/WAR)
- 📦 **Node.js**: npm packages (.tgz)
- 🐍 **Python**: wheels (.whl)
- 🔷 **.NET**: zip archives
- 🐹 **Go**: compressed binaries (.tar.gz)

### Deployment Templates
- ⎈ **Helm Charts**: Kubernetes/OpenShift deployments
- 📋 **Kubernetes Manifests**: Raw YAML files
- 📜 **Install Scripts**: Shell/PowerShell scripts
- 🔧 **Ansible Playbooks**: Configuration management

## Usage

### Using in Harness

Import the pipeline template:

```yaml
template:
  name: App Package and Publish
  identifier: cicd_app_package_and_publish
  versionLabel: "1.0"
  type: Stage
  projectIdentifier: YOUR_PROJECT
  orgIdentifier: YOUR_ORG
  spec:
    # ... (use the pipeline YAML)
```

### Local Testing

```bash
# Set environment variables
export APP_NAME="my-app"
export VERSION_FILE="version.txt"
export ARTIFACTORY_URL="https://artifactory.example.com"
export ARTIFACTORY_USERNAME="your-username"
export ARTIFACTORY_PASSWORD="your-password"

# Run pipeline steps
cd your-project/
python3 devops-automation/scripts/set_version.py
python3 devops-automation/scripts/package_app.py
python3 devops-automation/scripts/package_deploy_template.py
python3 devops-automation/scripts/checksum.py
python3 devops-automation/scripts/create_sbom.py
python3 devops-automation/scripts/sign_package.py
python3 devops-automation/scripts/publish_package.py
```

## Output Artifacts

After successful execution, the following artifacts are published to Artifactory:

```
non-prod/{APP_NAME}/{VERSION}/
├── {app-package}              # Main application (JAR, npm, wheel, etc.)
├── {app-package}.sig          # Package signature
├── {deploy-template}.tgz      # Deployment template (Helm chart or scripts)
├── {deploy-template}.tgz.sig  # Template signature
├── sbom.json                  # Software Bill of Materials
├── sbom.json.sig              # SBOM signature
└── SHA256SUMS                 # Checksum manifest
```

Each artifact includes metadata:
- **version**: Semantic version (e.g., 1.1.20-rc1)
- **commit**: Git commit hash
- **build**: CI/CD build URL

## Security Features

✅ **Checksum Verification**: SHA-256 checksums prevent tampering  
✅ **Cryptographic Signing**: Cosign/GPG signatures ensure authenticity  
✅ **SBOM Generation**: Track all dependencies for vulnerability management  
✅ **Audit Trail**: Version, commit, and build link for traceability  
✅ **Non-Prod Isolation**: Packages published to non-prod/ by default  

## Troubleshooting

See [scripts/README.md](../devops-automation/scripts/README.md) for detailed troubleshooting guide.

Common issues:
- **Version not incrementing**: Check Git tags and PR labels
- **Package not found**: Verify project structure matches supported types
- **Upload fails**: Check Artifactory credentials and connectivity
- **Signing fails**: Verify Cosign installation and key configuration

## Customization

### Adding Custom Steps

Edit [cicd-app-package-and-publish.yaml](../pipelines/cicd-app-package-and-publish.yaml) to add steps:

```yaml
- step:
    type: Run
    name: Save JAR for Downstream
    spec:
      command: |
        echo "Custom logic here"
```

### Supporting New Project Types

Edit `package_app.py` to add detection and packaging logic:

```python
def package_new_type(version):
    """Package new project type."""
    # Your packaging logic here
    pass
```

## Best Practices

1. ✅ Always use semantic versioning
2. ✅ Tag releases in Git for version tracking
3. ✅ Sign all production packages
4. ✅ Generate SBOMs for compliance
5. ✅ Verify checksums after upload
6. ✅ Use API keys instead of passwords
7. ✅ Keep secrets in CI/CD vault

## References

- [Harness CI/CD Documentation](https://developer.harness.io/)
- [JFrog Artifactory API](https://www.jfrog.com/confluence/display/JFROG/Artifactory+REST+API)
- [Sigstore Cosign](https://docs.sigstore.dev/cosign/overview/)
- [CycloneDX SBOM](https://cyclonedx.org/)
- [Semantic Versioning](https://semver.org/)

## Support

For issues or questions:
- Check [scripts/README.md](../devops-automation/scripts/README.md) for detailed documentation
- Review script logs for error messages
- Contact DevOps team for pipeline configuration assistance

