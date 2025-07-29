# Python CWMS Portable Environment

A portable, Windows, Python environment bundled with CWMS libraries and dependencies.

## To Update Python Build

### Build Locally
1. Clone this repository
2. Optionally, modify WinPython variables (`WINPYTHON_VERSION`, `WINPYTHON_FILENAME`, and `WINPYTHON_DOWNLOAD_URL`) in the [release.yml](.github\workflows\release.yml) if upgrading python.
3. Modify `requirements_binary_only.txt` with your dependencies
4. Push a tag to trigger the build: `git tag v0.8` and `git push origin v0.8`

### Manual Build
You can also trigger a build manually from the Actions tab.

## Requirements File

The `requirements_binary_only.txt` file contains all Python packages to be installed. Only binary wheels are used to ensure compatibility and faster installation.

