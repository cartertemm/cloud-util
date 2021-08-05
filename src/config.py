import logging
from configobj import ConfigObj, ConfigObjError, flatten_errors
from validate import Validator
import app
from configspec import configspec

log = logging.getLogger("config_handler")
config = None


def load(path, quiet=False, parent=None):
	global config
	if not quiet:
		import dialogs
	# seek back to the beginning of the spec for every read
	configspec.seek(0)
	try:
		config = ConfigObj(
			infile=path, configspec=configspec, encoding="UTF8", create_empty=True
		)
	except ConfigObjError as exc:
		log.exception("While loading the configuration file")
		if not quiet:
			dialogs.error(parent, "Error", "An error occurred while loading the configuration.\n"+str(exc))
			app.exit()
		return
	validator = Validator()
	result = config.validate(validator, copy=True)
	if result != True:
		errors = report_validation_errors(config, result)
		errors = "\n".join(errors)
		e = "error" + ("" if len(errors) == 1 else "s")
		log.error(e+ " were encountered while validating the configuration.\n" + errors)
		if not quiet:
			dialogs.error(parent, "Error", e+" were encountered while trying to load the configuration.\n"+errors)


def report_validation_errors(config, validation_result):
	errors = []
	for (section_list, key, _) in flatten_errors(config, validation_result):
		if key:
			errors.append(
				'"%s" key in section "%s" failed validation'
				% (key, ", ".join(section_list))
			)
		else:
			errors.append('missing required section "%s"' % (", ".join(section_list)))
	return errors
