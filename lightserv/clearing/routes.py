from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup,current_app)
from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
									  iDiscoAbbreviatedRatForm, uDiscoForm,  iDiscoEduForm )
from lightserv.clearing.tables import ClearingTable,IdiscoPlusTable, dynamic_clearing_management_table
from lightserv import db_lightsheet
from .utils import (determine_clearing_form, add_clearing_calendar_entry,
				   determine_clearing_dbtable, determine_clearing_table) 
from lightserv.main.utils import (logged_in, logged_in_as_clearer,
	 logged_in_as_clearing_manager, log_http_requests)
import numpy as np
import datajoint as dj
import re
import datetime

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
	reverse = (request.args.get('direction', 'asc') == 'desc')
	current_user = session['user']
	logger.info(f"{current_user} accessed clearing manager")

	clearing_admins = current_app.config['CLEARING_ADMINS']
	if current_user not in clearing_admins:
		clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'clearer="{current_user}"'
	else:
		clearing_batch_contents = db_lightsheet.Request.ClearingBatch()
	request_contents = db_lightsheet.Request()
	combined_contents = (clearing_batch_contents * request_contents).proj(
		'number_in_batch',
		'clearing_protocol','species',
		'clearer','clearing_progress','clearing_protocol','antibody1','antibody2',
		datetime_submitted='TIMESTAMP(date_submitted,time_submitted)')
	# combined_contents = dj.U('request_name','username','clearing_protocol','antibody1','antibody2').aggr(sample_contents, 
 #        clearer='clearer',clearing_progress='clearing_progress',
 #        sample_name='min(sample_name)',number_in_batch='count(*)') * request_contents	
	# all_contents_unique_clearing_protocol = combined_contents.proj('sample_name','number_in_batch',
	# 	'clearing_protocol','species',
	# 	'clearer','clearing_progress','clearing_protocol','antibody1','antibody2',
	# 	datetime_submitted='TIMESTAMP(date_submitted,time_submitted)') # will pick up the primary keys by default

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
	contents_already_cleared = combined_contents & 'clearing_progress="complete"'
	already_cleared_table_id = 'horizontal_already_cleared_table'
	table_already_cleared = dynamic_clearing_management_table(contents_already_cleared,
		table_id=already_cleared_table_id,
		sort_by=sort,sort_reverse=reverse)
	
	return render_template('clearing/clearing_management.html',table_being_cleared=table_being_cleared,
		table_ready_to_clear=table_ready_to_clear,
		table_already_cleared=table_already_cleared)

@clearing.route("/clearing/clearing_entry/<username>/<request_name>/<clearing_protocol>/<clearing_batch_number>/",
	methods=['GET','POST'],defaults={'antibody1':'','antibody2':''})
@clearing.route("/clearing/clearing_entry/<username>/<request_name>/<clearing_protocol>/<clearing_batch_number>/<antibody1>/",
	methods=['GET','POST'],defaults={'antibody2':''})
@clearing.route("/clearing/clearing_entry/<username>/<request_name>/<clearing_protocol>/<clearing_batch_number>/<antibody1>/<antibody2>",
	methods=['GET','POST'])
@logged_in
@logged_in_as_clearer
@log_http_requests
def clearing_entry(username,request_name,clearing_protocol,antibody1,antibody2,clearing_batch_number): 
	current_user = session['user']
	logger.debug(f'{current_user} accessed clearing entry form')
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'clearing_protocol="{clearing_protocol}"' & \
	 		f'antibody1="{antibody1}"' & f'antibody2="{antibody2}"'	& \
	 		f'clearing_batch_number={clearing_batch_number}'				
	if len(clearing_batch_contents) == 0:
		flash("No clearing batch exists with those parameters. Please try again.")
		return redirect(url_for('requests.all_requests'))
	clearing_table = ClearingTable(clearing_batch_contents)
	
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
		fill_dict = {'exp_notes':'some_notes'}
		form = determine_clearing_form(clearing_protocol,existing_form=request.form)
		for key,val in list(clearing_contents.fetch1().items()):
			if key in form._fields.keys():
				form[key].data = val	
	else:
		form = determine_clearing_form(clearing_protocol,existing_form=request.form)

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
			request_name=request_name,clearing_protocol=clearing_protocol,
			antibody1=antibody1,antibody2=antibody2,clearing_batch_number=clearing_batch_number))
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

							''' update the clearing progress to "complete" for this sample entry '''
							dj.Table._update(clearing_batch_contents,'clearing_progress','complete')

							''' Update the entries by inserting with replace=True'''
							clearing_dbTable().insert1(clearing_insert_dict,replace=True)	
							flash("Clearing form was successfully completed.",'success')
							return redirect(url_for('clearing.clearing_manager'))

					elif re.search("^(?!perfusion).*_date_submit$",key) != None: # one of the calendar date submit buttons
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
					else: # an update button was pressed
						''' Update the row '''
						column_name = key.split('_submit')[0]
						clearing_entry_dict = clearing_contents.fetch1() # returns as a dict
						clearing_entry_dict[column_name]=form[column_name].data
						# clearing_contents.delete_quick()
						clearing_dbTable().insert1(clearing_entry_dict,replace=True)
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

	clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
	if clearing_progress == 'complete':
		flash("Clearing is already complete for this sample. "
			"This page is read only and hitting any of the buttons will not update the clearing log",'warning')
	else:
		dj.Table._update(clearing_batch_contents,'clearing_progress','in progress')
	# form.time_pbs_wash1.data = "2019-16-19T16:54:17"
	return render_template('clearing/clearing_entry.html',clearing_protocol=clearing_protocol,
		form=form,clearing_table=clearing_table,column_name=column_name)

@clearing.route("/clearing/clearing_table/<username>/<request_name>/<clearing_protocol>/<clearing_batch_number>/",
	methods=['GET','POST'],defaults={'antibody1':'','antibody2':''})
@clearing.route("/clearing/clearing_table/<username>/<request_name>/<clearing_protocol>/<clearing_batch_number>/<antibody1>/",
	methods=['GET','POST'],defaults={'antibody2':''})
@clearing.route("/clearing/clearing_table/<username>/<request_name>/<clearing_protocol>/<clearing_batch_number>/<antibody1>/<antibody2>",
	methods=['GET','POST'])
@logged_in_as_clearer
@log_http_requests
def clearing_table(username,request_name,clearing_protocol,antibody1,antibody2,clearing_batch_number):
	""" Show the clearing contents for a clearing batch """ 
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'clearing_protocol="{clearing_protocol}"' & \
	 		f'antibody1="{antibody1}"' & f'antibody2="{antibody2}"'	& \
	 		f'clearing_batch_number={clearing_batch_number}'

	overview_table = ClearingTable(clearing_batch_contents)
	clearing_table.table_id = 'horizontal'
	dbTable = determine_clearing_dbtable(clearing_protocol)
	db_contents = dbTable() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'clearing_protocol="{clearing_protocol}"' & \
	 		f'antibody1="{antibody1}"' & f'antibody2="{antibody2}"'	& \
	 		f'clearing_batch_number={clearing_batch_number}'
	table = determine_clearing_table(clearing_protocol)(db_contents)
	table.table_id = 'vertical'

	return render_template('clearing/clearing_table.html',overview_table=overview_table,
		clearing_contents=db_contents,table=table)
