# RTS Jython 2.7 launcher for external CPython scripts.
#
# Requirements:
#   1. Set PYTHON_CWMS_HOME to the directory containing python.exe.
#   2. Scripts configured with cda=CDA_AUTH require an active RTS CDA login.

import json
import os
import shlex
import subprocess

from com.auth0.jwt import JWT
from java.awt import BorderLayout, GridLayout
from java.awt.event import ActionListener
from java.lang import NoSuchFieldException, Runnable, System, Thread
from java.time import ZonedDateTime
from java.time.format import DateTimeFormatter
from javax.swing import (
    JComboBox,
    JFrame,
    JLabel,
    JOptionPane,
    JPanel,
    JScrollPane,
    JTextArea,
    JTextField,
    SwingUtilities,
)

from hec.serversuite import ServerSuiteUtil
from hec2.rts.script import RTS
from hec2.rts.ui import ForecastTab
from mil.army.usace.hec.serversuite.cda import CdaAuthenticationSource


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PYTHON_HOME_ENV = "PYTHON_CWMS_HOME"
RUNNING_PROPERTY = "rts.cpython.launcher.running"

CDA_NONE = "none"
CDA_ENDPOINT = "endpoint"
CDA_AUTH = "auth"

# Environment variables controlled by this launcher. Clear them before
# configuring each child so scripts cannot inherit credentials accidentally.
MANAGED_ENVIRONMENT = (
    "CDA_API_ROOT",
    "CDA_API_KEY",
    "CDA_ACCESS_TOKEN",
    "CDA_REFRESH_TOKEN",
    "CDA_TOKEN_URL",
    "CDA_CLIENT_ID",
    "OFFICE",
    "RTS_CONTEXT_JSON",
    "RTS_WATERSHED_NAME",
    "RTS_WATERSHED_DIRECTORY",
    "RTS_WATERSHED_TIME_ZONE",
    "RTS_CURRENT_MODULE",
    "RTS_ACTIVE_FORECAST",
    "RTS_ACTIVE_FORECAST_DIRECTORY",
    "RTS_ACTIVE_FORECAST_DSS",
    "RTS_ACTIVE_RUN",
    "RTS_ACTIVE_RUN_KEY",
    "RTS_START_TIME",
    "RTS_EXTRACT_START_TIME",
    "RTS_FORECAST_TIME",
    "RTS_END_TIME",
)

# Per-script options:
#   cda=CDA_NONE      Do not pass CDA settings or credentials.
#   cda=CDA_ENDPOINT  Pass CDA_API_ROOT and OFFICE only.
#   cda=CDA_AUTH      Refresh, then pass RTS OAuth access/refresh credentials.
#   rts_context=True  Pass a snapshot of the current watershed/forecast/run.
SCRIPTS = [
    {
        "name": "Get MN DNR Data",
        "path": r"C:\code\mvp-wm-cwbi-jobs\python\get_mndnr.py",
        "args": "-d 1",
        "cda": CDA_AUTH,
        "rts_context": False,
    },
    {
        "name": "Get MN DNR Data - Selected Locations",
        "path": (
            r"C:\code\mvp-wm-cwbi-jobs\python\get_mndnr.py"
        ),
        "args": "-d 3 -l TMCM5 SPFM5",
        "cda": CDA_AUTH,
        "rts_context": False,
    },
    {
        "name": "Upload BLOB",
        "path": (
            r"C:\code\CWMS-data-acquisition-python"
            r"\src\upload_blob.py"
        ),
        "args": r'--file "C:\data\example.pdf"',
        "cda": CDA_AUTH,
        "rts_context": False,
    },
]

# Examples for additional entries:
#
# Local DSS script using the current watershed path, but no CDA variables:
# {
#     "name": "Local DSS Utility",
#     "path": r"C:\code\tools\local_dss_utility.py",
#     "args": "",
#     "cda": CDA_NONE,
#     "rts_context": True,
# }
#
# Public/read-only CDA script that needs only the selected endpoint and office:
# {
#     "name": "CDA Catalog",
#     "path": r"C:\code\tools\cda_catalog.py",
#     "args": "",
#     "cda": CDA_ENDPOINT,
#     "rts_context": False,
# }


# ---------------------------------------------------------------------------
# RTS authentication
# ---------------------------------------------------------------------------

