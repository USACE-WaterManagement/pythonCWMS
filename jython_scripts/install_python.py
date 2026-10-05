from java.net import URI

RELEASE_URL = "https://github.com/USACE-WaterManagement/pythonCWMS/releases/latest"
MESSAGE = """The Jython installer was retired in Python CWMS 2.0.

1. Open:
   https://github.com/USACE-WaterManagement/pythonCWMS/releases/latest
2. Download PythonCWMS-Installer.zip
3. Extract it
4. Run Install-PythonCWMS.cmd

Your existing Python installation has not been changed."""

print(MESSAGE)

try:
    from java.awt import Desktop
    from javax.swing import JOptionPane

    can_browse = (Desktop.isDesktopSupported() and
                  Desktop.getDesktop().isSupported(Desktop.Action.BROWSE))
    if can_browse:
        choice = JOptionPane.showConfirmDialog(
            None, MESSAGE + "\n\nOpen the release page now?",
            "Python CWMS installer retired",
            JOptionPane.YES_NO_OPTION,
            JOptionPane.INFORMATION_MESSAGE)
        if choice == JOptionPane.YES_OPTION:
            Desktop.getDesktop().browse(URI(RELEASE_URL))
    else:
        JOptionPane.showMessageDialog(
            None, MESSAGE, "Python CWMS installer retired",
            JOptionPane.INFORMATION_MESSAGE)
except Exception, error:
    print("Could not open the release page automatically: {0}".format(error))
    print("Open this URL in a browser: " + RELEASE_URL)
