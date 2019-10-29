from .forms import  (LightSheetStatusForm, TwoPhotonStatusForm, ConfocalStatusForm,
					NewMicroscopeForm)

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
	else:
		pass
	return form