def get_private_field(obj, field_name):
    """Read a private field from an object or one of its Java superclasses."""
    java_class = obj.getClass()

    while java_class is not None:
        try:
            field = java_class.getDeclaredField(field_name)
            field.setAccessible(True)
            return field.get(obj)
        except NoSuchFieldException:
            java_class = java_class.getSuperclass()

    raise RuntimeError(
        "Field %s was not found on %s"
        % (field_name, obj.getClass().getName())
    )


def get_active_cda():
    """Return the active CDA source and data-access factory."""
    source = ServerSuiteUtil.getCwmsAuthenticationSource()
    if not isinstance(source, CdaAuthenticationSource):
        raise RuntimeError(
            "This script requires an active RTS CDA connection"
        )

    factory = ServerSuiteUtil.getDataAccessFactory()
    if factory is None:
        raise RuntimeError(
            "RTS does not have an active CDA DataAccessFactory"
        )

    return source, factory


def get_token_remaining_seconds(oauth_token):
    """Return the access token's remaining lifetime."""
    access_token = oauth_token.getAccessToken()
    if access_token is None or not str(access_token).strip():
        raise RuntimeError("The cached RTS access token is empty")

    expires_at = JWT.decode(str(access_token)).getExpiresAt()
    if expires_at is None:
        raise RuntimeError("The cached RTS access token has no expiration")

    remaining_millis = expires_at.getTime() - System.currentTimeMillis()
    return max(0, int(remaining_millis / 1000))


def refresh_token_before_launch(provider, oauth_token):
    """Refresh through RTS immediately before launching CPython."""
    previous_remaining_seconds = get_token_remaining_seconds(oauth_token)
    refresh_token = oauth_token.getRefreshToken()
    if refresh_token is None or not str(refresh_token).strip():
        raise RuntimeError(
            "The cached RTS OAuth token has no refresh token"
        )

    try:
        oauth_token = provider.refreshToken()
    except Exception as error:
        raise RuntimeError(
            "RTS could not refresh the CDA token. "
            "Log out and back into CDA, then try again. %s" % error
        )

    if oauth_token is None:
        raise RuntimeError("RTS returned no token after refresh")

    return (
        oauth_token,
        get_token_remaining_seconds(oauth_token),
        previous_remaining_seconds,
    )


def add_cda_environment(child_env, cda_mode):
    """Add the requested level of CDA context to a child environment."""
    if cda_mode == CDA_NONE:
        return None

    source, factory = get_active_cda()
    child_env["CDA_API_ROOT"] = str(factory.getDataSourceUrl())
    child_env["OFFICE"] = str(factory.getOfficeId())

    if cda_mode == CDA_ENDPOINT:
        return None

    if cda_mode != CDA_AUTH:
        raise RuntimeError("Unknown CDA mode: %s" % cda_mode)

    if not ServerSuiteUtil.isConnected():
        raise RuntimeError(
            "This script requires an authenticated RTS CDA connection"
        )

    auth_optional = source.getCdaAuthExtension()
    if not auth_optional.isPresent():
        raise RuntimeError(
            "The active CDA connection has no authentication extension"
        )

    auth = auth_optional.get()
    auth_type = str(auth.getExtensionType().name())
    if auth_type not in ("OPEN_ID", "OPEN_ID_CWBI"):
        raise RuntimeError(
            "RTS authentication type %s does not use an OAuth bearer token"
            % auth_type
        )

    # Read the token created by the completed RTS login. Calling getToken()
    # here could start another interactive OpenID login.
    provider = get_private_field(auth, "_tokenProvider")
    if provider is None:
        raise RuntimeError(
            "RTS has no cached token provider. "
            "Log out and back into CDA, then try again."
        )

    oauth_token = get_private_field(provider, "token")
    if oauth_token is None:
        raise RuntimeError(
            "RTS has no cached OAuth token. "
            "Log out and back into CDA, then try again."
        )

    (
        oauth_token,
        remaining_seconds,
        previous_remaining_seconds,
    ) = refresh_token_before_launch(provider, oauth_token)
    access_token = oauth_token.getAccessToken()
    refresh_token = oauth_token.getRefreshToken()
    if access_token is None or not str(access_token).strip():
        raise RuntimeError("The cached RTS access token is empty")
    if refresh_token is None or not str(refresh_token).strip():
        raise RuntimeError(
            "The RTS OAuth response did not include a refresh token"
        )

    child_env["CDA_ACCESS_TOKEN"] = str(access_token)
    child_env["CDA_REFRESH_TOKEN"] = str(refresh_token)
    child_env["CDA_TOKEN_URL"] = str(
        provider.getTokenUrl().getApiRoot()
    )
    child_env["CDA_CLIENT_ID"] = str(
        System.getProperty(
            "hec.serversuite.cwbi.client.id.cda",
            "cwms",
        )
    )

    return {
        "lifetime_seconds": oauth_token.getExpiresIn(),
        "remaining_seconds": remaining_seconds,
        "previous_remaining_seconds": previous_remaining_seconds,
        "refreshed": True,
    }


