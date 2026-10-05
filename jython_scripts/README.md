# Python CWMS installation

The old Jython installation script has been retired. Do not copy and paste
`install_python.py` from GitHub to install Python CWMS. The file remains at its
historical location so old bookmarks and written instructions do not break,
but it now only points to this guide and the latest release.

Python CWMS is now distributed as a signed, portable Windows environment:

1. Open the [latest Python CWMS release](https://github.com/USACE-WaterManagement/pythonCWMS/releases/latest).
2. Download `PythonCWMS-Installer.zip`.
3. Extract the installer ZIP to a temporary directory.
4. Double-click `Install-PythonCWMS.cmd`.
5. If an installation already exists, press Enter to replace it. The previous
   installation is retained as a timestamped backup.
6. Close open terminals and VS Code, then open a new terminal and run:

   ```bat
   pythonCWMS --version
   ```

The default installation directory is `C:\hec\python\pythonCWMS`. The
installer downloads the current portable environment, verifies its SHA-256
hash and RSA signature, extracts it, tests Python startup, and configures the
user `PYTHON_CWMS_HOME` and `PATH` environment variables.

To choose another short installation directory, open Command Prompt in the
extracted installer directory and run:

```bat
Install-PythonCWMS.cmd -InstallRoot "D:\Tools\pythonCWMS"
```

For an unattended replacement, use `Install-PythonCWMS.cmd -Force`.

The remaining Jython script in this directory is only a launcher for running
CPython scripts from RTS or HEC-DSSVue. See
[`example_python_script_launcher.py`](example_python_script_launcher.py) for
its configuration.
