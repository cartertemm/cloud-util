"""
Convenience functions for dealing with pyiCloud and the iCloud web API
"""

import sys
from utils import run_threaded


# loading this module is slow, so we confine it's import to a separate thread as to not slow down launch of the application too much
# assuming that it'll be ready in time for when we need to authenticate
pyicloud = None
@run_threaded
def load_pyicloud():
	global pyicloud
	import pyicloud

service = None
