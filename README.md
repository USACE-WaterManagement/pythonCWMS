# Python CWMS Portable Environment

A portable Windows CPython 3.13 environment with CWMS libraries and their dependencies already installed.

## Install

The first release that supports the Windows installer is **v2.0**. Release v1.11 cannot be installed this way because it has no detached signature asset; a new signed v2.0 release must be published first. Do not modify the historical v1.11 release.

1. Open the [latest release](https://github.com/USACE-WaterManagement/pythonCWMS/releases/latest).
2. Download `PythonCWMS-Installer.zip`.
3. Extract the installer ZIP. It creates a `PythonCWMS-Installer` folder.
4. Open that folder and double-click `Install-PythonCWMS.cmd`.

After a successful installation, the installer removes `PythonCWMS-Installer.zip` and its extracted folder when possible.

The installer downloads the signed portable environment, verifies its SHA-256 hash and RSA signature, safely extracts it, and runs Python before changing an existing installation.

The default installation directory is:

```text
C:\hec\python\pythonCWMS
```

WinPython recommends keeping its base directory path to about 37 characters or fewer. The installer warns when a custom `-InstallRoot` exceeds that recommendation.

To select another directory, open Command Prompt in the extracted installer directory and run:

```bat
Install-PythonCWMS.cmd -InstallRoot "D:\Tools\pythonCWMS"
```

### Upgrade and backups

If the target directory already exists, the installer asks whether to replace it and defaults to **Yes**. The existing installation is retained as a timestamped backup. For an unattended upgrade, use `-Force` to approve replacement without prompting:

```bat
Install-PythonCWMS.cmd -Force
```

After confirmation (or `-Force`), the installer renames the exact existing target to a timestamped sibling such as `pythonCWMS.backup-20261005-143000`. If installation fails, it restores that backup. After a successful installation the backup is retained and must be removed manually when no longer needed.

### Environment variables

The installer uses .NET user-environment APIs to set:

- `PYTHON_CWMS_HOME` to `<InstallRoot>\python`
- user `PATH` entries `%PYTHON_CWMS_HOME%` and `%PYTHON_CWMS_HOME%\Scripts`

The PATH update is idempotent and removes entries from older Python CWMS installations. Close all Command Prompt, PowerShell, Windows Terminal, and VS Code windows after installation, then open a new terminal and run `pythonCWMS --version`.

For VS Code, set:

```json
"python.defaultInterpreterPath": "${env:PYTHON_CWMS_HOME}\\python.exe"
```

If a workspace has retained another interpreter, run **Python: Clear Workspace Interpreter Setting** from the Command Palette.

## Install additional libraries

Run packages through the installed interpreter:

```bat
pythonCWMS -m pip install package-name
```

Packages included in releases are defined by [base requirements](requirements/base_requirements.txt) and [supplemental requirements](requirements/supplemental_requirements.txt), then resolved into the hash-pinned [Windows lock](requirements/locked.txt).

## RTS and HEC-DSS scripts

Jython is still used as a launcher inside RTS and HEC-DSS. Edit `python_script_path` and `args` in [example_python_script_launcher.py](jython_scripts/example_python_script_launcher.py). Set `args` to `None` or an empty string when no arguments are needed; multiple arguments are split before launching CPython.

Do not use the former Jython `install_python.py` workflow to install Python CWMS. The file remains as a compatibility notice for old bookmarks, while the signed Windows installer is documented in the [Jython migration guide](jython_scripts/README.md). Saved copies of the old installer are also stopped by the retirement document at the root of `main`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for release maintenance.
