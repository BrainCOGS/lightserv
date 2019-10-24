from .forms import  LightSheetStatusForm, TwoPhotonStatusForm, ConfocalStatusForm
def microscope_form_picker(microscope):
	""" Given a microscope string, return the corresponding form """
	if microscope == 'light sheet microscope':
		form = LightSheetStatusForm()
	elif microscope == 'two photon microscope':
		form = TwoPhotonStatusForm()
	elif microscope == 'confocal microscope':
		form = ConfocalStatusForm()
	return form