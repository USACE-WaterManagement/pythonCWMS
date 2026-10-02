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

Before the next release, store the private key matching the public key embedded in
[`jython_scripts/install_python.py`](jython_scripts/install_python.py) as the repository
secret `RELEASE_SIGNING_PRIVATE_KEY`. The workflow fails rather than publishing an
unsigned release, and it verifies that the private key matches the embedded public key.

The current private key is generated outside the repository and must never be committed.
To rotate the keypair:
1. Generate a replacement keypair:
   ```
   openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out private.pem
   openssl rsa -in private.pem -pubout -out public.pem
   ```
2. Replace the repo secret `RELEASE_SIGNING_PRIVATE_KEY` with `private.pem`.
3. Replace `RELEASE_PUBLIC_KEY_PEM` with `public.pem` in
   [`jython_scripts/install_python.py`](jython_scripts/install_python.py).
4. Publish a signed release immediately after merging the public-key change. Installers
   refuse unsigned releases and signatures made with any other key.

### Hash-pinned dependencies (supply chain)
The workflow installs only binary wheels from the required, hash-pinned lock. Wheels
still contain executable code, so hashes and review of requirement changes both matter.
After changing either input requirements file, regenerate and commit the Windows lock:
```
python -m pip install uv==0.12.22
uv pip compile --python-platform windows --python-version 3.13 ^
  --generate-hashes --only-binary :all: --output-file requirements/locked.txt ^
  requirements/base_requirements.txt requirements/supplemental_requirements.txt
```
The build fails if `requirements/locked.txt` is missing or if a locked artifact hash
does not match.

### Manual Build
You can also trigger a build manually from the Actions tab.

## Requirements File

The `base_requirements.txt` file contains Python packages to be  installed with compatable versions in CWMS batch. The `supplemental_requirements.txt` file contains additional packages that may be useful.
