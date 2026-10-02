# Python CWMS Portable Environment

A portable, Windows, Python environment bundled with CWMS libraries and dependencies.

## To Update Python Build

### Build Locally
1. Clone this repository
2. Optionally, modify WinPython variables (`WINPYTHON_VERSION`, `WINPYTHON_FILENAME`, and `WINPYTHON_DOWNLOAD_URL`) in the [release.yml](.github\workflows\release.yml) if upgrading python.
   - **When you change `WINPYTHON_DOWNLOAD_URL`, also update `WINPYTHON_SHA256`** to the known-good hash of the new file. The build fails if the download does not match. Confirm the value against the upstream WinPython release page.
3. Modify `supplemental_requirements.txt` with your dependencies
4. Push a tag to trigger the build: `git tag v0.8` and `git push origin v0.8`

The release workflow commits the updated `pythonCWMS_config.json` to `main` after each
build, and the installer's default `Config URL` tracks that file, so installers pick up
the latest release automatically.

## Security Setup (maintainers)

### Release signing (authenticity)
The SHA-256 check only proves a download was not corrupted; it does **not** prove the
file is genuine, because the config supplies both the URL and the expected hash. To
add real authenticity, the workflow signs each archive with an RSA private key and the
installer verifies it against an embedded public key.

One-time setup:
1. Generate a keypair:
   ```
   openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out private.pem
   openssl rsa -in private.pem -pubout -out public.pem
   ```
2. Add the contents of `private.pem` as the repo secret `RELEASE_SIGNING_PRIVATE_KEY`
   (keep the private key out of the repo).
3. Paste the contents of `public.pem` into `RELEASE_PUBLIC_KEY_PEM` in
   [`jython_scripts/install_python.py`](jython_scripts/install_python.py).

Until the secret is set, releases ship unsigned and the installer warns that
authenticity is not verified. Once the public key is embedded, the installer **refuses**
any download that lacks a valid signature.

### Hash-pinned dependencies (supply chain)
The workflow installs with `--only-binary=:all:` (no source builds = no arbitrary code
during `pip install`). To additionally pin exact wheel hashes, generate a lock file on a
Windows host (so wheel hashes match the build) and commit it:
```
pip install pip-tools
pip-compile --generate-hashes --output-file requirements/locked.txt ^
  requirements/base_requirements.txt requirements/supplemental_requirements.txt
```
When `requirements/locked.txt` exists, the build installs from it with
`--require-hashes`; otherwise it falls back to the version-pinned (but un-hashed)
requirements and logs a warning.

### Manual Build
You can also trigger a build manually from the Actions tab.

## Requirements File

The `base_requirements.txt` file contains Python packages to be  installed with compatable versions in CWMS batch. The `supplemental_requirements.txt` file contains additional packages that may be useful.
