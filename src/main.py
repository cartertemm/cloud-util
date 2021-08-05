import app
import config
import gui
import icloud


if __name__ == "__main__":
	app.init()
	dlg = gui.LoginDialog(None)
	dlg.ShowModal()
	dlg.Destroy()
	if dlg and icloud.service:
		frame = gui.MainFrame(None)
		app.app.SetTopWindow(frame)
		frame.Show()
		app.app.MainLoop()