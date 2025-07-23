# Python CWMS Portable Environment

A portable, Windows, Python environment bundled with CWMS libraries and dependencies.

## What's Included

- **WinPython 3.12.10.1**: Portable Python distribution
- **Pre-installed Libraries**: All dependencies from `requirements_binary_only.txt`
- **Custom Configuration**: CWMS-specific setup and utilities
- **Jython installer script**: An installer that will download this python from the CWMS CAVI and setup user environment variables.

## Quick Start

### Download and Installation
Open the CAVI and script editor.

![alt text](image.png)

Make a new script in the CAVI called `install_python`.

![alt text](image-2.png)
![alt text](image-3.png)

Go to the [install_python.py] (./install_python.py) script and copy the raw script.
![alt text](image-1.png)

Paste the script into the script window.
![alt text](image-4.png)

Click `Save/Run` to launch the installer.

![alt text](image-5.png)

Click `Install Portable Python` to install.

### Usage
- Run `WinPython Command Prompt.exe` for command line access
- Run `WinPython Interpreter.exe` for Python IDLE
- Or use `pythonCWMS.bat` for the custom CWMS environment

## Python Build Development

### Building Locally
1. Clone this repository
2. Create/modify `requirements_binary_only.txt` with your dependencies
3. Push a tag to trigger the build: `git tag v0.8 && git push origin v0.8`

### Manual Build
You can also trigger a build manually from the Actions tab.

## Requirements File

The `requirements_binary_only.txt` file contains all Python packages to be installed. Only binary wheels are used to ensure compatibility and faster installation.

