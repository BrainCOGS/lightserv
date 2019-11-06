from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup)
# from flask_login import current_user, login_required
# from lightserv import db_lightsheet
# from lightserv.models import Experiment
from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
									  iDiscoAbbreviatedRatForm, uDiscoForm,  iDiscoEduForm )
from lightserv.tables import ClearingTable,IdiscoPlusTable
from lightserv import db_lightsheet
from .utils import (determine_clearing_form, add_clearing_calendar_entry,
				   determine_clearing_dbtable, determine_clearing_table) 
from lightserv.main.utils import logged_in, logged_in_as_clearer
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

@clearing.route("/clearing/clearing_entry/<username>/<experiment_name>/<sample_name>/<clearing_protocol>/",
	methods=['GET','POST'])
@logged_in_as_clearer
def clearing_entry(username,experiment_name,sample_name,clearing_protocol): 
	# print(username,experiment_name,sample_name,clearing_protocol)
	sample_contents = db_lightsheet.Sample() & f'experiment_name="{experiment_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' & f'clearing_protocol="{clearing_protocol}"'								
	# print(sample_contents)
	if not sample_contents:
		flash(f'Experiment must exist for experiment_name={experiment_name}, sample_name={sample_name} with \
			clearing_protocol="{clearing_protocol}" before clearing can be done. \
			Please submit a new request for this experiment first. ','danger')
		return redirect(url_for('experiments.new_exp'))
	dj.Table._update(sample_contents,'clearing_progress','in progress')
	clearing_table = ClearingTable(sample_contents)
	
	dbTable = determine_clearing_dbtable(clearing_protocol)
	''' Check to see if there is an entry in the db yet. If not create one with all NULL values.
	They will get updated as the user fills out the form '''
	clearing_contents = dbTable() & f'experiment_name="{experiment_name}"' & \
	 	f'username="{username}"' & f'sample_name="{sample_name}"'
	''' If there are contents and the form is blank, then that means the user is accessing the form 
	to edit it from a previous session and we should pre-load the current contents of the db '''
	if clearing_contents and (not request.form):
		print("We should autofill")
		fill_dict = {'exp_notes':'some_notes'}
		form = determine_clearing_form(clearing_protocol,existing_form=request.form)
		for key,val in list(clearing_contents.fetch1().items()):
			if key in form._fields.keys():
				form[key].data = val	
	else:
		form = determine_clearing_form(clearing_protocol,existing_form=request.form)

	# print(clearing_contents)
	# print(request.form)
	
	# print(clearing_contents)
	if not clearing_contents:
		sample_username = sample_contents.fetch1('username')
		insert_dict = {'experiment_name':experiment_name,
						'username':sample_username,'sample_name':sample_name}
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
						base_entry_dict = {'experiment_name':experiment_name,
										   'username':clearing_contents_dict['username'],
						                   'sample_name':clearing_contents_dict['sample_name']}
						clearing_entry_dict = {key:form_data_dict[key] for key in form_data_dict.keys() \
							if key in clearing_contents_dict.keys()}
						for k in base_entry_dict:
							clearing_entry_dict[k] = base_entry_dict[k]
						clearing_contents.delete_quick()
						dbTable().insert1(clearing_entry_dict)	
						dj.Table._update(sample_contents,'clearing_progress','complete')						
						flash("Clearing form was successfully completed.",'success')
						return redirect(url_for('main.home'))
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
				logger.debug(error)
			column_name = list(form.errors.keys())[0]
	else:
		column_name = None

	''' Populate form with current database contents '''
	# logger.debug("Current non-null contents of the database:")
	# clearing_contents = dbTable() & f'experiment_id={experiment_id}'
	# clearing_contents_dict = clearing_contents.fetch1()
	# form_fieldnames = form._fields.keys()
	# for key in clearing_contents_dict.keys():
	# 	val = clearing_contents_dict[key]
	# 	if key in form_fieldnames and val:
	# 		logger.debug(f"key={key},val={val}")
	# 		# logger.debug(val)
	# 		form[key].data = val
	return render_template('clearing/clearing_entry.html',clearing_protocol=clearing_protocol,
		form=form,clearing_table=clearing_table,experiment_name=experiment_name,
		column_name=column_name)

@clearing.route("/clearing/clearing_table/<username>/<experiment_name>/<sample_name>/<clearing_protocol>/",methods=['GET'])
@logged_in_as_clearer
def clearing_table(username,experiment_name,sample_name,clearing_protocol): 
	sample_contents = db_lightsheet.Sample() & f'experiment_name="{experiment_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' & f'clearing_protocol="{clearing_protocol}"'		
	if not sample_contents:
		flash(f"No sample contents for experiment_name={experiment_name}, sample_name={sample_name}\
			   with clearing_protocol={clearing_protocol} for username={username}",'danger')
		return redirect(url_for('main.home'))
	 
	dbTable = determine_clearing_dbtable(clearing_protocol)
	db_contents = dbTable() & f'experiment_name="{experiment_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"'
	table = determine_clearing_table(clearing_protocol)(db_contents)
	table.table_id = 'vertical'

	return render_template('clearing/clearing_table.html',clearing_contents=db_contents,table=table)
