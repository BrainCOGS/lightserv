from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup,current_app)
from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
		  iDiscoAbbreviatedRatForm, uDiscoForm,  iDiscoEduForm,
		  NewAntibodyForm, EditAntibodyForm )
from lightserv.clearing.tables import (ClearingTable,IdiscoPlusTable,
	dynamic_clearing_management_table,SamplesTable,
	AntibodyOverviewTable,AntibodyHistoryTable,
	AntibodyHistorySingleEntryTable)
from lightserv import db_lightsheet, smtp_connect
from .utils import (determine_clearing_form, add_clearing_calendar_entry,
				   determine_clearing_dbtable, determine_clearing_table) 
from lightserv.main.utils import (logged_in, logged_in_as_clearer,
	 logged_in_as_clearing_manager, log_http_requests,
	 table_sorter)
from lightserv.main.tasks import send_email
import numpy as np
import datajoint as dj
import re, os, datetime
import secrets
from functools import partial

import logging
from werkzeug.routing import BaseConverter

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
@logged_in
@log_http_requests
def clearing_manager():
	""" A user interface for handling past, present and future clearing batches.
	Can be used by a clearing admin to handle all clearing batches (except those claimed
	by the researcher) or by a researcher to handle their own clearing batches if they claimed 
	them in their request form """
	sort = request.args.get('sort', 'datetime_submitted') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'desc') == 'desc')
	current_user = session['user']
	logger.info(f"{current_user} accessed clearing manager")

	clearing_admins = current_app.config['CLEARING_ADMINS']
	if current_user not in clearing_admins:
		clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'clearer="{current_user}"'
	else:
		clearing_batch_contents = db_lightsheet.Request.ClearingBatch()
	request_contents = db_lightsheet.Request()
	combined_contents = (clearing_batch_contents * request_contents).proj(
		'number_in_batch','expected_handoff_date',
		'clearing_protocol','species',
		'clearer','clearing_progress','clearing_protocol','antibody1','antibody2',
		datetime_submitted='TIMESTAMP(date_submitted,time_submitted)')
	''' First get all entities that are currently being cleared '''
	contents_being_cleared = combined_contents & 'clearing_progress="in progress"'
	being_cleared_table_id = 'horizontal_being_cleared_table'
	table_being_cleared = dynamic_clearing_management_table(contents_being_cleared,
		table_id=being_cleared_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Next get all entities that are ready to be cleared '''
	contents_ready_to_clear = combined_contents & 'clearing_progress="incomplete"' 
	ready_to_clear_table_id = 'horizontal_ready_to_clear_table'
	table_ready_to_clear = dynamic_clearing_management_table(contents_ready_to_clear,
		table_id=ready_to_clear_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Now get all entities on deck (currently being cleared) '''
	''' Finally get all entities that have already been imaged '''

	contents_already_cleared = (combined_contents & 'clearing_progress="complete"').fetch(
		as_dict=True,order_by='datetime_submitted DESC')
	already_cleared_table_id = 'horizontal_already_cleared_table'
	table_already_cleared = dynamic_clearing_management_table(contents_already_cleared,
		table_id=already_cleared_table_id,
		sort_by=sort,sort_reverse=reverse)
	
	return render_template('clearing/clearing_management.html',table_being_cleared=table_being_cleared,
		table_ready_to_clear=table_ready_to_clear,
		table_already_cleared=table_already_cleared)

@clearing.route("/clearing/clearing_entry/<username>/<request_name>/<clearing_batch_number>",
	methods=['GET','POST'])
@logged_in
@logged_in_as_clearer
@log_http_requests
def clearing_entry(username,request_name,clearing_batch_number): 
	current_user = session['user']
	logger.debug(f'{current_user} accessed clearing entry form')
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'request_name="{request_name}"' & \
			f'username="{username}"' & \
			f'clearing_batch_number={clearing_batch_number}'				
	clearing_protocol,antibody1,antibody2 = clearing_batch_contents.fetch1(
		'clearing_protocol','antibody1','antibody2')
	clearing_table = ClearingTable(clearing_batch_contents)
	""" Make the samples table to sit directly underneath the clearing table """
	sample_keys = {'username':username,'request_name':request_name,
							   'clearing_protocol':clearing_protocol,'antibody1':antibody1,
							   'antibody2':antibody2,'clearing_batch_number':clearing_batch_number}
	samples_this_clearing_batch = (db_lightsheet.Request.Sample() & sample_keys).fetch('sample_name')
	samples_str = ', '.join(sample for sample in samples_this_clearing_batch)
	samples_contents = [dict(samples=samples_str)]
	samples_table = SamplesTable(samples_contents)
	clearing_dbTable = determine_clearing_dbtable(clearing_protocol)
	''' Check to see if there is an entry in the db yet. If not create one with all NULL values.
	They will get updated as the user fills out the form '''
	clearing_contents = clearing_dbTable() & f'request_name="{request_name}"' & \
		f'username="{username}"' & f'clearing_protocol="{clearing_protocol}"' & \
		f'antibody1="{antibody1}"' & f'antibody2="{antibody2}"'	& \
		f'clearing_batch_number={clearing_batch_number}'	

	''' If there are contents and the form is blank, then that means the user is accessing the form 
	to edit it from a previous session and we should pre-load the current contents of the db '''
	if len(clearing_contents) > 0 and (not request.form):
		form = determine_clearing_form(clearing_protocol,existing_form=request.form)
		for key,val in list(clearing_contents.fetch1().items()):
			if key in form._fields.keys():
				form[key].data = val	
	else:
		form = determine_clearing_form(clearing_protocol,existing_form=request.form)

	''' If there are not clearing contents then this is the first time the form 
	has been opened and the clearing is just getting started. '''
	if not clearing_contents:

		insert_dict = {'username':username,'request_name':request_name,
					   'clearing_protocol':clearing_protocol,'antibody1':antibody1,
					   'antibody2':antibody2,'clearing_batch_number':clearing_batch_number}
		clearing_dbTable().insert1(insert_dict)
		logger.info("Created clearing database entry")
	
	''' Handle user's post requests '''
	if request.method == 'POST':
		logger.debug("Post request")
		if form.validate_on_submit():
			logger.debug("Form validated")
			clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
			if clearing_progress == 'complete':
				return redirect(url_for('clearing.clearing_entry',username=username,
			request_name=request_name,clearing_batch_number=clearing_batch_number))
			submit_keys = [x for x in form._fields.keys() if 'submit' in x]
	
			for key in submit_keys:
				if form[key].data:
					if key == 'submit': # The final submit button
						logger.debug("Submitting entire form")
						''' Get data from the form and submit it to the database
						for all entries in the batch (same request,username,clearing_protocol,antibodies)'''
						connection = clearing_dbTable.connection
						with connection.transaction:
							form_data_dict = form.data
							clearing_contents_dict = clearing_contents.fetch1()
							base_insert_dict = {'username':username,'request_name':request_name,
							   'clearing_protocol':clearing_protocol,'antibody1':antibody1,
							   'antibody2':antibody2,'clearing_batch_number':clearing_batch_number} # the columns not in the form
							clearing_insert_dict = {key:form_data_dict[key] for key in form_data_dict.keys() \
									if key in clearing_contents_dict.keys()} # the columns from the form

							for k in base_insert_dict.keys():
								clearing_insert_dict[k] = base_insert_dict[k]

							if clearing_protocol == 'iDISCO+_immuno':
								''' update the antibody1_lot and antibody2_lot fields based on the form data '''
								logger.debug("Updating antibody lot info")
								clearing_batch_update_dict = clearing_batch_contents.fetch1()
								clearing_batch_update_dict['antibody1_lot'] = form_data_dict['antibody1_lot']
								clearing_batch_update_dict['antibody2_lot'] = form_data_dict['antibody2_lot']
								db_lightsheet.Request.ClearingBatch().update1(clearing_batch_update_dict)
								logger.debug("Updated antibody lot info")
							''' update the clearing progress to "complete" for this sample entry '''
							clearing_batch_update_dict = clearing_batch_contents.fetch1()
							clearing_batch_update_dict['clearing_progress'] = 'complete'
							db_lightsheet.Request.ClearingBatch().update1(clearing_batch_update_dict)

							''' Update the entries by inserting with replace=True'''
							clearing_dbTable().insert1(clearing_insert_dict,replace=True)	
							flash("Clearing form was successfully completed.",'success')
							""" Send email to user and imaging managers """
							
							""" Figure out all of the samples that are in this batch """
							
							# logger.debug(samples_this_clearing_batch)	
							hosturl = os.environ['HOSTURL']
							imaging_manager_url = f'https://{hosturl}' + url_for('imaging.imaging_manager')
							
							subject = 'Lightserv automated email: Clearing complete'
							message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
								'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
								'The clearing for your batch:\n'
								f'request_name: {request_name}\n'
								f'clearing_protocol: "{clearing_protocol}\n'
								f'antibody1: {antibody1}\n'
								f'antibody2: {antibody2}\n'
								f'clearing_batch_number: {clearing_batch_number}\n'
								f'Samples: {samples_str}\n\n'
								f'is now complete. Check the imaging management GUI: {imaging_manager_url}\n'
								'to see if you designated yourself as the imager for any of these samples\n\n'
								'Otherwise, the imaging will be handled by the Core Facility, and you will receive '
								'emails when the imaging for each of your samples is complete.\n\n'
								'Thanks,\nThe Histology and Brain Registration Core Facility.')
							request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
							correspondence_email = request_contents.fetch1('correspondence_email')
							recipients = [correspondence_email]

							if not os.environ['FLASK_MODE'] == 'TEST':
								send_email.delay(subject=subject,body=message_body,recipients=recipients) # pragma: no cover - used to exclude this line from calculating test coverage

							""" Now check to see if we need to send an email to the imaging managers """
							first_sample_name = samples_this_clearing_batch[0]
							imaging_request_keys = {'username':username,'request_name':request_name,
							   'sample_name':first_sample_name,'imaging_request_number':1}
							imager_this_batch = (db_lightsheet.Request.ImagingRequest & \
								imaging_request_keys).fetch1('imager')
							if not imager_this_batch: 
								subject = 'Lightserv automated email: Sample(s) ready for imaging'

								hosturl = os.environ['HOSTURL']
								imaging_manager_link = f'https://{hosturl}' + url_for('imaging.imaging_manager')
								message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
									'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
									'A request:\n'
									f'username: "{username}"\n'
									f'request_name: "{request_name}"\n'
									'has samples that are ready to be imaged.\n\n'
									f'Information about each sample can be viewed '
									f'at the imaging management page: {imaging_manager_link}\n\n'
									'Thanks,\nThe Histology and Brain Registration Core Facility.')
								recipients = [x + '@princeton.edu' for x in current_app.config['IMAGING_ADMINS']]
								if not os.environ['FLASK_MODE'] == 'TEST':
									send_email.delay(subject=subject,body=message_body,recipients=recipients)
							return redirect(url_for('clearing.clearing_manager'))

					elif re.search("^(?!perfusion).*_date_submit$",key) != None: # one of the calendar date submit buttons
						logger.debug("Calendar date submit button pressed")
						column_name = key.split('_submit')[0]
						date = form[column_name].data
						if date == None:
							logger.debug("Invalid date")
							flash("Please enter a valid date to push to the Clearing Calendar",'danger')
							break
						else:
							username = clearing_contents.fetch1('username')
							clearing_step = key.split('_')[0]
							summary = f'{username} {clearing_protocol} {clearing_step}'
							add_clearing_calendar_entry(date=date,
							summary=summary,calendar_id=current_app.config['CLEARING_CALENDAR_ID'])
							logger.debug("Added event to clearing calendar")
							flash("Event added to Clearing Calendar. Check the calendar.",'success')
						break
					else: # an update button was pressed
						''' Update the row '''
						logger.debug("update button pressed")
						column_name = key.split('_submit')[0]
						clearing_entry_dict = clearing_contents.fetch1() # returns as a dict
						clearing_entry_dict[column_name]=form[column_name].data
						logger.debug("inserting clearing entry:")
						logger.debug(clearing_entry_dict)
						clearing_dbTable().insert1(clearing_entry_dict,replace=True)
						logger.debug(f"Entered into database: {column_name}:{form[column_name].data}")
						this_index = submit_keys.index(key)
						next_index = this_index + 1 if 'notes' in column_name else this_index+2
						column_name = submit_keys[next_index].split('_submit')[0]
						logger.debug("Moving screen to colum name:")
						logger.debug(column_name)
						break
			else: # if none of the submit keys were found
				abort(500)
		else: # form not validated
			''' Find the first form field where there was an error and set the column_name to it 
			so the focus is set there upon reload of page '''
			logger.debug(form.errors)
			column_name = list(form.errors.keys())[0]
	else: # not a post request
		column_name = None

	clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
	notes_for_clearer = clearing_batch_contents.fetch1('notes_for_clearer')
	if clearing_progress == 'complete':
		flash("Clearing is already complete for this sample. "
			"This page is read only and hitting any of the buttons will not update the clearing log",'warning')
	else:
		clearing_batch_update_dict = clearing_batch_contents.fetch1()
		clearing_batch_update_dict['clearing_progress'] = 'in progress'
		db_lightsheet.Request.ClearingBatch().update1(clearing_batch_update_dict)
	# form.time_pbs_wash1.data = "2019-16-19T16:54:17"
	form_id = '_'.join([username,request_name,'clearing_batch',str(clearing_batch_number)]) 
	return render_template('clearing/clearing_entry.html',clearing_protocol=clearing_protocol,
		antibody1=antibody1,antibody2=antibody2,
		form=form,clearing_table=clearing_table,samples_table=samples_table,
		column_name=column_name,form_id=form_id,
		notes_for_clearer=notes_for_clearer)

