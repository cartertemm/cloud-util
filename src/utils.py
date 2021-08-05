import threading

def run_threaded(func):
	"""decorator to run a function in a separate thread"""
	def wrapper(*args, **kwargs):
		t=threading.Thread(target=func, args=args, daemon=True)
		t.start()
		return t
	return wrapper
