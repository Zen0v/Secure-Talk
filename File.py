# Interface with the os and filesystem
from os.path import getsize, splitext, isfile
from os import remove, rename
from sys import exit
from platform import system
import subprocess
import time

# Store file attribute lengths
import struct

# Compression algorithms
import lzma
import bz2
import gzip

DEFAULT_CHUNKSIZE = 128000  # 1000 bytes = 1 kilobyte
