from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
									  uDiscoForm, iDiscoPlusForm, iDiscoEduForm )

def determine_clearing_form(clearing_protocol):
	if clearing_protocol == 'iDISCO+': 
		form = iDiscoPlusForm()
	elif clearing_protocol == 'iDISCO abbreviated clearing':
		form = iDiscoAbbreviatedForm()
	elif clearing_protocol == 'uDISCO':
		form = uDiscoForm()
	elif clearing_protocol == 'iDISCO+_immuno':
		form = iDiscoPlusImmunoForm()
	elif clearing_protocol == 'iDISCO_EdU':
		form = iDiscoEduForm()
	return form
