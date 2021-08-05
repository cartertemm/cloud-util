import wx
import threading

def dialog(parent, caption, message, style=0, *args, **kwargs):
	style |= wx.CENTRE
	dlg = wx.MessageDialog(parent, message, caption, style, **kwargs)
	# hack: ensure UI events are always confined to the main thread
	evt = threading.Event()
	def inner():
		try:
			inner.response = dlg.ShowModal()
		finally:
			evt.set()
			dlg.Destroy()
	if threading.current_thread() != threading.main_thread():
		print("running from another thread")
		wx.CallAfter(inner)
	else:
		inner()
	evt.wait()
	return inner.response

def information(parent, caption, message):
	return dialog(parent, caption, message, style=wx.OK|wx.ICON_INFORMATION)

def error(parent, caption, message):
	return dialog(parent, caption, message, style=wx.OK|wx.ICON_ERROR)

def warning(parent, caption, message):
	return dialog(parent, caption, message, style=wx.OK|wx.ICON_WARNING)

def question(parent, caption, message, warning=False, cancelable=False):
	style=wx.YES_NO
	if warning:
		style |= wx.ICON_WARNING
	else:
		style |= wx.ICON_QUESTION
	if cancelable:
		style |= wx.CANCEL
	return dialog(parent, caption, message, style=style)
