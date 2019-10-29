from .forms import  (LightSheetStatusForm, TwoPhotonStatusForm, ConfocalStatusForm,
					NewMicroscopeForm, NewLaserForm, NewChannelForm)
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
	else:
		pass
	return dbtable