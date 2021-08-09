import requests

def geocode(latitude, longitude, **kwargs):
	"""Reverse geocode coordinates using OSM data via the Nominatim API.
	API docs: https://nominatim.org/release-docs/develop/api/Reverse/
	"""
	kwargs["format"] = kwargs.get("format", "json")
	kwargs["addressdetails"] = kwargs.get("addressdetails", 1)
	kwargs["extratags"] = kwargs.get("extratags", 0)
	kwargs["namedetails"] = kwargs.get("namedetails", 0)
	r = requests.get("https://nominatim.openstreetmap.org/reverse", {"lat": latitude, "lon": longitude, **kwargs})
	r.raise_for_status()
	return r.json()
