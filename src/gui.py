import time
import json
import wx
import pyperclip
import tformat
from pyicloud import *
from pyicloud import exceptions as pyi_exceptions
import app
import config
import dialogs
import geocoder
import icloud
import utils


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
		self.contacts = Contacts(self.tabs)
		self.tabs.AddPage(self.contacts, "Contacts", False)

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
		self.locate = wx.Button(self, label="L&ocate (experimental)")
		actions_sizer.Add(self.locate, 0, wx.ALL, 5)
		self.play_sound = wx.Button(self, label="&Play sound")
		actions_sizer.Add(self.play_sound, 0, wx.ALL, 5)
		self.lost_mode = wx.Button(self, label="&Lost mode")
		actions_sizer.Add(self.lost_mode, 0, wx.ALL, 5)
		self.update = wx.Button(self, label="&Refresh")
		actions_sizer.Add(self.update, 0, wx.ALL, 5)
		if app.debug:
			self.copy = wx.Button(self, label="&Copy to clipboard (debug)")
			actions_sizer.Add(self.copy, 0, wx.ALL, 5)
		self.main_sizer.Add(device_sizer)
		self.main_sizer.Add(actions_sizer)
		self.SetSizer(self.main_sizer)
		self.Layout()

	def bind_events(self):
		self.Bind(wx.EVT_BUTTON, self.on_play_sound, self.play_sound)
		self.Bind(wx.EVT_BUTTON, self.on_info, self.info)
		self.Bind(wx.EVT_BUTTON, self.on_locate, self.locate)
		self.Bind(wx.EVT_BUTTON, self.on_refresh, self.update)
		self.Bind(wx.EVT_BUTTON, self.on_lost_mode, self.lost_mode)
		if app.debug:
			self.Bind(wx.EVT_BUTTON, self.on_copy, self.copy)

	def on_copy(self, event):
		idx = self.device_list.GetSelection()
		if idx == wx.NOT_FOUND:
			return
		pyperclip.copy(json.dumps(icloud.service.devices[idx].data, indent=4))

	def on_refresh(self, event):
		self._populate_devices(True)

	def on_locate(self, event):
		@utils.run_threaded
		def inner():
			idx = self.device_list.GetSelection()
			if idx == wx.NOT_FOUND:
				return
			location = icloud.service.devices[idx].get("location")
			if not location:
				dialogs.error(self, "Error", "This device has no associated location information")
				return
			idx = self.device_list.GetSelection()
			if idx == wx.NOT_FOUND:
				return
			lat = location.get("latitude")
			lon = location.get("longitude")
			if not lat or not lon:
				dialogs.error(self, "Error", "Unable to retrieve device coordinates")
				return
			g = geocoder.geocode(lat, lon, addressdetails=0)
			name = g.get("display_name")
			elapsed = tformat.format_time(time.time() - location.get("timeStamp")/1000)
			wx.CallAfter(dialogs.information, self, "Location", "As of "+elapsed+" ago, your device is located at or near "+name+".")
		inner()

	def _populate_devices(self, focus_list=False):
		@utils.run_threaded
		def _inner():
			items = []
			try:
				devices = icloud.service.devices
			except PyiCloudNoDevicesException:
				pass  # nothing to do
			else:
				for device in devices:
					item = self._format_device(device)
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

	def _format_device(self, info):
		statuses = {
			"200": "Online",
			"201": "Offline",
			"203": "Pending",
			"204": "Unregistered",
		}
		info = info.status(["batteryStatus"])
		return ", ".join((
			info["name"],
			info["deviceDisplayName"],
			str(round(info["batteryLevel"]*100, 3))+"%",
			info["batteryStatus"],
		))

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

	def on_info(self, event):
		idx = self.device_list.GetSelection()
		if idx == wx.NOT_FOUND:
			return
		dlg = DeviceInfoDialog(self, icloud.service.devices[idx])
		dlg.ShowModal()

