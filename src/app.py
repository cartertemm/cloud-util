import sys
import os
import appdirs
import wx
import config
import icloud


name = "Cloud Util"
version = "0.1 Beta"
author="Carter Temm <cartertemm@gmail.com>"
data_dir = appdirs.user_data_dir("cloud_util", roaming=True)
config_path = os.path.join(data_dir, "config.ini")
app = None

def init():
	"""non-UI critical app initialization"""
	global app
	icloud.load_pyicloud()
	if not os.path.isdir(data_dir):
		os.makedirs(data_dir)
	config.load(config_path)
	app = wx.App()

def exit():
	app.ExitMainLoop()
	sys.exit()
