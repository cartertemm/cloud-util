import threading

def run_threaded(func):
	"""decorator to run a function in a separate thread"""
	def wrapper(*args, **kwargs):
		t=threading.Thread(target=func, args=args, daemon=True)
		t.start()
		return t
	return wrapper

# convenience functions for GUI text display
def friendly_bool(value, true="yes", false="no"):
	return (true if value else false)

def enabled(value):
	return friendly_bool(value, "enabled", "disabled")