class LostDeviceDialog(wx.Dialog):
	def __init__(self, parent, title="Lost device"):
		super().__init__(parent, title=title)
		self.init_ui()

	def init_ui(self):
		self.main_sizer = wx.BoxSizer(wx.VERTICAL)
		msg_sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, label="Message: ")
		self.message = wx.TextCtrl(self)
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
			dialogs.error(self, "Error", "Pass codes must match")
			self.passcode.SetFocus()
			return
		self.Close()

class ChoiceDialog(wx.Dialog):
	"""Generic WX dialog with a list of items and set of buttons.
	Override the init_ui function in child classes to add additional UI controls.
	"""

	def __init__(self, parent, info, title="Info", flags=wx.CLOSE):
		self.info = info
		super().__init__(parent, title=title)
		self.init_ui()
		btn_sizer = self.CreateButtonSizer(flags)
		self.sizer.Add(btn_sizer)
		self.panel.SetSizerAndFit(self.sizer)
		self.Layout()

	def format_items(self):
		pass

	def init_ui(self):
		self.panel = wx.Panel(self)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		lst_sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self.panel, label="Info")
		items = [str(k)+": "+str(v) for (k, v) in self.format_items().items()]
		self.list = wx.ListBox(self.panel, choices=items)
		lst_sizer.Add(label, 0, wx.ALL, 5)
		lst_sizer.Add(self.list, 0, wx.ALL, 5)
		self.sizer.Add(lst_sizer, 0, wx.ALL, 5)

class DeviceInfoDialog(ChoiceDialog):
	def __init__(self, parent, info):
		title = info["name"]+" info"
		super().__init__(parent, info, title)
		self.bind_events()

	def init_ui(self):
		super().init_ui()
		actions_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.update = wx.Button(self.panel, label="&Update")
		actions_sizer.Add(self.update, 0, wx.ALL, 5)
		self.sizer.Add(actions_sizer, 0, wx.ALL, 5)

	def bind_events(self):
		self.Bind(wx.EVT_BUTTON, self.on_update, self.update)

	def update_items(self, focus=False):
		self.info.manager.refresh_client()
		items = [str(k)+": "+str(v) for (k, v) in self.format_items().items()]
		self.list.Freeze()
		self.list.Set(items)
		self.list.Thaw()
		if focus:
			self.list.SetFocus()

	def on_update(self, event):
		@utils.run_threaded
		def inner():
			wx.CallAfter(self.update_items, True)
		inner()

	def format_items(self):
		"""Formats device attributes into a readable list."""
		info = {}
		info["Name"] = self.info["name"]
		info["Status"] = self.info.get("deviceStatus", "unknown")
		model = self.info.get("deviceModel", "unknown")
		if model != "unknown":
			model += " (" + self.info.get("rawDeviceModel", "unknown") + ")"
		info["Model"] = model
		info["Display name"] = self.info.get("deviceDisplayName", "unknown")
		info["Battery status"] = self.info.get("batteryStatus", "unknown")
		info["Battery level"] = str(round(self.info.get("batteryLevel", 0)*100, 3)) + "%"
		# verify meaning of this
		info["UUID"] = self.info.get("baUUID", "unknown")
		info["Discovery ID"] = self.info.get("deviceDiscoveryId", "unknown")
		info["Low power mode"] = utils.enabled(self.info.get("lowPowerMode"))
		info["Activation lock"] = utils.enabled(self.info.get("activationLocked"))
		info["Passcode length"] = str(self.info.get("passcodeLength", "unknown"))
		info["Family share"] = utils.enabled(self.info.get("fmlyShare"))
		info["Lost mode"] = utils.enabled(self.info.get("lostModeEnabled"))
		info["Lost mode capable"] = utils.friendly_bool(self.info.get("lostModeCapable"))
		info["Whipe in progress"] = utils.friendly_bool(self.info.get("wipeInProgress"))
		#: WARNING! I don't actually know whether this means what I think it does
		info["Wipe after lock/failed pass code attempts"] = utils.enabled(self.info.get("canWipeAfterLock"))
		info["Location services"] = utils.enabled(self.info.get("locationEnabled"))
		info["Location capable"] = utils.friendly_bool(self.info.get("locationCapable"))
		info["Is locating"] = utils.friendly_bool(self.info.get("isLocating"))
		info["Device with you"] = utils.friendly_bool(self.info.get("deviceWithYou"))
		location = self.info.get("location")
		if location:
			info["Location inaccurate"] = utils.friendly_bool(location.get("isInaccurate"))
			info["Position type"] = location.get("positionType", "unknown")
			info["Latitude"] = str(location.get("latitude", 0))
			info["Longitude"] = str(location.get("longitude", 0))
			info["altitude"] = str(location.get("altitude", 0))
			info["Floor level"] = str(location.get("floorLevel", 0))
			info["Horizontal accuracy"] = str(location.get("horizontalAccuracy", 0))
			info["verticalAccuracy"] = str(location.get("verticalAccuracy", 0))
			ts = location.get("timeStamp")
			if ts:
				ts /= 1000
				info["Location updated"] = tformat.format_time(time.time() - ts) + " ago"
		else:
			dialogs.warning(self.panel, "Warning", "This device has no associated location information")
		return info

