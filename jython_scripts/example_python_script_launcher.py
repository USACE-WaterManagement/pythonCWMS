import os
import subprocess

# path to your python script
python_script_path = r"C:\code\CWMS-data-acquisition-python\src\get_USGS_measurements\get_USGS_measurements.py"

# any arguments you may need, set to None or '' if not needed
args = "-d 60"

##################################################################################################

# 1. Get the expanded pythonCWMS directory from the environment variable
pythoncwms_home = os.environ.get('PYTHON_CWMS_HOME')  # Get the value of PYTHON_CWMS_HOME
if not pythoncwms_home:
    print("Error: PYTHON_CWMS_HOME environment variable not set.")
    exit()  # Or handle the error appropriately

# 2. Construct the pythonCWMS directory path using os.path.join

pythoncwms_path = os.path.join(pythoncwms_home, "python.exe") # Path to the executable

# 3. Check if the pythonCWMS_dir is in the PATH
current_path = os.environ.get('PATH', '')
if pythoncwms_home not in current_path:
    os.environ['PATH'] = pythoncwms_home + os.pathsep + current_path
    print("Updated PATH:", os.environ['PATH'])
else:
    print("pythonCWMS directory already in PATH.")


# 4. Test using os.system()
print("\n--- Testing pythonCWMS directly with os.system() ---")
return_code_os_system = os.system("pythonCWMS --version") 
print("os.system return code:", return_code_os_system)

if return_code_os_system == 0:
    print("os.system succeeded. pythonCWMS is accessible.")
else:
    print("os.system failed. pythonCWMS is NOT accessible. Check the PATH.")

# 5. Subprocess Call (only if the above test succeeds)
if return_code_os_system == 0:
    python_executable = pythoncwms_path  # Use the constructed path
    

    cmd = [python_executable, python_script_path]
    if not args or args != '':
    	cmd.append(args)
    	
    print("Executing command:", cmd)

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    stdout_str = stdout.decode('utf-8')
    stderr_str = stderr.decode('utf-8')
    stdout_str = stdout_str.replace('\r\n', '\n')
    stderr_str = stderr_str.replace('\r\n', '\n')
    print("STDOUT:\n")
    print(stdout_str)
    print("STDERR:\n")
    print(stderr_str)

    return_code = process.returncode
    print("Return Code:", return_code)
else:
    print("\nSkipping subprocess call because os.system failed.")