@clearing.route("/clearing/clearing_table/<username>/<request_name>/<clearing_batch_number>",
	methods=['GET'])
@logged_in_as_clearing_manager
@log_http_requests
def clearing_table(username,request_name,clearing_batch_number):
	""" Show the clearing contents for a clearing batch """ 
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'request_name="{request_name}"' & \
			f'username="{username}"' & \
			f'clearing_batch_number={clearing_batch_number}'
	clearing_protocol = clearing_batch_contents.fetch1('clearing_protocol')
	overview_table = ClearingTable(clearing_batch_contents)
	clearing_table.table_id = 'horizontal'
	dbTable = determine_clearing_dbtable(clearing_protocol)
	db_contents = dbTable() & f'request_name="{request_name}"' & \
			f'username="{username}"' & \
			f'clearing_batch_number={clearing_batch_number}'
	logger.debug("Showing db contents in table:")
	logger.debug(db_contents)
	table = determine_clearing_table(clearing_protocol)(db_contents)
	table.table_id = 'vertical'

	return render_template('clearing/clearing_table.html',overview_table=overview_table,
		clearing_contents=db_contents,table=table)

@clearing.route("/clearing/antibody_overview",
	methods=['GET'])
@logged_in_as_clearing_manager
@log_http_requests
def antibody_overview():
	""" Show all antibodies currently in the db """ 
	antibody_overview_contents = db_lightsheet.AntibodyOverview()

	overview_table = AntibodyOverviewTable(antibody_overview_contents)

	return render_template('clearing/antibody_overview.html',
		overview_table=overview_table)

