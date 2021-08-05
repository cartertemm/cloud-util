import time
import wx
from pyicloud import *
from pyicloud import exceptions as pyi_exceptions
import app
import config
import dialogs
import icloud
from utils import run_threaded


class LoginDialog(wx.Dialog):
	def __init__(self, parent, title="Login"):
		super().__init__(parent, title=title)
		self.init_ui()
		email = config.config.get("email")
		if email:
			self.username.SetValue(email)
		self.remember_me.SetValue(True)
		self.bind_events()

	def init_ui(self):
		main_sizer = wx.BoxSizer(wx.VERTICAL)
		email_sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, label="Apple ID: ")
		self.username = wx.TextCtrl(self)
		email_sizer.Add(label, 0, wx.ALL, 5)
		email_sizer.Add(self.username, 0, wx.ALL, 5)
		password_sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, label="Password: ")
		self.password = wx.TextCtrl(self, style=wx.TE_PASSWORD)
		password_sizer.Add(label, 0, wx.ALL, 5)
		password_sizer.Add(self.password, 0, wx.ALL, 5)
		cb_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.remember_me = wx.CheckBox(self, label="Remember me")
		cb_sizer.Add(self.remember_me)
		main_sizer.Add(email_sizer)
		main_sizer.Add(password_sizer)
		main_sizer.Add(cb_sizer)
		btn_sizer = wx.StdDialogButtonSizer()
		self.login_btn = wx.Button(self, id=wx.ID_OK, label="&Login")
		btn_sizer.AddButton(self.login_btn)
		self.close_btn= wx.Button(self, id=wx.ID_CLOSE)
		btn_sizer.AddButton(self.close_btn)
		btn_sizer.Realize()
		main_sizer.Add(btn_sizer)
		self.SetEscapeId(self.close_btn.GetId())
		self.SetSizerAndFit(main_sizer)
		self.Layout()

	def bind_events(self):
		self.Bind(wx.EVT_BUTTON, self.on_login, self.login_btn)

	def on_login(self, event):
		username = self.username.GetValue()
		password = self.password.GetValue()
		if not username or not password:
			dialogs.error(self, "Error", "both an Apple ID and password must be supplied")
			self.username.SetFocus()
			return
		# here we attempt authentication
		try:
			icloud.service = PyiCloudService(username, password, cookie_directory=app.data_dir)
		except pyi_exceptions.PyiCloudException as exc:
			dialogs.error(self, "Login failed", str(exc))
		if self.remember_me.IsChecked():
			config.config["email"] = username
			config.config.write()
		if icloud.service.requires_2fa:
			dlg = wx.TextEntryDialog(self, caption="Two-factor authentication required", message="Enter the code you received from an approved device")
			res = dlg.ShowModal()
			if res == wx.ID_OK:
				res = icloud.service.validate_2fa_code(dlg.GetValue())
				if not res:
					dialogs.error(self, "Error validating code", "Please try again, making sure to enter the correct security code")
					return
				if not icloud.service.is_trusted_session and self.remember_me.IsChecked():
					res = icloud.service.trust_session()
					if not res:
						dialog.warning(self, "Warning", "There was an error obtaining a trusted session. This unfortunately means you may have to reauthenticate next time")
		elif icloud.service.requires_2sa:
			pass  # implement this later
		self.Close()

class MainFrame(wx.Frame):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.SetTitle("Cloud Util")
		self.panel = wx.Panel(self)
		self.main_sizer = wx.BoxSizer(wx.VERTICAL)
		self.tabs = wx.Notebook(self.panel)
		self.make_tabs()
		self.main_sizer.Add(self.tabs, 0, wx.ALL, 5)
		self.panel.SetSizerAndFit(self.main_sizer)
		self.Layout()

	def make_tabs(self):
		self.find_my = FindMy(self.tabs)
		self.tabs.AddPage(self.find_my, "Find my", True)

class FindMy(wx.Panel):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.ps_time = 0
		self.update_time = 0
		self.init_ui()
		self.bind_events()
		self.Layout()
		self.populate_devices()

	def init_ui(self):
		self.main_sizer= wx.BoxSizer(wx.VERTICAL)
		device_sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, label="Devices")
		self.device_list = wx.ListBox(self)
		device_sizer.Add(label, 0, wx.ALL, 5)
		device_sizer.Add(self.device_list, 0, wx.ALL, 5)
		actions_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.info = wx.Button(self, label="&Info")
		actions_sizer.Add(self.info, 0, wx.ALL, 5)
		self.play_sound = wx.Button(self, label="&Play sound")
		actions_sizer.Add(self.play_sound, 0, wx.ALL, 5)
		self.display_message = wx.Button(self, label="&Display message")
		actions_sizer.Add(self.display_message, 0, wx.ALL, 5)
		self.lost_mode = wx.Button(self, label="&Lost mode")
		actions_sizer.Add(self.lost_mode, 0, wx.ALL, 5)
		self.update = wx.Button(self, label="&Refresh")
		actions_sizer.Add(self.update, 0, wx.ALL, 5)
		self.main_sizer.Add(device_sizer)
		self.main_sizer.Add(actions_sizer)
		self.SetSizer(self.main_sizer)

	def bind_events(self):
		self.Bind(wx.EVT_BUTTON, self.on_play_sound, self.play_sound)
		self.Bind(wx.EVT_BUTTON, self.populate_devices, self.update)

	def populate_devices(self, event=None):
		self._populate_devices()

	def _populate_devices(self):
		@run_threaded
		def _inner():
			devices = icloud.service.devices
			items = []
			for device in devices:
				item = ", ".join((device["name"], device["deviceDisplayName"], str(round(device["batteryLevel"]*100, 3))+"%", device["batteryStatus"]))
				items.append(item)
			wx.CallAfter(self.device_list.Set, items)
		# to prevent unnecessary API spam, only allow updating every three seconds
		if time.time() - self.update_time < 3:
			return
		self.update_time = time.time()
		self.device_list.Freeze()
		self.device_list.Clear()
		_inner()
		self.device_list.Thaw()

	def on_play_sound(self, event):
		# to prevent unnecessary API spam, only allow one sound to play per second
		if time.time() - self.ps_time < 1:
			return
		self.ps_time = time.time()
		idx = self.device_list.GetSelection()
		if idx == wx.NOT_FOUND:
			return
		icloud.service.devices[idx].play_sound()
		dialogs.information(self, "Playing", "A sound is being played on devices[idx].name. Listen up!")
