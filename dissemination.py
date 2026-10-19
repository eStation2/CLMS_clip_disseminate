import os
import sys
import pycurl
import datetime
import glob
from io import BytesIO, StringIO

# Load variables from a local .env file if present (optional; see .env.template).
# Falls back to the process environment and the production defaults below when
# python-dotenv is not installed or no .env exists.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

# --- GLOBAL CONFIGURATION (unchanging settings) ---
# All values are read from the environment (see .env / .env.template), falling
# back to the original production CDSE defaults when unset.
CLMS_HOME = os.environ.get("CLMS_HOME", "/home/eouser/clms")

FTP_SERVER = os.environ.get("CLMS_FTP_SERVER", "ofids.eumetsat.int")
LOG_BASE_DIR = os.environ.get("CLMS_LOG_DIR", os.path.join(CLMS_HOME, "logs"))
CONFIG_BASE_DIR = os.environ.get("CLMS_CONFIG_DIR", os.path.join(CLMS_HOME, "config"))
PROCESSED_OUTPUT_LIST = os.environ.get(
    "CLMS_PROCESSED_OUTPUT_FILE", os.path.join(CONFIG_BASE_DIR, "processed_output_files.txt")
)
LOCAL_IP = os.environ.get("CLMS_FTP_LOCAL_IP", "46.60.20.214")
PORT_RANGE_START = int(os.environ.get("CLMS_FTP_PORT_RANGE_START", "50000"))
PORT_RANGE_END = int(os.environ.get("CLMS_FTP_PORT_RANGE_END", "50100"))

# Per-ROI output directories (shared with the clipping step via the same vars).
OUTPUT_AFR_DIR = os.environ.get("CLMS_OUTPUT_AFR_DIR", os.path.join(CLMS_HOME, "outputs", "afr"))
OUTPUT_SOAM_DIR = os.environ.get("CLMS_OUTPUT_SOAM_DIR", os.path.join(CLMS_HOME, "outputs", "sam"))
# --------------------------------------------------

# --- REGIONAL PROFILES ---
# Credentials (user_pwd) and remote dirs come from the environment so they are
# not hardcoded in the (duplicated) dissemination scripts. netrc_file is kept
# as-is since the current upload uses USERPWD, not NETRC_FILE.
REGIONS = {
    "AFR": {
        "remote_dir": os.environ.get("CLMS_AFR_REMOTE_DIR", "/out/groups/vito-open-afr-test"),
        "local_dir": OUTPUT_AFR_DIR,
        "netrc_file": os.path.join(CONFIG_BASE_DIR, "vgt4afr.netrc"),
        "user_pwd": os.environ.get("CLMS_AFR_USER_PWD", "user:pwd"),
        "list_file_suffix": "afr"
    },
    "SOAM": {
        "remote_dir": os.environ.get("CLMS_SOAM_REMOTE_DIR", "/out/groups/vito-open-sam-test"),
        "local_dir": OUTPUT_SOAM_DIR,
        "netrc_file": os.path.join(CONFIG_BASE_DIR, "devcocast.netrc"),
        "user_pwd": os.environ.get("CLMS_SOAM_USER_PWD", "user:pwd"),
        "list_file_suffix": "soam"
    }
}
# -------------------------

# Global variable to hold the current log file path for the log_message function
CURRENT_LOG_FILE = None


# --- HELPER FUNCTIONS ---

def set_log_file(region_name):
    """Sets the log file path based on the region and returns the path."""
    global CURRENT_LOG_FILE
    log_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    CURRENT_LOG_FILE = os.path.join(LOG_BASE_DIR, f"ftp_upload_{region_name}_{log_timestamp}.log")
    return CURRENT_LOG_FILE


def log_message(message, level="INFO"):
    """Writes a message to the console and the current log file."""
    if not CURRENT_LOG_FILE:
        print(f"CRITICAL: Log file not set! Message: {message}", file=sys.stderr)
        return

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp} | {level}] {message}"

    # Print to console (stdout)
    print(message, end="")
    sys.stdout.flush()

    # Append to log file
    with open(CURRENT_LOG_FILE, 'a') as f:
        f.write(log_line + "\n")


def load_uploaded_list(file_path):
    """Loads the set of filenames that have already been uploaded."""
    if not os.path.exists(file_path):
        return set()
    try:
        with open(file_path, 'r') as f:
            return {line.strip() for line in f if line.strip()}
    except IOError:
        log_message(f"ERROR: Could not read upload list file: {file_path}", level="ERROR")
        return set()


