from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup)
# from flask_login import current_user, login_required
# from lightserv import db
# from lightserv.models import Experiment
from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
									  iDiscoAbbreviatedRatForm, uDiscoForm,  iDiscoEduForm )
from lightserv.tables import ClearingTable,IdiscoPlusTable
from lightserv import db
from .utils import (determine_clearing_form, add_clearing_calendar_entry,
				   determine_clearing_dbtable, determine_clearing_table) 
from lightserv.main.utils import logged_in
import numpy as np
import datajoint as dj
import re
import datetime

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/clearing_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

clearing = Blueprint('clearing',__name__)

@clearing.route("/clearing/clearing_entry/<clearing_protocol>/<experiment_id>",methods=['GET','POST'])
@logged_in
def clearing_entry(clearing_protocol,experiment_id): 
	exp_contents = db.Experiment() & f'experiment_id={experiment_id}' & f'clearing_protocol="{clearing_protocol}"'
	if not exp_contents:
		flash(f'Experiment must exist for experiment_id={experiment_id} with \
			clearing_protocol="{clearing_protocol}" before clearing can be done. \
			Please submit a new request for this experiment first. ','danger')
		return redirect(url_for('experiments.new_exp'))

	clearing_table = ClearingTable(exp_contents)
	form = determine_clearing_form(clearing_protocol,existing_form=request.form)
	
	dbTable = determine_clearing_dbtable(clearing_protocol)
	''' Check to see if there is an entry in the db yet. If not create one with all NULL values.
	They will get updated as the user fills out the form '''
	clearing_contents = dbTable() & f'experiment_id="{experiment_id}"'
	if not clearing_contents:
		experiment_username = exp_contents.fetch1('username')
		insert_dict = {'experiment_id':experiment_id,
						'username':experiment_username,'clearer':session['user']}
		dbTable().insert1(insert_dict)
		logger.info("Created clearing database entry")
	

	''' Handle user's post requests '''
	if request.method == 'POST':
		logger.debug("Post request")
		if form.validate_on_submit():
			logger.debug("Form validated")
			submit_keys = [x for x in form._fields.keys() if 'submit' in x]
			for key in submit_keys:
				if form[key].data:
					if key == 'submit': # The final submit button
						logger.debug("Submitting entire form")
						''' Get data from the form and submit it to the database '''
						form_data_dict = form.data
						clearing_contents_dict = clearing_contents.fetch1()
						''' The fields that need to go in the database that are not in the form '''
						base_entry_dict = {'experiment_id':experiment_id,
										   'username':clearing_contents_dict['username'],
						                   'clearer':clearing_contents_dict['clearer']}
						clearing_entry_dict = {key:form_data_dict[key] for key in form_data_dict.keys() if key in clearing_contents_dict.keys()}
						for k in base_entry_dict:
							clearing_entry_dict[k] = base_entry_dict[k]
						clearing_contents.delete_quick()
						dbTable().insert1(clearing_entry_dict)	
						dj.Table._update(exp_contents,'clearing_progress','complete')						
						flash("Clearing form was successfully completed.",'success')
						return redirect(url_for('clearing.clearing_table',experiment_id=experiment_id))
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
						dbTable().insert1(clearing_entry_dict)
						logger.debug(f"Entered into database: {column_name}:{form[column_name].data}")
						this_index = submit_keys.index(key)
						next_index = this_index + 1 if 'notes' in column_name else this_index+2
						column_name = submit_keys[next_index].split('_submit')[0]
						break
			else:
				column_name=None
		else:
			''' Find the first form field where there was an error and set the column_name to it 
			so the focus is set there upon reload of page '''
			logger.debug(form.errors)
			for error in form['time_pbs_wash1'].errors:
				print(error)
			column_name = list(form.errors.keys())[0]
	else:
		column_name = None

	''' Populate form with current database contents '''
	logger.debug("Current non-null contents of the database:")
	clearing_contents = dbTable() & f'experiment_id={experiment_id}'
	clearing_contents_dict = clearing_contents.fetch1()
	form_fieldnames = form._fields.keys()
	for key in clearing_contents_dict.keys():
		val = clearing_contents_dict[key]
		if key in form_fieldnames and val:
			logger.debug(f"key={key},val={val}")
			# logger.debug(val)
			form[key].data = val
	return render_template('clearing/clearing_entry.html',clearing_protocol=clearing_protocol,
		form=form,clearing_table=clearing_table,experiment_id=experiment_id,
		column_name=column_name)

@clearing.route("/clearing/clearing_table/<experiment_id>",methods=['GET'])
@logged_in
def clearing_table(experiment_id): 
	exp_contents = db.Experiment() & f'experiment_id="{experiment_id}"'
	assert exp_contents, f"experiment_id={experiment_id} does not exist.\
						   It must exist for clearing for this experiment to exist."
	clearing_protocol = exp_contents.fetch1('clearing_protocol')

	dbTable = determine_clearing_dbtable(clearing_protocol)

	db_contents = dbTable() & f'experiment_id = {experiment_id}'

	table = determine_clearing_table(clearing_protocol)(db_contents)



	return render_template('clearing/clearing_table.html',table=table)