@clearing.route("/clearing/antibody_history",
	methods=['GET'])
@log_http_requests
@logged_in
def antibody_history():
	""" Show all antibodies currently in the db """ 
	sort = request.args.get('sort', 'date') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'desc') == 'desc')
	logger.debug(sort)
	logger.debug(reverse)
	current_user = session['user']
	logger.info(f"{current_user} accessed antibody history")
	antibody_history_contents = db_lightsheet.AntibodyHistory()

	# clearing_admins = current_app.config['CLEARING_ADMINS']
	# if current_user not in clearing_admins:
	# 	antibody_history_contents = antibody_history_contents & f'username="{current_user}"'

	sorted_results = sorted(antibody_history_contents.fetch(as_dict=True),
        key=partial(table_sorter,sort_key=sort),reverse=reverse)
	
	history_table = AntibodyHistoryTable(sorted_results,
		sort_by=sort,sort_reverse=reverse)

	return render_template('clearing/antibody_history.html',
		history_table=history_table)

@clearing.route("/clearing/edit_antibody_entry",
	methods=['GET','POST'])
@logged_in
@log_http_requests
def edit_antibody_entry():
	""" Edit an existing antibody history entry """ 
	current_user = session['user']
	logger.info(f"{current_user} accessed edit antibody history")
	clearing_admins = current_app.config['CLEARING_ADMINS']


	date = request.args.get('date')
	date_corr_format = datetime.datetime.strptime(date,'%Y-%m-%d')
	username = request.args.get('username')
	if (current_user not in clearing_admins) and (current_user != username):
		flash("You do not have permission to update this entry","danger")
		return redirect(url_for('clearing.antibody_history'))
	request_name = request.args.get('request_name')
	brief_descriptor = request.args.get('brief_descriptor')
	animal_model = request.args.get('animal_model')
	primary_antibody = request.args.get('primary_antibody')
	primary_order_info = request.args.get('primary_order_info')
	secondary_antibody = request.args.get('secondary_antibody')
	primary_concentration = request.args.get('primary_concentration')
	secondary_concentration = request.args.get('secondary_concentration')
	secondary_order_info = request.args.get('secondary_order_info')
	notes = request.args.get('notes')
	existing_contents = [{
		'date':date_corr_format,
		'username':username,
		'request_name':request_name,
		'brief_descriptor':brief_descriptor,
		'animal_model':animal_model,
		'primary_antibody':primary_antibody,
		'secondary_antibody':secondary_antibody,
		'primary_concentration':primary_concentration,
		'secondary_concentration':secondary_concentration,
		'primary_order_info':primary_order_info,
		'secondary_order_info':secondary_order_info,
		'notes':notes,
		}]
	# logger.debug("received args:")
	# logger.debug(dict(request.args))
	existing_entry_table = AntibodyHistorySingleEntryTable(existing_contents)
	form = EditAntibodyForm()
	restrict_dict = {
		'date':date_corr_format,
		'brief_descriptor':brief_descriptor,
		'animal_model':animal_model,
		'primary_antibody':primary_antibody,
		'secondary_antibody':secondary_antibody,
		'primary_concentration':primary_concentration,
		'secondary_concentration':secondary_concentration,
		}
	existing_db_entry = db_lightsheet.AntibodyHistory() & restrict_dict
	if request.method == 'POST':
		logger.debug("POST request")
		if form.validate_on_submit():
			logger.debug("Form validated")
			form_columns = ['primary_antibody','primary_concentration',
			'secondary_antibody','secondary_concentration','primary_order_info',
			'secondary_order_info','notes',]
			""" Make a replacement insert into the db """
			antibody_history_insert_dict = existing_db_entry.fetch1()
			for col in form.data:
				if col in form_columns:
					antibody_history_insert_dict[col] = form[col].data
			logger.debug("inserting:")
			logger.debug(antibody_history_insert_dict)
			# Delete existing entry
			existing_db_entry.delete()
			db_lightsheet.AntibodyHistory().insert1(antibody_history_insert_dict,
				skip_duplicates=True)
			flash("Antibody entry successfully updated","success")
			return redirect(url_for('clearing.antibody_history'))
	if request.method == 'GET':
		form.date.data = date_corr_format
		form.brief_descriptor.data = brief_descriptor
		form.animal_model.data = animal_model
		form.primary_antibody.data = primary_antibody
		form.secondary_antibody.data = secondary_antibody
		form.primary_concentration.data = primary_concentration
		form.secondary_concentration.data = secondary_concentration
		form.primary_order_info.data = primary_order_info
		form.secondary_order_info.data = secondary_order_info
		form.notes.data = notes
	return render_template('clearing/edit_antibody_form.html',
		form=form,existing_entry_table=existing_entry_table)

@clearing.route("/clearing/new_antibody",
	methods=['GET','POST'])
@logged_in_as_clearing_manager
@log_http_requests
def new_antibody():
	""" Show all antibodies currently in the db """ 

	form = NewAntibodyForm()

	if request.method == 'POST':
		logger.debug("POST request")
		if form.validate_on_submit():
			logger.debug("Form validated")
			form_columns = ['date','brief_descriptor','animal_model',
			'primary_antibody','primary_concentration','primary_order_info',
			'secondary_antibody','secondary_concentration','secondary_order_info','notes',]
			antibody_history_insert_dict = {}
			for col in form.data:
				if col in form_columns:
					antibody_history_insert_dict[col] = form[col].data
			logger.debug("inserting:")
			logger.debug(antibody_history_insert_dict)
			db_lightsheet.AntibodyHistory().insert1(antibody_history_insert_dict)
			flash("New antibody entry successfully captured","success")
			return redirect(url_for('clearing.antibody_history'))
	return render_template('clearing/new_antibody_form.html',
		form=form)