def write_to_uploaded_list(file_path, filename):
    """Appends a single filename to the persistent upload list."""
    try:
        with open(file_path, 'a') as f:
            f.write(f"{filename}\n")
    except IOError:
        log_message(f"CRITICAL: Could not write filename to upload list: {file_path}", level="CRITICAL")


def remove_from_processed_list(file_path, filename):
    """Removes a single filename from the persistent upload list by rewriting the file."""
    try:
        # 1. Read all lines from the file
        with open(file_path, 'r') as f:
            lines = f.readlines()

        # Strip newline characters from the filename to match file content
        filename_to_match = f"{filename.strip()}\n"

        new_lines = []
        item_removed = False

        # 2. Filter out the line containing the filename
        for line in lines:
            # Check if the line matches the filename (including the newline character)
            if line.strip() == filename.strip():
                item_removed = True
                continue  # Skip this line

            new_lines.append(line)

        if not item_removed:
            log_message(f"WARNING: Filename '{filename}' not found in the upload list.", level="WARNING")
            return

        # 3. Rewrite the file completely with the new lines
        with open(file_path, 'w') as f:
            f.writelines(new_lines)

        print(f"Successfully removed '{filename}' from the persistent upload list.")

    except IOError as e:
        log_message(f"CRITICAL: Could not read/write the upload list file: {file_path}. Error: {e}", level="CRITICAL")
        pass  # Handle logging here


# Example usage:
# remove_from_uploaded_list('/path/to/upload_list.txt', 'file_b.zip')
# --- CORE UPLOAD FUNCTION (now accepts config) ---

