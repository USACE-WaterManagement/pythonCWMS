# Python CWMS Portable Environment

A portable Windows CPython 3.13 environment with CWMS libraries and their dependencies already installed.

## Install

The first release that supports the Windows installer is **v2.0**. Release v1.11 cannot be installed this way because it has no detached signature asset; a new signed v2.0 release must be published first. Do not modify the historical v1.11 release.

1. Open the [latest release](https://github.com/USACE-WaterManagement/pythonCWMS/releases/latest).
2. Download `PythonCWMS-Installer.zip`.
3. Extract the installer ZIP.
4. Double-click `Install-PythonCWMS.cmd`.

The installer downloads the signed portable environment, verifies its SHA-256 hash and RSA signature, safely extracts it, and runs Python before changing an existing installation.

The default installation directory is:

```text
%LOCALAPPDATA%\Programs\pythonCWMS
```

To select another directory, open Command Prompt in the extracted installer directory and run:

```bat
Install-PythonCWMS.cmd -InstallRoot "D:\Tools\pythonCWMS"
```

### Upgrade and backups

The installer stops if the target directory already exists. To upgrade the same target, use `-Force`:

```bat
Install-PythonCWMS.cmd -Force
```

Before installing, `-Force` renames the exact existing target to a timestamped sibling such as `pythonCWMS.backup-20261005-143000`. If installation fails, it restores that backup. After a successful installation the backup is retained and must be removed manually when no longer needed.

### Environment variables

The installer uses .NET user-environment APIs to set:

- `PYTHON_CWMS_HOME` to `<InstallRoot>\python`
- user `PATH` entries `%PYTHON_CWMS_HOME%` and `%PYTHON_CWMS_HOME%\Scripts`

The PATH update is idempotent. Open a new Command Prompt or restart applications after installation, then run `pythonCWMS --version`.

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

The former Jython installer now only shows migration instructions and may open the releases page. It never downloads, installs, deletes, or modifies files. Saved copies of the old installer are also stopped by the retirement document at the root of `main`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for release maintenance.