def format_hec_time(hec_time, zone_id):
    """Format a defined HecTime as an ISO-8601 timestamp with offset."""
    if hec_time is None or not hec_time.isDefined():
        return None

    instant = hec_time.getInstant(zone_id)
    return str(
        ZonedDateTime.ofInstant(instant, zone_id).format(
            DateTimeFormatter.ISO_OFFSET_DATE_TIME
        )
    )


def add_rts_context_environment(child_env):
    """Add a versioned snapshot of the current RTS context."""
    context = {
        "version": 1,
        "watershed": None,
        "current_module": None,
        "active_forecast": None,
        "active_run": None,
        "time_window": None,
    }

    watershed = RTS.getWatershed()
    zone_id = None
    if watershed is not None:
        time_zone = watershed.getTimeZone()
        zone_id = time_zone.toZoneId()
        watershed_context = {
            "name": str(watershed.getName()),
            "directory": str(watershed.getProjectDirectory()),
            "time_zone": str(time_zone.getID()),
        }
        context["watershed"] = watershed_context
        child_env["RTS_WATERSHED_NAME"] = watershed_context["name"]
        child_env["RTS_WATERSHED_DIRECTORY"] = watershed_context["directory"]
        child_env["RTS_WATERSHED_TIME_ZONE"] = watershed_context["time_zone"]

    current_module = RTS.getCurrentModule()
    if current_module is not None:
        module_name = str(current_module.getTabTitle())
        context["current_module"] = module_name
        child_env["RTS_CURRENT_MODULE"] = module_name

    if isinstance(current_module, ForecastTab):
        forecast = current_module.getForecast()
        if forecast is not None:
            forecast_context = {
                "name": str(forecast.getName()),
                "directory": str(forecast.getForecastDirectory()),
                "dss_file": str(forecast.getForecastDSSFilename()),
            }
            context["active_forecast"] = forecast_context
            child_env["RTS_ACTIVE_FORECAST"] = forecast_context["name"]
            child_env["RTS_ACTIVE_FORECAST_DIRECTORY"] = (
                forecast_context["directory"]
            )
            child_env["RTS_ACTIVE_FORECAST_DSS"] = forecast_context["dss_file"]

            forecast_run = current_module.getActiveForecastRun()
            if forecast_run is not None:
                run_context = {
                    "name": str(forecast_run.getName()),
                    "key": str(forecast_run.getKey()),
                }
                context["active_run"] = run_context
                child_env["RTS_ACTIVE_RUN"] = run_context["name"]
                child_env["RTS_ACTIVE_RUN_KEY"] = run_context["key"]

            # RTS calls the simulation start "lookback time" internally.
            # The Forecast Time Window UI maps the four fields as follows.
            run_time_window = (
                forecast_run.getRunTimeWindow()
                if forecast_run is not None
                else forecast.getRunTimeWindow()
            )
            if run_time_window is not None and zone_id is not None:
                time_window_context = {
                    "startTime": format_hec_time(
                        run_time_window.getLookbackTime(),
                        zone_id,
                    ),
                    "extractStartTime": format_hec_time(
                        run_time_window.getExtractStartTime(),
                        zone_id,
                    ),
                    "forecastTime": format_hec_time(
                        run_time_window.getStartTime(),
                        zone_id,
                    ),
                    "endTime": format_hec_time(
                        run_time_window.getEndTime(),
                        zone_id,
                    ),
                }
                context["time_window"] = time_window_context

                time_environment = (
                    ("RTS_START_TIME", "startTime"),
                    ("RTS_EXTRACT_START_TIME", "extractStartTime"),
                    ("RTS_FORECAST_TIME", "forecastTime"),
                    ("RTS_END_TIME", "endTime"),
                )
                for environment_name, context_name in time_environment:
                    value = time_window_context[context_name]
                    if value is not None:
                        child_env[environment_name] = value

    child_env["RTS_CONTEXT_JSON"] = json.dumps(context, sort_keys=True)


