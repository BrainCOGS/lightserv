from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup)
from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
									  iDiscoAbbreviatedRatForm, uDiscoForm,  iDiscoEduForm )
from lightserv.tables import ClearingTable,IdiscoPlusTable, dynamic_clearing_management_table
from lightserv import db_lightsheet
from .utils import (determine_clearing_form, add_clearing_calendar_entry,
				   determine_clearing_dbtable, determine_clearing_table) 
from lightserv.main.utils import logged_in, logged_in_as_clearer, logged_in_as_clearing_manager
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

@clearing.route("/clearing/clearing_manager",methods=['GET','POST'])
@logged_in_as_clearing_manager
def clearing_manager():
	sort = request.args.get('sort', 'datetime_submitted') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	sample_contents = db_lightsheet.Sample()
	exp_contents = db_lightsheet.Experiment()
	combined_contents = dj.U('clearing_protocol', 'experiment_name').aggr(sample_contents, 
        clearer='clearer',clearing_progress='clearing_progress',
        sample_name='min(sample_name)',number_in_batch='count(*)') * exp_contents	
	all_contents_unique_clearing_protocol = combined_contents.proj('sample_name','number_in_batch','sample_prefix',
		'clearing_protocol','species',
		'clearer','clearing_progress','clearing_protocol',
		datetime_submitted='TIMESTAMP(date_submitted,time_submitted)') # will pick up the primary keys by default

	''' First get all entities that are currently being cleared '''
	contents_being_cleared = all_contents_unique_clearing_protocol & 'clearing_progress="in progress"'
	being_cleared_table_id = 'horizontal_being_cleared_table'
	table_being_cleared = dynamic_clearing_management_table(contents_being_cleared,
		table_id=being_cleared_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Next get all entities that are ready to be cleared '''
	contents_ready_to_clear = all_contents_unique_clearing_protocol & 'clearing_progress="incomplete"' 
	ready_to_clear_table_id = 'horizontal_ready_to_clear_table'
	table_ready_to_clear = dynamic_clearing_management_table(contents_ready_to_clear,
		table_id=ready_to_clear_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Now get all entities on deck (currently being cleared) '''
	''' Finally get all entities that have already been imaged '''
	contents_already_cleared = all_contents_unique_clearing_protocol & 'clearing_progress="complete"'
	already_cleared_table_id = 'horizontal_already_cleared_table'
	table_already_cleared = dynamic_clearing_management_table(contents_already_cleared,
		table_id=already_cleared_table_id,
		sort_by=sort,sort_reverse=reverse)
	
	return render_template('clearing/clearing_management.html',table_being_cleared=table_being_cleared,
		table_ready_to_clear=table_ready_to_clear,
		table_already_cleared=table_already_cleared)

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
			clearing_progress = sample_contents.fetch1('clearing_progress')
			if clearing_progress == 'complete':
				return redirect(url_for('clearing.clearing_entry',username=username,
			experiment_name=experiment_name,sample_name=sample_name,clearing_protocol=clearing_protocol))
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
						return redirect(url_for('experiments.exp',username=username,
							experiment_name=experiment_name))
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
			else: # if none of the submit keys were found
				column_name=None
		else: # form not validated
			''' Find the first form field where there was an error and set the column_name to it 
			so the focus is set there upon reload of page '''
			logger.debug(form.errors)
			for error in form['time_pbs_wash1'].errors:
				logger.debug(error)
			column_name = list(form.errors.keys())[0]
	else: # not a post request
		column_name = None

	clearing_progress = sample_contents.fetch1('clearing_progress')
	if clearing_progress == 'complete':
		flash("clearing is already complete for this sample. "
			"This page is read only and hitting any of the buttons will not update the clearing log",'warning')
	else:
		dj.Table._update(sample_contents,'clearing_progress','in progress')

	return render_template('clearing/clearing_entry.html',clearing_protocol=clearing_protocol,
		form=form,clearing_table=clearing_table,username=username,experiment_name=experiment_name,
		sample_name=sample_name,column_name=column_name)

@clearing.route("/clearing/clearing_table/<username>/<experiment_name>/<sample_name>/<clearing_protocol>/",methods=['GET'])
@logged_in_as_clearer
def clearing_table(username,experiment_name,sample_name,clearing_protocol): 
	sample_contents = db_lightsheet.Sample() & f'experiment_name="{experiment_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' & f'clearing_protocol="{clearing_protocol}"'		
	if not sample_contents:
		flash(f"No sample contents for experiment_name={experiment_name}, sample_name={sample_name}\
			   with clearing_protocol={clearing_protocol} for username={username}",'danger')
		return redirect(url_for('main.home'))
	overview_table = ClearingTable(sample_contents)
	clearing_table.table_id = 'horizontal'
	dbTable = determine_clearing_dbtable(clearing_protocol)
	db_contents = dbTable() & f'experiment_name="{experiment_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"'
	table = determine_clearing_table(clearing_protocol)(db_contents)
	table.table_id = 'vertical'

	return render_template('clearing/clearing_table.html',overview_table=overview_table,
		clearing_contents=db_contents,table=table)
