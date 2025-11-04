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

![alt text](./screenshots/image.png)

Make a new script in the CAVI called `install_python`.

![alt text](./screenshots/image-2.png)
![alt text](./screenshots/image-3.png)

Go to the [install_python.py](./jython_scripts/install_python.py) script in the `jython_scripts` folder and copy the raw script.
![alt text](./screenshots/image-1.png)

Paste the script into the script window.
![alt text](./screenshots/image-4.png)

Click `Save/Run` to launch the installer.

![alt text](./screenshots/image-5.png)

Click `Install Portable Python` to install. Please be patient, it may take up to 10 minutes to install.

#### Failed to download configuration error

Note: if you get a "Failed to download configuration" error with the jython installer, try replacing the `Config URL:` path with a link to the ` pythonCWMS_config.json` file in the latest release (e.g. [./releases/tag/v0.81/pythonCWMS_config.json](https://github.com/USACE-WaterManagement/pythonCWMS/releases/tag/v0.81)) and reload the configuration. This error can occur if the rawgithub content is blocked.

You can also just download the latest release file (e.g. `pythonCWMS0.81.7z` (https://github.com/USACE-WaterManagement/pythonCWMS/releases/)) and unzip the portable python distribution and setup your user environment variables yourself to add the python to your path.

### General Usage
- Use `pythonCWMS` in the command line to run python.
- Setup the default python in VsCode by pointing the []`python.defaultInterpreterPath`] (https://code.visualstudio.com/docs/python/settings-reference) to the installation directory (e.g. `C:\hec\python\pythonCWMS0.8.0\python`). 
- Run `WinPython Command Prompt.exe` for command line access
- Run `WinPython Interpreter.exe` for Python IDLE
- Or use `pythonCWMS.bat` for the custom CWMS environment

#### VS Code Use
To have VS Code default to this portable python, open `Preferences: Open User Settings (JSON)` by pressing `Cntr+Shift+P` and searching for Preferences in the search bar at the top of VS Code.
![alt text](./screenshots/vsCodeUserSettings.png)

In your `settings.json` file, put this line in `"python.defaultInterpreterPath": "${env:PYTHON_CWMS_HOME}\\python.exe"`.
  
#### Install additional libraries
- To install additional libraries beyond what is in the [requirements_binary_only.txt](./requirements_binary_only.txt) file, open the WinPython powershell included in your python (e.g. `C:\hec\python\pythonCWMS0.8.0\WinPython Powershell Prompt.exe`) and do a pip install from there.

### CAVI Python Script Usage
 To use the python environment in the CAVI, a jython launcher script is used to run the python script as a subprocess. The jython script can also pass arguments to the python script.

- To run a python script in the CAVI, edit the `python_script_path` and `args` variables in the [`example_python_script_launcher.py`](./jython_scripts/example_python_script_launcher.py) jython script to point to your python script and save in the CAVI script editor. You can pass arguments from your jython environment (e.g. watershed path etc...), but this is optional. Leave `args` as `None` or `''` if arguments are not needed.
- Output of the python script will be passed to the CAVI console after the process is completed. 

## To help maintain the python builds

See [`CONTRIBUTING.md`](CONTRIBUTING.md)