def build_child_environment(script):
    """Build only the environment capabilities requested by a script."""
    child_env = os.environ.copy()
    for name in MANAGED_ENVIRONMENT:
        child_env.pop(name, None)

    cda_mode = script.get("cda", CDA_NONE)
    token_info = add_cda_environment(child_env, cda_mode)

    if script.get("rts_context", False):
        add_rts_context_environment(child_env)

    child_env["PYTHONUNBUFFERED"] = "1"
    return child_env, token_info


# ---------------------------------------------------------------------------
# Command-line handling
# ---------------------------------------------------------------------------

def split_arguments(argument_text):
    """Split editable Windows-style arguments into a subprocess argument list."""
    if not argument_text or not argument_text.strip():
        return []

    values = shlex.split(str(argument_text), posix=False)
    result = []

    # shlex with posix=False preserves surrounding quotes. Remove those
    # quotes because Popen receives an argument list rather than a shell line.
    for value in values:
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in ("'", '"')
        ):
            value = value[1:-1]

        result.append(value)

    return result


# ---------------------------------------------------------------------------
# Live output window
# ---------------------------------------------------------------------------

class AppendOutput(Runnable):
    def __init__(self, output_area, text):
        self.output_area = output_area
        self.text = text

    def run(self):
        self.output_area.append(self.text)
        document = self.output_area.getDocument()
        self.output_area.setCaretPosition(document.getLength())


def append_output(output_area, text):
    """Append text safely from the process thread to the Swing UI."""
    SwingUtilities.invokeLater(AppendOutput(output_area, text))


def create_output_window(script_name):
    """Create and display a window for live subprocess output."""
    output_area = JTextArea(30, 110)
    output_area.setEditable(False)
    output_area.setLineWrap(False)

    frame = JFrame("Python Output: %s" % script_name)
    frame.setDefaultCloseOperation(JFrame.DISPOSE_ON_CLOSE)
    frame.getContentPane().setLayout(BorderLayout())
    frame.getContentPane().add(
        JScrollPane(output_area),
        BorderLayout.CENTER,
    )
    frame.pack()
    frame.setLocationRelativeTo(None)
    frame.setVisible(True)

    return output_area


# ---------------------------------------------------------------------------
# Background process
# ---------------------------------------------------------------------------

