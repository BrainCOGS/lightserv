from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
									  uDiscoForm, iDiscoPlusForm, iDiscoEduForm )

def determine_clearing_form(clearing_protocol,existing_form):
	if clearing_protocol == 'iDISCO+': 
		form = iDiscoPlusForm(existing_form)
	elif clearing_protocol == 'iDISCO abbreviated clearing':
		form = iDiscoAbbreviatedForm(existing_form)
	elif clearing_protocol == 'uDISCO':
		form = uDiscoForm(existing_form)
	elif clearing_protocol == 'iDISCO+_immuno':
		form = iDiscoPlusImmunoForm(existing_form)
	elif clearing_protocol == 'iDISCO_EdU':
		form = iDiscoEduForm()
	return form
