from flask import redirect, url_for
from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
									  uDiscoForm, iDiscoPlusForm, iDiscoEduForm )
from lightserv.tables import (IdiscoPlusTable)

def determine_clearing_route(clearing_protocol,experiment_id):

	if clearing_protocol == 'iDISCO+_immuno':
		return redirect(url_for('clearing.iDISCOplus_entry',experiment_id=experiment_id))
	else:
		return redirect(url_for('main.home'))

def determine_clearing_table(clearing_protocol):

	if clearing_protocol == 'iDISCO+_immuno':
		return IdiscoPlusTable
	else:
		return None # Update!

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
		form = iDiscoEduForm(existing_form)
	return form
