from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup)
# from flask_login import current_user, login_required
# from lightserv import db
# from lightserv.models import Experiment
from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
									  uDiscoForm, iDiscoPlusForm, iDiscoEduForm )
from lightserv.tables import ClearingTable,IdiscoPlusTable
from lightserv import db
from .utils import (determine_clearing_form, determine_clearing_route,
					add_clearing_calendar_entry)# import cloudvolume
import numpy as np
import datajoint as dj
import re

clearing = Blueprint('clearing',__name__)

@clearing.route("/clearingfinder/<experiment_id>",methods=['GET'])
def clearing_finder(experiment_id):
	""" Given an experiment_id redirect to the correct 
	clearing protocol route """
	exp_contents = db.Experiment() & f'experiment_id="{experiment_id}"'

	clearing_protocol = exp_contents.fetch1('clearing_protocol')
	return determine_clearing_route(clearing_protocol,experiment_id)

@clearing.route("/clearing/idiscoplus_entry/<experiment_id>",methods=['GET','POST'])
def iDISCOplus_entry(experiment_id): 
	exp_contents = db.Experiment() & f'experiment_id="{experiment_id}"'
	assert exp_contents, f"experiment_id={experiment_id} does not exist.\
						   It must exist before the clearing for this experiment can be done"
	clearing_table = ClearingTable(exp_contents)
	clearing_protocol = exp_contents.fetch1('clearing_protocol')
	form = determine_clearing_form(clearing_protocol,existing_form=request.form)

	''' Check to see if there is an entry in the db yet. If not create one with all NULL values.
	They will get updated as the user fills out the form '''
	clearing_contents = db.IdiscoPlusClearing() & f'experiment_id="{experiment_id}"'
	if not clearing_contents:
		experiment_username = exp_contents.fetch1('username')
		insert_dict = {'experiment_id':experiment_id,
						'username':experiment_username,'clearer':session['user']}
		db.IdiscoPlusClearing().insert1(insert_dict)
		print("Created clearing database entry")

	''' Handle user's post requests '''
	if request.method == 'POST':
		submit_keys = [x for x in form._fields.keys() if 'submit' in x]
		for key in submit_keys:
			if form[key].data:
				if key == 'submit': # The final submit button
					print("Submitting entire form")
				elif re.search("^(?!perfusion).*_date_submit$",key) != None:
					column_name = key.split('_submit')[0]
					date = form[column_name].data
					if date == None:
						flash("Please enter a valid date to push to the Clearing Calendar",'danger')
						break
					else:
						username = clearing_contents.fetch1('username')
						clearing_step = key.split('_')[0]
						summary = f'{username} {clearing_protocol} {clearing_step}'
						print(summary)
						add_clearing_calendar_entry(date=date,
						summary=summary)
						flash("Event added to Clearing Calendar. Check the calendar.",'success')
					break
				else: 
					''' Update the row '''
					column_name = key.split('_submit')[0]
					clearing_entry_dict = clearing_contents.fetch1() # returns as a dict
					clearing_entry_dict[column_name]=form[column_name].data
					clearing_contents.delete_quick()
					db.IdiscoPlusClearing().insert1(clearing_entry_dict)
					print(f"updated row for value: {column_name}")
					break
		else:
			column_name=None

		# print(f"Going to render {column_name}")
		# return render_template('clearing/idiscoplus.html',form=form,
		# 	clearing_table=clearing_table,experiment_id=experiment_id,column_name=column_name)
	else:
		column_name = None
	# print(f"Going to render {column_name}")
	return render_template('clearing/idiscoplus.html',form=form,
		clearing_table=clearing_table,experiment_id=experiment_id,
		column_name=column_name)


@clearing.route("/clearing/clearing_table/<experiment_id>",methods=['GET'])
def clearing_table(experiment_id): 
	exp_contents = db.Experiment() & f'experiment_id="{experiment_id}"'
	assert exp_contents, f"experiment_id={experiment_id} does not exist.\
						   It must exist for clearing for this experiment to exist."
	clearing_protocol = exp_contents.fetch1('clearing_protocol')

	if clearing_protocol == 'iDISCO+_immuno':
		clearing_contents = db.IdiscoPlusClearing() & f'experiment_id="{experiment_id}"'
		table = IdiscoPlusTable(clearing_contents) 
	else:
		table = "Need to work on this" 


	return render_template('clearing/clearing_table.html',table=table)
