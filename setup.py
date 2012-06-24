# A simple setup script to create an executable using PyQt4. This also
# demonstrates the method for creating a Windows executable that does not have
# an associated console.
#
# PyQt4app.py is a very simple type of PyQt4 application
#
# Run the build process by running the command 'python setup.py build'
#
# If everything works well you should find a subdirectory in the build
# subdirectory that contains the files needed to run the application

import sys
import os
os.environ['PATH']=''

from cx_Freeze import setup, Executable

base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
        name = "Wake on LAN",
        version = "1.0",
        description = "Wake up remote hosts from system tray",
        options = {"build_exe": {"includes": ["atexit", "sip"]}},
        executables = [Executable("run.py", icon="res/power.ico", base=base)])

