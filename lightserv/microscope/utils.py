from .forms import  (LightSheetStatusForm, TwoPhotonStatusForm, ConfocalStatusForm,
					NewMicroscopeForm, NewLaserForm, NewChannelForm,NewDichroicForm,
					NewFilterForm, NewObjectiveForm, NewScannerForm)
from lightserv import db_microscope

def microscope_form_picker(microscope):
	""" Given a microscope string, return the corresponding form """
	if microscope == 'light sheet microscope':
		form = LightSheetStatusForm()
	elif microscope == 'two photon microscope':
		form = TwoPhotonStatusForm()
	elif microscope == 'confocal microscope':
		form = ConfocalStatusForm()
	return form


def data_entry_form_picker(data_entry_type):
	""" Given a microscope string, return the corresponding form """
	if data_entry_type == 'new_microscope':
		form = NewMicroscopeForm()
	elif data_entry_type == 'new_laser':
		form = NewLaserForm()
	elif data_entry_type == 'new_channel':
		form = NewChannelForm()
	elif data_entry_type == 'new_dichroic':
		form = NewDichroicForm()
	elif data_entry_type == 'new_filter':
		form = NewFilterForm()
	elif data_entry_type == 'new_objective':
		form = NewObjectiveForm()
	elif data_entry_type == 'new_scanner':
		form = NewScannerForm()
	else:
		pass
	return form

def data_entry_dbtable_picker(data_entry_type):
	""" Given a microscope string, return the corresponding form """
	if data_entry_type == 'new_microscope':
		dbtable = db_microscope.Microscope
	elif data_entry_type == 'new_laser':
		dbtable = db_microscope.Laser
	elif data_entry_type == 'new_channel':
		dbtable = db_microscope.Channel
	elif data_entry_type == 'new_dichroic':
		dbtable = db_microscope.DichroicMirrorType
	elif data_entry_type == 'new_filter':
		dbtable = db_microscope.FilterType
	elif data_entry_type == 'new_objective':
		dbtable = db_microscope.ObjectiveLensType
	elif data_entry_type == 'new_scanner':
		dbtable = db_microscope.ScannerType
	else:
		pass
	return dbtable