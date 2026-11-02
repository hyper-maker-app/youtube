"""Keep Chrome CDP (Port 9223) running as a daemon process for Google Flow & Gemini WebAPI."""
import os
import subprocess
import sys

user_data = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile")
chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

if not os.path.isfile(chrome):
    print(f"Error: Chrome executable not found at {chrome}")
    sys.exit(1)

cmd = [
    chrome,
    "--remote-debugging-port=9223",
    f"--user-data-dir={user_data}",
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "https://gemini.google.com",
    "https://flow.google.com",
]

print("Starting isolated Flow Chrome process on port 9223...")
sys.stdout.flush()
proc = subprocess.Popen(cmd)
print(f"Chrome running with PID: {proc.pid}")
sys.stdout.flush()

try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