class ChildProcessRunner(Runnable):
    def __init__(self, selected_script, argument_text, output_area):
        self.selected_script = selected_script
        self.argument_text = argument_text
        self.output_area = output_area

    def run(self):
        process = None

        try:
            python_home = os.environ.get(PYTHON_HOME_ENV)
            if not python_home:
                raise RuntimeError(
                    "%s environment variable is not set"
                    % PYTHON_HOME_ENV
                )

            python_executable = os.path.join(
                python_home,
                "python.exe",
            )
            script_path = self.selected_script["path"]

            if not os.path.isfile(python_executable):
                raise RuntimeError(
                    "Python executable not found: %s"
                    % python_executable
                )

            if not os.path.isfile(script_path):
                raise RuntimeError(
                    "Python script not found: %s" % script_path
                )

            append_output(
                self.output_area,
                "Preparing requested runtime context...\n",
            )

            child_env, token_info = build_child_environment(
                self.selected_script
            )

            child_env["PATH"] = (
                python_home
                + os.pathsep
                + child_env.get("PATH", "")
            )

            # -u makes stdin, stdout, and stderr unbuffered in CPython.
            command = [python_executable, "-u", script_path]
            command.extend(split_arguments(self.argument_text))

            append_output(
                self.output_area,
                "\nStarting command:\n%s\n\n"
                % subprocess.list2cmdline(command),
            )
            append_output(
                self.output_area,
                "CDA context: %s\n"
                % self.selected_script.get("cda", CDA_NONE),
            )
            if "CDA_API_ROOT" in child_env:
                append_output(
                    self.output_area,
                    "CDA_API_ROOT: %s\n" % child_env["CDA_API_ROOT"],
                )
                append_output(
                    self.output_area,
                    "OFFICE: %s\n" % child_env["OFFICE"],
                )
            if token_info is not None:
                append_output(
                    self.output_area,
                    "Access-token lifetime: %s seconds\n"
                    % token_info["lifetime_seconds"],
                )
                append_output(
                    self.output_area,
                    "Access token before refresh: %s seconds remaining\n"
                    % token_info["previous_remaining_seconds"],
                )
                append_output(
                    self.output_area,
                    "Access token at launch: %s seconds remaining\n"
                    % token_info["remaining_seconds"],
                )
                append_output(
                    self.output_area,
                    "Pre-launch token refresh: %s\n"
                    % ("yes" if token_info["refreshed"] else "not needed"),
                )
            append_output(
                self.output_area,
                "RTS context snapshot: %s\n\n"
                % (
                    "enabled"
                    if self.selected_script.get("rts_context", False)
                    else "disabled"
                ),
            )

            # Never print CDA_ACCESS_TOKEN or CDA_REFRESH_TOKEN.
            process = subprocess.Popen(
                command,
                cwd=os.path.dirname(script_path),
                env=child_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            # Stream output instead of waiting for communicate() to return.
            while True:
                line = process.stdout.readline()

                if line:
                    try:
                        text = line.decode("utf-8", "replace")
                    except AttributeError:
                        text = str(line)

                    append_output(self.output_area, text)
                elif process.poll() is not None:
                    break

            return_code = process.wait()

            append_output(
                self.output_area,
                "\nProcess finished with return code %s.\n"
                % return_code,
            )

        except Exception as error:
            append_output(
                self.output_area,
                "\nLauncher error: %s\n" % error,
            )

        finally:
            if process is not None and process.stdout is not None:
                try:
                    process.stdout.close()
                except Exception:
                    pass

            System.clearProperty(RUNNING_PROPERTY)


# ---------------------------------------------------------------------------
# Script-selection dialog
# ---------------------------------------------------------------------------

def describe_script_context(script):
    """Return a short description of a script's requested capabilities."""
    parts = ["CDA: %s" % script.get("cda", CDA_NONE)]
    parts.append(
        "RTS context: %s"
        % ("yes" if script.get("rts_context", False) else "no")
    )
    return " | ".join(parts)


class ScriptSelectionListener(ActionListener):
    def __init__(self, selector, argument_field, context_field):
        self.selector = selector
        self.argument_field = argument_field
        self.context_field = context_field

    def actionPerformed(self, event):
        index = self.selector.getSelectedIndex()
        script = SCRIPTS[index]
        self.argument_field.setText(script["args"])
        self.context_field.setText(describe_script_context(script))


def show_launcher():
    if not SCRIPTS:
        JOptionPane.showMessageDialog(
            None,
            "No scripts are configured.",
            "Python Launcher",
            JOptionPane.ERROR_MESSAGE,
        )
        return

    if System.getProperty(RUNNING_PROPERTY) == "true":
        JOptionPane.showMessageDialog(
            None,
            "A Python job launched by this tool is already running.",
            "Python Launcher",
            JOptionPane.WARNING_MESSAGE,
        )
        return

    selector = JComboBox()
    for script in SCRIPTS:
        selector.addItem(script["name"])

    argument_field = JTextField(SCRIPTS[0]["args"], 70)
    context_field = JTextField(describe_script_context(SCRIPTS[0]), 70)
    context_field.setEditable(False)
    selector.addActionListener(
        ScriptSelectionListener(selector, argument_field, context_field)
    )

    panel = JPanel(GridLayout(0, 1, 5, 5))
    panel.add(JLabel("Python script:"))
    panel.add(selector)
    panel.add(JLabel("Injected context:"))
    panel.add(context_field)
    panel.add(JLabel("Arguments:"))
    panel.add(argument_field)

    choice = JOptionPane.showConfirmDialog(
        None,
        panel,
        "Run CPython Script",
        JOptionPane.OK_CANCEL_OPTION,
        JOptionPane.PLAIN_MESSAGE,
    )

    if choice != JOptionPane.OK_OPTION:
        return

    selected_script = SCRIPTS[selector.getSelectedIndex()]
    argument_text = str(argument_field.getText())

    output_area = create_output_window(
        selected_script["name"]
    )

    System.setProperty(RUNNING_PROPERTY, "true")

    worker = Thread(
        ChildProcessRunner(
            selected_script,
            argument_text,
            output_area,
        ),
        "RTS-CPython-Launcher",
    )
    worker.setDaemon(True)
    worker.start()


class ShowLauncher(Runnable):
    def run(self):
        show_launcher()


# Swing dialogs and components should be created on the event-dispatch thread.
if SwingUtilities.isEventDispatchThread():
    show_launcher()
else:
    SwingUtilities.invokeAndWait(ShowLauncher())