class Contacts(wx.Panel):
	def __init__(self, parent, *args, **kwargs):
		super().__init__(parent, *args, **kwargs)
		self.init_ui()
		self.bind_events()
		self.populate_contacts()
		self.order_filters = (
			"first,last",
			"last,first"
		)
		self.order_by.Set(self.order_filters)
		self.order_by.SetSelection(0)

	def bind_events(self):
		self.Bind(wx.EVT_BUTTON, self.on_refresh, self.update)

	def init_ui(self):
		self.main_sizer = wx.BoxSizer(wx.VERTICAL)
		lst_sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, label="Contacts: ")
		self.contacts_list = wx.ListBox(self)
		lst_sizer.Add(label, 0, wx.ALL, 5)
		lst_sizer.Add(self.contacts_list, 0, wx.ALL, 5)
		order_sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, label="Order by: ")
		self.order_by = wx.Choice(self)
		order_sizer.Add(label, 0, wx.ALL, 5)
		order_sizer.Add(self.order_by, 0, wx.ALL, 5)
		actions_sizer = wx.BoxSizer(wx.VERTICAL)
		self.update = wx.Button(self, label="&Refresh")
		actions_sizer.Add(self.update, 0, wx.ALL, 5)
		self.main_sizer.Add(lst_sizer)
		self.main_sizer.Add(order_sizer)
		self.main_sizer.Add(actions_sizer)
		self.SetSizerAndFit(self.main_sizer)
		self.Layout()

	def on_refresh(self, event):
		self.populate_contacts(True)

	def populate_contacts(self, focus_list=False):
		@utils.run_threaded
		def inner():
			contacts_service = icloud.service.contacts
			idx = self.order_by.GetSelection()
			if idx != wx.NOT_FOUND:
				contacts_service.order = self.order_filters[idx]
			self.contacts = contacts_service.all()
			items = self._format_contacts()
			wx.CallAfter(_set_items, items)
		def _set_items(items):
			self.contacts_list.Freeze()
			self.contacts_list.Clear()
			self.contacts_list.Set(items)
			self.contacts_list.Thaw()
			if self.contacts_list.GetCount() > 0:
				self.contacts_list.SetSelection(0)
			if focus_list:
				self.contacts_list.SetFocus()
		inner()

	def _format_contacts(self):
		contacts = []
		for contact in self.contacts:
			item = " ".join([contact.get("firstName", ""), contact.get("lastName", "")]).strip()
			contacts.append(item)
		return contacts
