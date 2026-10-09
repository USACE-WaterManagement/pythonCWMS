# Maintaining Python CWMS releases

GitHub Actions builds the complete portable environment. User machines only download, verify, extract, smoke test, and configure that finished environment.

## Dependency changes

Edit [requirements/base_requirements.txt](requirements/base_requirements.txt) or [requirements/supplemental_requirements.txt](requirements/supplemental_requirements.txt), then regenerate the Windows CPython 3.13 lock from **both** inputs with the pinned tool and binary-only resolution:

```powershell
python -m pip install uv==0.12.22
python -m uv pip compile `
  --python-platform windows `
  --python-version 3.13 `
  --upgrade `
  --generate-hashes `
  --only-binary :all: `
  --output-file requirements/locked.txt `
  requirements/base_requirements.txt `
  requirements/supplemental_requirements.txt
```

Commit [requirements/locked.txt](requirements/locked.txt). The release workflow resolves both inputs under the committed pins and fails if the package or hash body differs, installs with `--require-hashes --only-binary=:all:`, and verifies every directly requested version after installation.

## Release signing

The repository secret `RELEASE_SIGNING_PRIVATE_KEY` must contain the PKCS#8 RSA private key matching `$ReleasePublicKeyPem` in [Install-PythonCWMS.ps1](installer/Install-PythonCWMS.ps1). The private key must never be committed.

To rotate the key:

```text
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out private.pem
openssl rsa -in private.pem -pubout -out public.pem
```

Update the repository secret and embedded public key together. The workflow signs the completed ZIP and verifies that the secret matches the installer's embedded key before publishing.

## WinPython updates

When changing `WINPYTHON_DOWNLOAD_URL` in [.github/workflows/release.yml](.github/workflows/release.yml), also update `WINPYTHON_FILENAME`, `WINPYTHON_VERSION`, and the independently verified `WINPYTHON_SHA256` value.

The workflow relocates the finished environment before testing imports and `pythonCWMS --version`, scans portable configuration files for GitHub-runner paths, creates a standard ZIP, and publishes:

- `pythonCWMS<VERSION>.zip`
- `pythonCWMS<VERSION>.zip.sig`
- a generated release-only `pythonCWMS_config.json`
- `PythonCWMS-Installer.zip`

It does not overwrite the root [pythonCWMS_config.json](pythonCWMS_config.json), which must remain the legacy Jython retirement document.

## First installer release

This migration is breaking, so the next release is v2.0, not v1.12. Merge these changes to `main`, confirm the Windows installer checks pass, confirm the signing secret is configured, then create the release with:

```bash
git tag -a v2.0 -m "Python CWMS 2.0"
git push origin v2.0
```

The workflow generates `pythonCWMS2.0.zip` and v2.0 configuration metadata. Its release notes include migration instructions. Never modify the historical v1.11 release.
