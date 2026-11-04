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

## RTS CPython launcher

[`example_python_script_launcher.py`](example_python_script_launcher.py) is a
Jython 2.7 launcher for running external CPython scripts from RTS. It provides:

- A menu of configured scripts with editable command-line arguments.
- Live, combined standard output and error output in a Swing window.
- Optional CDA endpoint, office, and OAuth credentials from the active RTS
  connection.
- An optional snapshot of the active watershed, forecast, run, and forecast
  time window.

The launcher uses RTS-specific classes and is not compatible with HEC-DSSVue.
It runs one child process at a time. Closing the output window does not stop a
running child process.

### Prerequisites

1. Install Python CWMS using the instructions above.
2. Restart RTS after installation so it sees the new `PYTHON_CWMS_HOME` user
   environment variable.
3. Confirm that `%PYTHON_CWMS_HOME%\python.exe` exists.
4. Log in to a CDA connection in RTS before running an entry configured with
   `CDA_AUTH`.

### Configure scripts

Edit the `SCRIPTS` list near the top of the launcher. Each entry requires
`name`, `path`, and `args`. The `cda` and `rts_context` options default to
`CDA_NONE` and `False`.

```python
SCRIPTS = [
    {
        "name": "Local DSS Utility",
        "path": r"C:\code\tools\local_dss_utility.py",
        "args": r'--file "C:\data\forecast.dss"',
        "cda": CDA_NONE,
        "rts_context": True,
    },
    {
        "name": "Authenticated CDA Job",
        "path": r"C:\code\jobs\store_data.py",
        "args": "--dry-run",
        "cda": CDA_AUTH,
        "rts_context": False,
    },
]
```

Use an empty string for `args` when a script takes no arguments. The launcher
splits the argument text using Windows-style quoting and passes an argument
list directly to CPython without invoking a shell. The launch dialog lets the
operator edit arguments for that run without changing the configured default.

Each child starts with its script directory as the working directory and uses
`%PYTHON_CWMS_HOME%\python.exe -u`. Standard error is merged into standard
output and streamed to the output window.

### CDA access

Choose the least-privileged CDA mode needed by each script:

| Mode | Child environment | RTS requirement |
| --- | --- | --- |
| `CDA_NONE` | No CDA variables supplied by the launcher | None |
| `CDA_ENDPOINT` | `CDA_API_ROOT` and `OFFICE` | Active RTS CDA connection |
| `CDA_AUTH` | Endpoint and office plus `CDA_ACCESS_TOKEN`, `CDA_REFRESH_TOKEN`, `CDA_TOKEN_URL`, and `CDA_CLIENT_ID` | Authenticated OpenID RTS CDA connection |

For `CDA_AUTH`, the launcher refreshes the cached RTS OAuth token immediately
before starting CPython. The CPython script is responsible for reading the
environment and initializing its CDA client. For example:

```python
import os

import cwms

cwms.init_session(
    api_root=os.environ["CDA_API_ROOT"],
    token=os.environ.get("CDA_ACCESS_TOKEN"),
)

office_id = os.environ["OFFICE"]
```

Before constructing a child environment, the launcher removes all CDA and RTS
variables that it manages. It then adds only the capabilities requested by the selected entry, preventing a `CDA_NONE` or `CDA_ENDPOINT` script from
accidentally inheriting credentials from RTS.

`CDA_AUTH` gives the selected script and any processes it starts access to the current user's OAuth credentials. Configure only trusted scripts, and do not print tokens or a complete copy of the child environment. The launcher reports token lifetimes but does not display token values.

### RTS context

Set `rts_context` to `True` to provide `RTS_CONTEXT_JSON`, a versioned JSON
snapshot with this shape:

```json
{
  "version": 1,
  "watershed": {
    "name": "Example Watershed",
    "directory": "C:\\watersheds\\example",
    "time_zone": "America/Chicago"
  },
  "current_module": "Forecast",
  "active_forecast": {
    "name": "Example Forecast",
    "directory": "C:\\watersheds\\example\\forecast\\example",
    "dss_file": "C:\\watersheds\\example\\forecast\\example\\forecast.dss"
  },
  "active_run": {
    "name": "Run 1",
    "key": "..."
  },
  "time_window": {
    "startTime": "2026-11-01T00:00:00-05:00",
    "extractStartTime": "2026-11-01T06:00:00-06:00",
    "forecastTime": "2026-11-02T06:00:00-06:00",
    "endTime": "2026-11-05T06:00:00-06:00"
  }
}
```

Unavailable values remain `null`. Forecast, run, and time-window values are
only populated when the current RTS module is a forecast tab.

The same available values are also exported individually:

| Context | Environment variables |
| --- | --- |
| Watershed | `RTS_WATERSHED_NAME`, `RTS_WATERSHED_DIRECTORY`, `RTS_WATERSHED_TIME_ZONE` |
| Module | `RTS_CURRENT_MODULE` |
| Forecast | `RTS_ACTIVE_FORECAST`, `RTS_ACTIVE_FORECAST_DIRECTORY`, `RTS_ACTIVE_FORECAST_DSS` |
| Run | `RTS_ACTIVE_RUN`, `RTS_ACTIVE_RUN_KEY` |
| Time window | `RTS_START_TIME`, `RTS_EXTRACT_START_TIME`, `RTS_FORECAST_TIME`, `RTS_END_TIME` |

Times are ISO-8601 values with a UTC offset in the watershed time zone. A
CPython script can load the full snapshot with:

```python
import json
import os

context = json.loads(os.environ["RTS_CONTEXT_JSON"])
```

### Troubleshooting

- `PYTHON_CWMS_HOME environment variable is not set`: restart RTS after
  installing Python CWMS, or verify the user environment variable.
- `Python executable not found`: verify that `PYTHON_CWMS_HOME` points to the
  directory containing `python.exe`, normally
  `C:\hec\python\pythonCWMS\python`.
- `This script requires an active RTS CDA connection`: select a CDA connection
  in RTS or change the entry to `CDA_NONE`.
- Token or authentication errors: log out of CDA in RTS, log back in, and
  launch the script again.
- `Python script not found`: correct the absolute `path` in the selected
  `SCRIPTS` entry.

The authenticated mode reads RTS's cached token provider through Java
reflection to avoid opening another interactive login. That implementation
detail may need updating when moving the launcher to a different RTS release.
