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
		self.bind_events()
		self.Layout()

	def make_tabs(self):
		self.find_my = FindMy(self.tabs)
		self.tabs.AddPage(self.find_my, "Find my", True)

	def bind_events(self):
		self.Bind(wx.EVT_CLOSE, self.on_close)

	def on_close(self, event):
		app.exit()

class FindMy(wx.Panel):
	def __init__(self, parent, *args, **kwargs):
		super().__init__(parent, *args, **kwargs)
		self.ps_time = 0
		self.update_time = 0
		self.lm_time = 0
		self.init_ui()
		self.bind_events()
		self._populate_devices()

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
		self.lost_mode = wx.Button(self, label="&Lost mode")
		actions_sizer.Add(self.lost_mode, 0, wx.ALL, 5)
		self.update = wx.Button(self, label="&Refresh")
		actions_sizer.Add(self.update, 0, wx.ALL, 5)
		self.main_sizer.Add(device_sizer)
		self.main_sizer.Add(actions_sizer)
		self.SetSizer(self.main_sizer)
		self.Layout()

	def bind_events(self):
		self.Bind(wx.EVT_BUTTON, self.on_play_sound, self.play_sound)
		self.Bind(wx.EVT_BUTTON, self.on_refresh, self.update)
		self.Bind(wx.EVT_BUTTON, self.on_lost_mode, self.lost_mode)

	def on_refresh(self, event):
		self._populate_devices(True)

	def _populate_devices(self, focus_list=False):
		@run_threaded
		def _inner():
			devices = icloud.service.devices
			items = []
			for device in devices:
				item = ", ".join((device["name"], device["deviceDisplayName"], str(round(device["batteryLevel"]*100, 3))+"%", device["batteryStatus"]))
				items.append(item)
			wx.CallAfter(_set_items, items)
		def _set_items(items):
			self.device_list.Freeze()
			self.device_list.Clear()
			self.device_list.Set(items)
			self.device_list.Thaw()
			if self.device_list.GetCount() > 0:
				self.device_list.SetSelection(0)
			if focus_list:
				self.device_list.SetFocus()
		# to prevent unnecessary API spam, only allow updating every three seconds
		if time.time() - self.update_time < 3:
			return
		self.update_time = time.time()
		_inner()

	def on_play_sound(self, event):
		# to prevent unnecessary API spam, only allow one sound to play per second
		if time.time() - self.ps_time < 1:
			return
		self.ps_time = time.time()
		idx = self.device_list.GetSelection()
		if idx == wx.NOT_FOUND:
			return
		icloud.service.devices[idx].play_sound()
		dialogs.information(self, "Playing", "A sound is being played on "+icloud.service.devices[idx]["name"]+". Listen up!")

	def on_lost_mode(self, event):
		if time.time() - self.lm_time < 1:
			return
		self.lm_time = time.time()
		idx = self.device_list.GetSelection()
		if idx == wx.NOT_FOUND:
			return
		dlg = LostDeviceDialog(self)
		res = dlg.ShowModal()
		if res != wx.ID_OK:
			return
		message = dlg.message.GetValue()
		number = dlg.number.GetValue()
		passcode = dlg.passcode.GetValue()
		icloud.service.devices[idx].lost_device(number, message, passcode)
		dialogs.information(self, "Success", "Lost mode enabled on "+icloud.service.devices[idx]["name"])

class LostDeviceDialog(wx.Dialog):
	def __init__(self, parent, title="Lost device"):
		super().__init__(parent, title=title)
		self.init_ui()

	def init_ui(self):
		self.main_sizer = wx.BoxSizer(wx.VERTICAL)
		msg_sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, label="Message: ")
		self.message = wx.TextCtrl(self, style=wx.TE_MULTILINE)
		msg_sizer.Add(label, 0, wx.ALL, 5)
		msg_sizer.Add(self.message, 0, wx.ALL, 5)
		number_sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, label="Owner phone number (leave blank for none): ")
		self.number = wx.TextCtrl(self)
		number_sizer.Add(label, 0, wx.ALL, 5)
		number_sizer.Add(self.number, 0, wx.ALL, 5)
		pc_sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, label="New Passcode (leave blank for none): ")
		self.passcode = wx.TextCtrl(self)
		pc_sizer.Add(label, 0, wx.ALL, 5)
		pc_sizer.Add(self.passcode, 0, wx.ALL, 5)
		label = wx.StaticText(self, label="Repeat new passcode")
		self.pc_repeat = wx.TextCtrl(self)
		pc_sizer.Add(label, 0, wx.ALL, 5)
		pc_sizer.Add(self.pc_repeat, 0, wx.ALL, 5)
		self.main_sizer.Add(msg_sizer)
		self.main_sizer.Add(number_sizer)
		self.main_sizer.Add(pc_sizer)
		btn_sizer = wx.StdDialogButtonSizer()
		cancel_btn = wx.Button(parent=self, id=wx.ID_CANCEL)
		self.SetEscapeId(cancel_btn.GetId())
		self.ok_btn = wx.Button(parent=self, id=wx.ID_OK)
		btn_sizer.AddButton(cancel_btn)
		btn_sizer.AddButton(self.ok_btn)
		self.main_sizer.Add(btn_sizer)
		btn_sizer.Realize()
		self.main_sizer.Add(btn_sizer)
		self.SetSizerAndFit(self.main_sizer)
		self.Layout()

	def bind_events(self):
		self.Bind(wx.EVT_BUTTON, self.on_ok, self.ok_btn)

	def on_ok(self):
		message = self.message.GetValue()
		number = self.number.GetValue()
		passcode = self.passcode.GetValue()
		repeat = self.pc_repeat.GetValue()
		if not message:
			dialogs.error(self, "Error", "A message is required")
			self.message.SetFocus()
			return
		if passcode and passcode != repeat:
			dialogs.error(self, "Error", "The provided passwords must be the same")
			self.passcode.SetFocus()
			return
		self.Close()