def run_ftp_upload(region_name, config):
    """Performs the FTP upload process for a single region using pycurl."""

    local_dir = config["local_dir"]
    remote_dir = config["remote_dir"]
    netrc_file = config["netrc_file"]
    user_pwd = config["user_pwd"]
    uploaded_dir = os.path.join(local_dir, "uploaded")

    upload_list_file = os.path.join(CONFIG_BASE_DIR, f"ftp_uploaded_{config['list_file_suffix']}.list")

    # 1. Initialize log file
    current_log_file = set_log_file(region_name)

    with open(current_log_file, 'w') as f:
        f.write(f"--- FTP Upload Script Started for {region_name}: {datetime.datetime.now()} ---\n")

    log_message(f"FTP Upload Script Started for {region_name} at {datetime.datetime.now().strftime('%H:%M:%S')}\n",
                level="START")
    log_message(f"Local Directory: {local_dir}\n")
    log_message(f"Tracking List File: {upload_list_file}\n")
    log_message(f"Tracking Processed output File: {PROCESSED_OUTPUT_LIST}\n")
    log_message(f"Log File: {current_log_file}\n")

    # Create the uploaded directory
    try:
        os.makedirs(uploaded_dir, exist_ok=True)
        log_message(f"Created/Checked directory: {uploaded_dir}\n")
    except Exception as e:
        log_message(f"ERROR: Failed to create uploaded directory {uploaded_dir}: {e}", level="CRITICAL")
        return 1  # Return error code

    log_message("------------------------------------------------\n")

    # 2. Load the list of already uploaded files
    uploaded_files_set = load_uploaded_list(upload_list_file)
    processed_files_set = load_uploaded_list(PROCESSED_OUTPUT_LIST)
    # 3. Iterate over files in LOCAL_DIR
    for file_path in glob.glob(os.path.join(local_dir, '*.zip')):
        if not os.path.isfile(file_path):
            continue

        filename = os.path.basename(file_path)

        # 4. Check if already processed
        if filename in uploaded_files_set :
            log_message(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Skipping: {filename}... ALREADY UPLOADED\n")
            continue
        # Additional check if needed
        if filename not in processed_files_set :
            log_message(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Skipping: {filename}... NOT in the Processed output list\n")
            continue

        # 5. Define remote paths
        remote_tmp_name = f"{filename}.tmp"
        remote_tmp_path = os.path.join(remote_dir, remote_tmp_name)
        remote_final_path = os.path.join(remote_dir, filename)

        log_message(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Processing: {filename}...")

        # 6. pycurl setup
        buffer = BytesIO()
        # log_buffer = StringIO()
        c = pycurl.Curl()
        curl_exit_code = 99

        try:
            file_handle = open(file_path, 'rb')
            file_size = os.path.getsize(file_path)

            # Configure pycurl options
            c.setopt(pycurl.URL, f"ftp://{FTP_SERVER}{remote_tmp_path}")
            # c.setopt(pycurl.NETRC_FILE, netrc_file)
            c.setopt(pycurl.USERPWD, user_pwd)
            # Disable EPSV to force the use of the older PASV command
            # c.setopt(pycurl.FTP_SKIP_PASV_IP, 1)  # Tells libcurl to ignore the IP address in the PASV response
            # c.setopt(pycurl.FTP_PRET, 1)  # Optional: useful for some firewalls
            # c.setopt(pycurl.USE_SSL, pycurl.USESSL_ALL)
            # c.setopt(pycurl.SSL_VERIFYPEER, 0)
            # c.setopt(pycurl.FTP_CREATE_MISSING_DIRS, 1)
            # if hasattr(pycurl, 'SSLCIPHER_LIST'):
            #     c.setopt(pycurl.SSLCIPHER_LIST, "DEFAULT@SECLEVEL=1")
            # elif hasattr(pycurl, 'SSLCIPHER'):
            #     # Fallback for older versions, though this is where the error occurred
            #     c.setopt(pycurl.SSLCIPHER, "DEFAULT@SECLEVEL=1")
            # else:
            #     # Handle the case where neither is available
            #     print("Warning: Cannot set SSL cipher list.")
            # Configure FTP PORT mode with specified IP and port range
            c.setopt(pycurl.FTPPORT, f"{LOCAL_IP}:{PORT_RANGE_START}-{PORT_RANGE_END}")
            c.setopt(pycurl.UPLOAD, 1)
            c.setopt(pycurl.READDATA, file_handle)
            c.setopt(pycurl.INFILESIZE, file_size)

            # Logging/Output handling
            c.setopt(pycurl.VERBOSE, 1)
            # c.setopt(pycurl.DEBUGFUNCTION,
            #          lambda debug_type, debug_msg: log_buffer.write(debug_msg.decode('utf-8', 'ignore')))
            c.setopt(pycurl.WRITEDATA, buffer)

            # Post-transfer commands (Rename)
            post_commands = [
                f"RNFR {remote_tmp_path}",
                f"RNTO {remote_final_path}"
            ]
            c.setopt(pycurl.POSTQUOTE, post_commands)

            c.perform()
            curl_exit_code = 0

        except pycurl.error as e:
            curl_exit_code = e.args[0]
            log_message(f"PycURL Error ({curl_exit_code}): {e.args[1]}", level="ERROR")

        finally:
            if 'file_handle' in locals() and not file_handle.closed:
                file_handle.close()
            c.close()

            # # Write the verbose log to the file
            # pycurl_output = log_buffer.getvalue()
            # filtered_output = '\n'.join(
            #     line for line in pycurl_output.splitlines()
            #     if 'Warning: Using default' not in line
            # )
            # with open(current_log_file, 'a') as f:
            #     f.write(f"\n--- PycURL Debug Output for {filename} ---\n{filtered_output}\n--- End PycURL Output ---\n")

        # 7. Check results and perform file actions
        if curl_exit_code == 0:
            log_message(f"SUCCESS (Renamed to {filename})")

            # ACTION 1: Add filename to the persistent list and remove from Processed output list
            write_to_uploaded_list(upload_list_file, filename)

            remove_from_processed_list(PROCESSED_OUTPUT_LIST, filename)
            # ACTION 2: Move the file to the uploaded directory
            try:
                os.rename(file_path, os.path.join(uploaded_dir, filename))
                log_message(f" | MOVED to {uploaded_dir}\n")
            except OSError as e:
                log_message(f" | FAILED to move file to {uploaded_dir}: {e}\n", level="ERROR")
        else:
            log_message(f"FAILED. Curl Exit Code: {curl_exit_code}. Check log file for details.\n", level="ERROR")

    log_message("------------------------------------------------\n")
    log_message(f"--- FTP Upload Script Finished for {region_name}: {datetime.datetime.now()} ---\n", level="FINISH")
    return 0  # Success


# --- MAIN EXECUTION ---

if __name__ == "__main__":

    # 1. Execute upload for Africa
    afr_status = run_ftp_upload("AFR", REGIONS["AFR"])

    # 2. Execute upload for South America
    soam_status = run_ftp_upload("SOAM", REGIONS["SOAM"])

    # Exit with an error code if either region failed
    if afr_status != 0 or soam_status != 0:
        sys.exit(1)

    sys.exit(0)