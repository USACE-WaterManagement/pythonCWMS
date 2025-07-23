import sys
import os
import subprocess
import threading
import urllib
import tempfile
import shutil
import hashlib
import json

from javax.swing import (
    JFrame, JPanel, JLabel, JTextField, JButton, JFileChooser, JTextArea, JScrollPane,
    JOptionPane, BorderFactory
)
from java.awt import (
    BorderLayout, GridLayout, Insets, FlowLayout, Dimension
)
from java.awt.event import ActionListener
from java.io import File as JFile
from javax.swing import SwingUtilities, JProgressBar # JProgressBar was missing from this specific import line

class InstallerGUI(JFrame):
    def __init__(self):
        super(InstallerGUI, self).__init__("CWMS Portable Python Installer")
        self.setDefaultCloseOperation(JFrame.DISPOSE_ON_CLOSE)
        self.setSize(850, 550)
        self.setLocationRelativeTo(None)

        # --- Default hardcoded URL for the configuration file ---
        # This is the starting point for the Config URL input field.
        self.default_config_url = "https://raw.githubusercontent.com/msweier/pythonCWMS/refs/heads/main/pythonCWMS_config.json" # <--- IMPORTANT: CHANGE THIS URL!
        # --------------------------------------------------------

        # Initialize these as None; they will be populated from the config file
        self.python_7z_url = None
        self.expected_sha256_hash = None
        self.destination_dir = None
        self.env_var_name = None
        self.python_exe_sub_dir = None

        self.python_exe_path = None
        self.temp_7z_file = None
        self.cancel_event = threading.Event()

        self.setup_ui()
        self.log_area.append("Welcome to the Portable Python Installer!\n")
        
        # Start initial config loading in a separate thread
        self._update_ui(lambda: self.log_area.append("Attempting to load initial configuration from: {}\n".format(self.default_config_url)))
        self._update_ui(lambda: self.status_label.setText("Status: Loading configuration..."))
        self._update_ui(lambda: self.progress_bar.setIndeterminate(True))
        
        config_load_thread = threading.Thread(target=self._run_load_config_in_thread, args=(self.default_config_url,))
        config_load_thread.daemon = True
        config_load_thread.start()


    def setup_ui(self):
        # --- Input Panel ---
        input_panel = JPanel(GridLayout(5, 1, 5, 5)) # Increased rows for new config URL input
        input_panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10))

        # New: Config URL Row
        self.config_url_field = JTextField(40)
        self.config_url_field.setText(self.default_config_url) # Set default config URL
        self.config_url_field.setEditable(True)
        self.load_config_button = JButton("Load Config")
        self.load_config_button.addActionListener(self._load_config_action)
        
        config_url_row_panel = JPanel(FlowLayout(FlowLayout.LEFT))
        config_url_row_panel.add(JLabel("Config URL:"))
        config_url_row_panel.add(self.config_url_field)
        config_url_row_panel.add(self.load_config_button)
        input_panel.add(config_url_row_panel)

        # 7z URL Row (now populated by config)
        self.seven_z_field = JTextField(40)
        self.seven_z_field.setEditable(True) # User can still change if they want
        
        seven_z_url_row_panel = JPanel(FlowLayout(FlowLayout.LEFT))
        seven_z_url_row_panel.add(JLabel("Python .7z URL:"))
        seven_z_url_row_panel.add(self.seven_z_field)
        input_panel.add(seven_z_url_row_panel)

        # Destination Directory Row (now populated by config)
        self.dest_dir_field = JTextField(40)
        self.dest_dir_field.setEditable(False)
        dest_dir_button = JButton("Browse Destination...")
        dest_dir_button.addActionListener(self.browse_destination)
        
        dest_dir_row_panel = JPanel(FlowLayout(FlowLayout.LEFT))
        dest_dir_row_panel.add(JLabel("Installation Directory:"))
        dest_dir_row_panel.add(self.dest_dir_field)
        dest_dir_row_panel.add(dest_dir_button)
        input_panel.add(dest_dir_row_panel)

        # Environment Variable Name Row (now populated by config)
        self.env_var_name_field = JTextField(20)
        env_var_name_row_panel = JPanel(FlowLayout(FlowLayout.LEFT))
        env_var_name_row_panel.add(JLabel("Environment Variable Name:"))
        env_var_name_row_panel.add(self.env_var_name_field)
        input_panel.add(env_var_name_row_panel)
        
        # Install/Cancel Buttons Row
        button_row_panel = JPanel(FlowLayout(FlowLayout.CENTER))
        self.install_button = JButton("Install Portable Python")
        self.install_button.addActionListener(self.perform_installation)
        self.install_button.setEnabled(False) # Disabled until config loaded
        button_row_panel.add(self.install_button)

        self.cancel_button = JButton("Cancel")
        self.cancel_button.addActionListener(self.cancel_installation)
        self.cancel_button.setEnabled(False)
        button_row_panel.add(self.cancel_button)
        
        input_panel.add(button_row_panel)

        # --- Log Panel ---
        self.log_area = JTextArea(10, 50)
        self.log_area.setEditable(False)
        self.log_area.setLineWrap(True)
        self.log_area.setWrapStyleWord(True)
        log_scroll_pane = JScrollPane(self.log_area)
        log_scroll_pane.setBorder(BorderFactory.createTitledBorder("Installation Log"))
        log_scroll_pane.setPreferredSize(Dimension(600, 200))

        # --- Progress Bar and Status ---
        progress_panel = JPanel(BorderLayout())
        progress_panel.setBorder(BorderFactory.createEmptyBorder(5, 10, 5, 10))
        self.progress_bar = JProgressBar()
        self.progress_bar.setStringPainted(True)
        self.progress_bar.setString("Ready")
        self.progress_bar.setIndeterminate(False)
        
        self.status_label = JLabel("Status: Idle")

        progress_panel.add(self.status_label, BorderLayout.NORTH)
        progress_panel.add(self.progress_bar, BorderLayout.CENTER)


        # --- Main Layout ---
        self.getContentPane().add(input_panel, BorderLayout.NORTH)
        self.getContentPane().add(log_scroll_pane, BorderLayout.CENTER)
        self.getContentPane().add(progress_panel, BorderLayout.SOUTH)

    def _load_config_action(self, event):
        """Action listener for the 'Load Config' button."""
        config_url = self.config_url_field.getText().strip()
        if not config_url:
            JOptionPane.showMessageDialog(self, "Please enter a Config URL.", "Input Error", JOptionPane.ERROR_MESSAGE)
            return
        
        self._update_ui(lambda: self.log_area.append("Attempting to load configuration from: {}\n".format(config_url)))
        self._update_ui(lambda: self.status_label.setText("Status: Loading configuration..."))
        self._update_ui(lambda: self.progress_bar.setIndeterminate(True))
        
        load_config_thread = threading.Thread(target=self._run_load_config_in_thread, args=(config_url,))
        load_config_thread.daemon = True
        load_config_thread.start()


    def _run_load_config_in_thread(self, config_url):
        """
        Runs the config download and parsing in a separate thread.
        """
        self._update_ui(lambda: self.load_config_button.setEnabled(False))
        self._update_ui(lambda: self.install_button.setEnabled(False))
        
        temp_config_filepath = None
        try:
            temp_config_file_obj = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            temp_config_filepath = temp_config_file_obj.name
            temp_config_file_obj.close()

            urllib.urlretrieve(config_url, temp_config_filepath)
            
            with open(temp_config_filepath, 'r') as f:
                config_data = json.load(f)
            
            # Populate instance variables (used by installation thread)
            self.python_7z_url = config_data.get("python_download_url")
            self.expected_sha256_hash = config_data.get("python_expected_hash_sha256")
            self.destination_dir = config_data.get("default_install_directory")
            self.env_var_name = config_data.get("default_env_var_name")
            self.python_exe_sub_dir = config_data.get("python_exe_sub_directory")

            # Validate essential fields
            if not self.python_7z_url or not self.expected_sha256_hash or \
               not self.destination_dir or not self.env_var_name or \
               self.python_exe_sub_dir is None:
                raise ValueError("Missing essential configuration keys in JSON.")

            # Update UI fields with loaded values
            self._update_ui(lambda: self.seven_z_field.setText(self.python_7z_url))
            self._update_ui(lambda: self.dest_dir_field.setText(self.destination_dir))
            self._update_ui(lambda: self.env_var_name_field.setText(self.env_var_name))
            
            self._update_ui(lambda: self.log_area.append("Configuration loaded successfully.\n"))
            self._update_ui(lambda: self.install_button.setEnabled(True)) # Enable install button on success
            self._update_ui(lambda: self.status_label.setText("Status: Configuration Loaded"))
            
        except IOError, e:
            self._update_ui(lambda: self.log_area.append("ERROR: Failed to download configuration file from {}: {}\n".format(config_url, e)))
            self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Failed to download configuration.\nError: {}".format(e), "Configuration Error", JOptionPane.ERROR_MESSAGE))
            self._update_ui(lambda: self.status_label.setText("Status: Config Load Failed"))
        except ValueError, e:
            self._update_ui(lambda: self.log_area.append("ERROR: Failed to parse configuration JSON or missing required keys: {}\n".format(e)))
            self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Invalid configuration file.\nError: {}".format(e), "Configuration Error", JOptionPane.ERROR_MESSAGE))
            self._update_ui(lambda: self.status_label.setText("Status: Config Load Failed"))
        except Exception, e:
            self._update_ui(lambda: self.log_area.append("ERROR: An unexpected error occurred while loading configuration: {}\n".format(e)))
            self._update_ui(lambda: JOptionPane.showMessageDialog(self, "An unexpected error occurred during configuration loading.\nError: {}".format(e), "Configuration Error", JOptionPane.ERROR_MESSAGE))
            self._update_ui(lambda: self.status_label.setText("Status: Config Load Failed"))
        finally:
            if temp_config_filepath and os.path.exists(temp_config_filepath):
                try:
                    os.remove(temp_config_filepath)
                    self._update_ui(lambda: self.log_area.append("Cleaned up temporary config file: {}\n".format(temp_config_filepath)))
                except Exception, e:
                    self._update_ui(lambda: self.log_area.append("Warning: Could not remove temporary config file {}: {}\n".format(temp_config_filepath, e)))
            
            self._update_ui(lambda: self.load_config_button.setEnabled(True))
            self._update_ui(lambda: self.progress_bar.setIndeterminate(False))
            # If install button was enabled by success, leave it. Otherwise, leave it disabled.


    def browse_destination(self, event):
        file_chooser = JFileChooser()
        file_chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY)
        file_chooser.setDialogTitle("Select Installation Destination Directory")
        # Use self.destination_dir which should be populated by config
        if self.destination_dir:
            file_chooser.setSelectedFile(JFile(self.destination_dir))
        else:
            default_user_path = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "PortablePython")
            file_chooser.setSelectedFile(JFile(default_user_path))

        return_val = file_chooser.showSaveDialog(self)
        if return_val == JFileChooser.APPROVE_OPTION:
            selected_dir = file_chooser.getSelectedFile()
            self.destination_dir = selected_dir.getAbsolutePath()
            self.dest_dir_field.setText(self.destination_dir)
            self.log_area.append("Selected Destination: {}\n".format(self.destination_dir))
    
    def cancel_installation(self, event):
        """Called when the Cancel button is pressed."""
        response = JOptionPane.showConfirmDialog(self, 
                                                 "Are you sure you want to cancel the installation?\nAny partial files will be removed.",
                                                 "Confirm Cancellation", 
                                                 JOptionPane.YES_NO_OPTION, 
                                                 JOptionPane.WARNING_MESSAGE)
        if response == JOptionPane.YES_OPTION:
            self._update_ui(lambda: self.log_area.append("\nCancellation requested by user...\n"))
            self._update_ui(lambda: self.status_label.setText("Status: Cancelling..."))
            self.cancel_event.set()
            self._update_ui(lambda: self.cancel_button.setEnabled(False))

    def _update_ui(self, callable_func):
        SwingUtilities.invokeLater(callable_func)

    def _download_progress_hook(self, blocks_transferred, block_size, total_size):
        """Callback for urllib.urlretrieve to update download progress."""
        if self.cancel_event.is_set():
            raise IOError("Download cancelled by user.")

        if total_size > 0:
            percentage = int(100.0 * blocks_transferred * block_size / total_size)
            if percentage > 100:
                percentage = 100
            self._update_ui(lambda: self.progress_bar.setValue(percentage))
            self._update_ui(lambda: self.progress_bar.setString("Downloading: {}%".format(percentage)))
            
            downloaded_mb = (blocks_transferred * block_size) / (1024.0 * 1024.0)
            total_mb = total_size / (1024.0 * 1024.0)
            self._update_ui(lambda: self.status_label.setText("Status: Downloading {:.2f}MB / {:.2f}MB".format(downloaded_mb, total_mb)))
        else:
            self._update_ui(lambda: self.progress_bar.setIndeterminate(True))
            self._update_ui(lambda: self.status_label.setText("Status: Downloading (size unknown)..."))

    @staticmethod
    def _calculate_file_hash(filepath, hash_algo='sha256', block_size=65536):
        """Calculates the hash of a file."""
        hasher = hashlib.new(hash_algo)
        try:
            with open(filepath, 'rb') as f:
                buf = f.read(block_size)
                while len(buf) > 0:
                    hasher.update(buf)
                    buf = f.read(block_size)
            return hasher.hexdigest()
        except Exception, e:
            raise Exception("Failed to calculate hash of {}: {}".format(filepath, e))

    def _add_to_user_path(self, env_var_name):
        """
        Checks if %ENV_VAR_NAME% and %ENV_VAR_NAME%\Scripts are in the user's PATH
        and adds them if they are not.
        """
        self._update_ui(lambda: self.log_area.append("\nChecking/updating user PATH...\n"))
        current_user_path = ""
        
        try:
            reg_query_cmd = ["reg", "query", "HKCU\\Environment", "/v", "Path"]
            reg_process = subprocess.Popen(reg_query_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
            reg_stdout_bytes, reg_stderr_bytes = reg_process.communicate()
            
            reg_stdout = reg_stdout_bytes.decode('utf-8', errors='ignore')
            
            if reg_process.returncode == 0:
                for line in reg_stdout.splitlines():
                    if "REG_EXPAND_SZ" in line or "REG_SZ" in line:
                        parts = line.split("    ") 
                        if len(parts) >= 3:
                            current_user_path = parts[3].strip()
                            break
            else:
                self._update_ui(lambda: self.log_area.append("Warning: Could not read current user PATH from registry. Error: {}\n".format(reg_stderr_bytes.decode('utf-8', errors='ignore'))))
        except Exception, e:
            self._update_ui(lambda: self.log_area.append("Warning: Error querying registry for PATH: {}\n".format(e)))
        
        paths_to_add_str = [
            "%{}%".format(env_var_name),
            "%{}\\Scripts%".format(env_var_name)
        ]
        
        expanded_paths_to_add = [os.path.normpath(os.path.expandvars(p)) for p in paths_to_add_str]

        current_paths_normalized = [os.path.normpath(os.path.expandvars(p)) for p in current_user_path.split(os.pathsep) if p]
        
        new_paths_for_setx = []
        for i, path_to_check in enumerate(expanded_paths_to_add):
            if path_to_check not in current_paths_normalized:
                new_paths_for_setx.append(paths_to_add_str[i])

        if new_paths_for_setx:
            self._update_ui(lambda: self.log_area.append("Adding {} to user PATH...\n".format(", ".join(new_paths_for_setx))))
            
            new_path_value = current_user_path
            if new_path_value and not new_path_value.endswith(os.pathsep):
                new_path_value += os.pathsep

            new_path_value += os.pathsep.join(new_paths_for_setx)

            setx_path_cmd = ["setx", "Path", new_path_value]
            try:
                setx_path_process = subprocess.Popen(setx_path_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
                setx_path_stdout_bytes, setx_path_stderr_bytes = setx_path_process.communicate()
                
                setx_path_stdout = setx_path_stdout_bytes.decode('utf-8', errors='ignore')
                setx_path_stderr = setx_path_stderr_bytes.decode('utf-8', errors='ignore')

                if setx_path_process.returncode == 0:
                    self._update_ui(lambda: self.log_area.append("Successfully added to user PATH.\n"))
                    self._update_ui(lambda: self.log_area.append("SETX PATH Output: {}\n".format(setx_path_stdout)))
                    self._update_ui(lambda: self.log_area.append("\nIMPORTANT: User PATH changes will be available in NEW command prompt windows.\n"))
                    self._update_ui(lambda: self.log_area.append('\nUser can launch python with "pythonCWMS" in the command prompt window.\n'))
                else:
                    self._update_ui(lambda: self.log_area.append("Failed to add to user PATH. Error: {}. Output: {}\n".format(setx_path_stderr, setx_path_stdout)))
            except Exception, e:
                self._update_ui(lambda: self.log_area.append("Error executing SETX for PATH: {}\n".format(e)))
        else:
            self._update_ui(lambda: self.log_area.append("User PATH already contains required Python entries. No changes made.\n"))


    def _cleanup_destination_dir(self, path):
        """Removes the destination directory and its contents."""
        if os.path.exists(path):
            self._update_ui(lambda: self.log_area.append("Cleaning up partially installed directory: {}\n".format(path)))
            self._update_ui(lambda: self.status_label.setText("Status: Cleaning up..."))
            try:
                shutil.rmtree(path)
                self._update_ui(lambda: self.log_area.append("Cleaned up: {}\n".format(path)))
            except Exception, e:
                self._update_ui(lambda: self.log_area.append("Warning: Failed to clean up directory {}: {}\n".format(path, e)))
                self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Warning: Could not fully clean up directory {}. Please remove it manually if needed.\nError: {}".format(path, e), "Cleanup Warning", JOptionPane.WARNING_MESSAGE))


    def _run_installation_in_thread(self, current_python_7z_url, current_expected_sha256_hash, current_destination_dir, current_env_var_name, current_python_exe_sub_dir, seven_z_exe_path):
        """
        This method runs in a separate thread to perform the download, extraction,
        and environment variable setup, using the *current* values from the UI fields.
        """
        self.temp_7z_file = None
        self.cancel_event.clear()
        
        try:
            self._update_ui(lambda: self.install_button.setEnabled(False))
            self._update_ui(lambda: self.load_config_button.setEnabled(False)) # Disable load config button during install
            self._update_ui(lambda: self.cancel_button.setEnabled(True))
            self._update_ui(lambda: self.progress_bar.setIndeterminate(False))
            self._update_ui(lambda: self.progress_bar.setValue(0))
            self._update_ui(lambda: self.progress_bar.setString("Starting..."))
            self._update_ui(lambda: self.status_label.setText("Status: Initializing installation..."))
            self._update_ui(lambda: self.log_area.append("\nStarting installation process...\n"))

            if self.cancel_event.is_set(): raise Exception("Installation cancelled.")

            # --- 1. Download .7z file ---
            self._update_ui(lambda: self.log_area.append("Downloading '{}'...\n".format(current_python_7z_url)))
            self._update_ui(lambda: self.status_label.setText("Status: Downloading .7z file..."))
            
            temp_file_obj = tempfile.NamedTemporaryFile(delete=False, suffix=".7z")
            self.temp_7z_file = temp_file_obj.name
            temp_file_obj.close()

            try:
                urllib.urlretrieve(current_python_7z_url, self.temp_7z_file, reporthook=self._download_progress_hook)
                self._update_ui(lambda: self.log_area.append("Download complete: {}\n".format(self.temp_7z_file)))
            except IOError, e:
                self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Error downloading file: {}".format(e), "Download Error", JOptionPane.ERROR_MESSAGE))
                self._update_ui(lambda: self.log_area.append("Download failed: {}\n".format(e)))
                raise Exception("Download failed.")
            except Exception, e:
                self._update_ui(lambda: JOptionPane.showMessageDialog(self, "An unexpected error occurred during download: {}".format(e), "Download Error", JOptionPane.ERROR_MESSAGE))
                self._update_ui(lambda: self.log_area.append("Download failed with unexpected error: {}\n".format(e)))
                raise Exception("Unexpected download error.")
            
            if self.cancel_event.is_set(): raise Exception("Installation cancelled.")

            # --- 2. Verify Downloaded File Hash ---
            self._update_ui(lambda: self.status_label.setText("Status: Verifying file integrity..."))
            self._update_ui(lambda: self.log_area.append("Verifying downloaded file hash...\n"))
            self._update_ui(lambda: self.log_area.append("Expected SHA256 hash: {}\n".format(current_expected_sha256_hash)))
            try:
                calculated_hash = self._calculate_file_hash(self.temp_7z_file, 'sha256')
                self._update_ui(lambda: self.log_area.append("Calculated SHA256 hash: {}\n".format(calculated_hash)))
                if calculated_hash.lower() != current_expected_sha256_hash.lower():
                    self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Hash mismatch! Downloaded file is corrupted or tampered with.\nExpected: {}\nCalculated: {}".format(current_expected_sha256_hash, calculated_hash), "Integrity Error", JOptionPane.ERROR_MESSAGE))
                    self._update_ui(lambda: self.log_area.append("ERROR: Hash mismatch! Expected {} but calculated {}.\n".format(current_expected_sha256_hash, calculated_hash)))
                    raise Exception("File integrity check failed (hash mismatch).")
                self._update_ui(lambda: self.log_area.append("File hash verified successfully.\n"))
            except Exception, e:
                self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Error calculating hash: {}".format(e), "Hash Error", JOptionPane.ERROR_MESSAGE))
                self._update_ui(lambda: self.log_area.append("ERROR: Failed to calculate hash of downloaded file: {}\n".format(e)))
                raise Exception("Failed to calculate hash.")

            if self.cancel_event.is_set(): raise Exception("Installation cancelled.")

            # --- 3. Create Destination Directory (if it doesn't exist) ---
            self._update_ui(lambda: self.status_label.setText("Status: Creating destination directory..."))
            try:
                if not os.path.exists(current_destination_dir):
                    os.makedirs(current_destination_dir)
                    self._update_ui(lambda: self.log_area.append("Created destination directory: {}\n".format(current_destination_dir)))
                else:
                    self._update_ui(lambda: self.log_area.append("Destination directory already exists: {}\n".format(current_destination_dir)))
            except Exception, e:
                self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Error creating destination directory: {}".format(e), "Directory Error", JOptionPane.ERROR_MESSAGE))
                self._update_ui(lambda: self.log_area.append("Error creating destination directory: {}\n".format(e)))
                raise Exception("Failed to create destination directory.")

            if self.cancel_event.is_set(): raise Exception("Installation cancelled.")

            # --- 4. Extract 7z Archive ---
            self._update_ui(lambda: self.progress_bar.setIndeterminate(True))
            self._update_ui(lambda: self.progress_bar.setString("Extracting..."))
            self._update_ui(lambda: self.status_label.setText("Status: Extracting files..."))
            self._update_ui(lambda: self.log_area.append("Extracting '{}' to '{}'...\n".format(self.temp_7z_file, current_destination_dir)))
            
            command = [
                seven_z_exe_path,
                "x",
                self.temp_7z_file,
                "-o{}".format(current_destination_dir),
                "-y"
            ]

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
            
            while True:
                if self.cancel_event.is_set():
                    self._update_ui(lambda: self.log_area.append("Cancellation requested during extraction. Terminating 7z.exe...\n"))
                    try:
                        process.terminate()
                    except Exception, e:
                        self._update_ui(lambda: self.log_area.append("Warning: Could not terminate 7z.exe process: {}\n".format(e)))
                    raise Exception("Installation cancelled.")

                output_line = process.stdout.readline()
                if output_line == '' and process.poll() is not None:
                    break
                if output_line:
                    decoded_line = output_line.decode('utf-8', errors='ignore').strip()
                    self._update_ui(lambda: self.log_area.append(decoded_line + "\n"))
                    if decoded_line.startswith("Extracting "):
                        filename = decoded_line[len("Extracting "):].split('\n')[0].strip()
                        self._update_ui(lambda: self.status_label.setText("Status: Extracting " + filename))

            stderr_output = process.stderr.read().decode('utf-8', errors='ignore')

            if stderr_output:
                self._update_ui(lambda: self.log_area.append("--- 7z Errors ---\n"))
                self._update_ui(lambda: self.log_area.append(stderr_output + "\n"))

            if process.returncode == 0:
                self._update_ui(lambda: self.log_area.append("7z extraction completed successfully.\n"))
                
                self.python_exe_path = os.path.join(current_destination_dir, current_python_exe_sub_dir, "python.exe")

                if not os.path.exists(self.python_exe_path):
                    self._update_ui(lambda: self.log_area.append("ERROR: Expected python.exe at '{}' but it was not found.\n".format(self.python_exe_path)))
                    self._update_ui(lambda: self.log_area.append("Please ensure your .7z archive extracts into the structure specified in the config: '{}' relative to the destination directory.\n".format(current_python_exe_sub_dir)))
                    self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Extraction completed, but python.exe not found at expected location.\nSee log for details.", "Extraction Warning", JOptionPane.WARNING_MESSAGE))
                    self.python_exe_path = None
                else:
                    self._update_ui(lambda: self.log_area.append("Identified Python executable at: {}\n".format(self.python_exe_path)))

            else:
                self._update_ui(lambda: self.log_area.append("7z extraction failed with error code {}.\n".format(process.returncode)))
                self._update_ui(lambda: JOptionPane.showMessageDialog(self, "7-Zip extraction failed. See log for details (Error code: {}).".format(process.returncode), "Extraction Error", JOptionPane.ERROR_MESSAGE))
                raise Exception("7-Zip extraction failed.")

            if self.cancel_event.is_set(): raise Exception("Installation cancelled.")

            # --- 5. Set Python_HOME Environment Variable ---
            if self.python_exe_path:
                python_base_dir = os.path.dirname(self.python_exe_path)
                self._update_ui(lambda: self.status_label.setText("Status: Setting {} environment variable...".format(current_env_var_name)))
                self._update_ui(lambda: self.log_area.append("Setting user environment variable '{}' to '{}'...\n".format(current_env_var_name, python_base_dir)))
                
                setx_command = ["setx", current_env_var_name, python_base_dir]
                
                setx_process = subprocess.Popen(setx_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
                setx_stdout_bytes, setx_stderr_bytes = setx_process.communicate()
                
                setx_stdout = setx_stdout_bytes.decode('utf-8', errors='ignore')
                setx_stderr = setx_stderr_bytes.decode('utf-8', errors='ignore')
                
                self._update_ui(lambda: self.log_area.append("--- SETX Output for {}---\n".format(current_env_var_name)))
                if setx_stdout:
                    self._update_ui(lambda: self.log_area.append(setx_stdout))
                if setx_stderr:
                    self._update_ui(lambda: self.log_area.append("--- SETX Errors for {}---\n".format(current_env_var_name)))
                    self._update_ui(lambda: self.log_area.append(setx_stderr))

                if setx_process.returncode == 0:
                    self._update_ui(lambda: self.log_area.append("Environment variable '{}' set successfully for the current user.\n".format(current_env_var_name)))
                    self._update_ui(lambda: self.log_area.append("NOTE: This variable will be available in NEW command prompt windows or applications launched AFTER this installation.\n"))
                    
                    self._add_to_user_path(current_env_var_name)

                    self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Portable Python installed and environment variables set successfully!\n\n" +
                                                               "NOTE: Environment variables will be active in new command prompt windows.\n\n" + 
                                                               'Python can be accessed using "pythonCWMS" in the command prompt or scripts.',
                                                               "Installation Complete", JOptionPane.INFORMATION_MESSAGE))
                else:
                    self._update_ui(lambda: self.log_area.append("Failed to set environment variable. SETX return code: {}.\n".format(setx_process.returncode)))
                    self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Failed to set environment variable. See log for details (Error code: {}).".format(setx_process.returncode), "Environment Variable Error", JOptionPane.ERROR_MESSAGE))
                    raise Exception("Failed to set main environment variable.")
            else:
                self._update_ui(lambda: self.log_area.append("Skipping environment variable setup as python.exe path could not be determined.\n"))
                self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Portable Python installed, but could not set environment variable automatically.\n" +
                                                                   "Please manually set the environment variable for your Python installation.",
                                                                   "Installation Partial", JOptionPane.WARNING_MESSAGE))
            
            self._installation_finished(True)

        except Exception, e:
            is_cancelled = self.cancel_event.is_set()
            if is_cancelled:
                self._update_ui(lambda: JOptionPane.showMessageDialog(self, "Installation cancelled by user.", "Installation Cancelled", JOptionPane.INFORMATION_MESSAGE))
                self._update_ui(lambda: self.log_area.append("Installation cancelled by user.\n"))
            else:
                self._update_ui(lambda: JOptionPane.showMessageDialog(self, "An unexpected error occurred during installation: {}".format(e), "Installation Error", JOptionPane.ERROR_MESSAGE))
                self._update_ui(lambda: self.log_area.append("An unexpected error occurred: {}\n".format(e)))
            
            # Cleanup partially installed directory only if it wasn't a clean cancellation
            if not is_cancelled: 
                self._cleanup_destination_dir(current_destination_dir)
            
            self._installation_finished(False, is_cancelled)

        finally:
            if self.temp_7z_file and os.path.exists(self.temp_7z_file):
                try:
                    os.remove(self.temp_7z_file)
                    self._update_ui(lambda: self.log_area.append("Cleaned up temporary .7z file: {}\n".format(self.temp_7z_file)))
                except Exception, e:
                    self._update_ui(lambda: self.log_area.append("Warning: Could not remove temporary .7z file {}: {}\n".format(self.temp_7z_file, e)))


    def _installation_finished(self, success, was_cancelled=False):
        """Called when the installation thread completes (success, failure, or cancellation)."""
        self._update_ui(lambda: self.install_button.setEnabled(True))
        self._update_ui(lambda: self.load_config_button.setEnabled(True)) # Re-enable load config button
        self._update_ui(lambda: self.cancel_button.setEnabled(False))
        self._update_ui(lambda: self.progress_bar.setIndeterminate(False))
        
        if was_cancelled:
            self._update_ui(lambda: self.progress_bar.setString("Cancelled"))
            self._update_ui(lambda: self.status_label.setText("Status: Installation Cancelled!"))
            self._update_ui(lambda: self.progress_bar.setValue(0))
        elif success:
            self._update_ui(lambda: self.progress_bar.setString("Done"))
            self._update_ui(lambda: self.status_label.setText("Status: Installation Complete!"))
            self._update_ui(lambda: self.progress_bar.setValue(100))
        else:
            self._update_ui(lambda: self.progress_bar.setString("Failed"))
            self._update_ui(lambda: self.status_label.setText("Status: Installation Failed!"))
            self._update_ui(lambda: self.progress_bar.setValue(0))


    def perform_installation(self, event):
        # Retrieve current values from UI fields, as user might have changed them
        current_python_7z_url = self.seven_z_field.getText().strip()
        current_destination_dir = self.dest_dir_field.getText().strip()
        current_env_var_name = self.env_var_name_field.getText().strip()
        
        # These values come from the last successful config load
        current_expected_sha256_hash = self.expected_sha256_hash 
        current_python_exe_sub_dir = self.python_exe_sub_dir


        self.log_area.setText("")
        self.log_area.append("Starting pre-installation checks...\n")

        # --- 1. Validate Inputs (from UI) ---
        if not current_python_7z_url:
            JOptionPane.showMessageDialog(self, "Please enter a Python .7z URL.", "Input Error", JOptionPane.ERROR_MESSAGE)
            self.log_area.append("Error: Python .7z URL is empty.\n")
            return
        if not (current_python_7z_url.startswith("http://") or current_python_7z_url.startswith("https://")):
            JOptionPane.showMessageDialog(self, "Please enter a valid URL (must start with http:// or https://).", "Input Error", JOptionPane.ERROR_MESSAGE)
            self.log_area.append("Error: Invalid URL format.\n")
            return

        if not current_destination_dir:
            JOptionPane.showMessageDialog(self, "Please select an installation destination directory.", "Input Error", JOptionPane.ERROR_MESSAGE)
            self.log_area.append("Error: No destination directory selected.\n")
            return
        if not current_env_var_name:
            JOptionPane.showMessageDialog(self, "Please enter an environment variable name.", "Input Error", JOptionPane.ERROR_MESSAGE)
            self.log_area.append("Error: Environment variable name is empty.\n")
            return
        
        # Validate that config values are present (meaning config was loaded successfully)
        if not current_expected_sha256_hash or len(current_expected_sha256_hash) != 64:
             JOptionPane.showMessageDialog(self, "Internal Error: Expected SHA256 hash is missing or invalid. Please load configuration first.", "Input Error", JOptionPane.ERROR_MESSAGE)
             self.log_area.append("Error: Expected SHA256 hash is missing or invalid from config.\n")
             return
        if current_python_exe_sub_dir is None:
             JOptionPane.showMessageDialog(self, "Internal Error: Python executable sub-directory is missing from config. Please load configuration first.", "Input Error", JOptionPane.ERROR_MESSAGE)
             self.log_area.append("Error: Python executable sub-directory is missing from config.\n")
             return


        # --- 2. Find 7z.exe ---
        seven_z_exe_path = None
        
        program_files_path = os.environ.get('ProgramFiles')
        if not program_files_path:
            program_files_path = "C:\\Program Files"

        standard_7z_path = os.path.join(program_files_path, "7-Zip", "7z.exe")

        if os.path.exists(standard_7z_path):
            seven_z_exe_path = standard_7z_path
            self.log_area.append("Using system-wide 7z.exe at: {}\n".format(seven_z_exe_path))
        else:
            script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            bundled_7z_path_1 = os.path.join(script_dir, "7z", "7z.exe")
            bundled_7z_path_2 = os.path.join(script_dir, "7z.exe")

            if os.path.exists(bundled_7z_path_1):
                seven_z_exe_path = bundled_7z_path_1
                self.log_area.append("Using bundled 7z.exe at: {}\n".format(seven_z_exe_path))
            elif os.path.exists(bundled_7z_path_2):
                seven_z_exe_path = bundled_7z_path_2
                self.log_area.append("Using bundled 7z.exe at: {}\n".format(seven_z_exe_path))
            else:
                JOptionPane.showMessageDialog(self, "Error: 7z.exe not found.\nAttempted: '{}', '{}', and '{}'.\nPlease ensure 7-Zip is installed or '7z.exe' is bundled correctly.".format(standard_7z_path, bundled_7z_path_1, bundled_7z_path_2), "Error", JOptionPane.ERROR_MESSAGE)
                self.log_area.append("Error: 7z.exe not found at any expected location.\n")
                return
        
        if not seven_z_exe_path:
            JOptionPane.showMessageDialog(self, "Internal Error: 7z.exe path could not be determined.", "Error", JOptionPane.ERROR_MESSAGE)
            self.log_area.append("Internal Error: 7z.exe path could not be determined after all checks.\n")
            return

        # --- Start installation in a new thread ---
        installation_thread = threading.Thread(target=self._run_installation_in_thread, 
                                             args=(current_python_7z_url, current_expected_sha256_hash, current_destination_dir, current_env_var_name, current_python_exe_sub_dir, seven_z_exe_path))
        installation_thread.daemon = True
        installation_thread.start()


# Main execution block
if __name__ == "__main__":
    frame = InstallerGUI()
    frame.setVisible(True)

