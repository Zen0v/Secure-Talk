# Author: Rodrigo Graca

from enum import Enum

# Generate the windows binary
"""pyinstaller.exe -F -w -i padlock.ico -n "Secure Talk" GUI.py"""

# Define encryption settings (Bytes)
RSA_KEY_LENGTH = 4096
AES_KEY_LENGTH = 32

# Define app settings
WINDOW_SIZE = (450, 500)

# Define how often the output is reloaded
OUTPUT_REFRESH_RATE = .5

# Public IP of common relay server
SERVER = 'zenov.ddns.net'


# Provide commands to communicate between threads
class DisplayCommands(Enum):
    clearOutput = 1


class SocketCommands:
    DISPLAY = '0'
    FILE_SEND = '1'
