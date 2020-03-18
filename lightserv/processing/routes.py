from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)
from lightserv.processing.forms import StartProcessingForm, NewProcessingRequestForm
from lightserv.processing.tables import (create_dynamic_processing_overview_table,
	dynamic_processing_management_table,ImagingOverviewTable,ExistingProcessingTable,
	ProcessingChannelTable)
from lightserv import db_lightsheet
from lightserv.main.utils import (logged_in, table_sorter,logged_in_as_processor,
	check_clearing_completed,check_imaging_completed,log_http_requests)
from lightserv.processing.utils import run_spock_pipeline
from lightserv import cel
import datajoint as dj
from datetime import datetime
import logging
import tifffile
import glob
import os, errno
import pickle
import paramiko
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/processing_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

# neuroglancer.set_static_content_source(url='https://neuromancer-seung-import.appspot.com')

processing = Blueprint('processing',__name__)

@processing.route("/processing/processing_manager",methods=['GET','POST'])
@logged_in
@log_http_requests
def processing_manager():
	""" A user interface for handling past, present and future clearing batches.
	Can be  used by a clearing admin to handle all clearing batches (except those claimed
	by the researcher) or by a researcher to handle their own clearing batches if they claimed 
	them in their request form """
	sort = request.args.get('sort', 'datetime_submitted') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	current_user = session['user']
	logger.info(f"{current_user} accessed processing manager")

	processing_admins = current_app.config['PROCESSING_ADMINS']
	
	sample_contents = db_lightsheet.Request.Sample()
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch()
	request_contents = db_lightsheet.Request()
	imaging_request_contents = db_lightsheet.Request.ImagingRequest()
	processing_request_contents = (db_lightsheet.Request.ProcessingRequest() * \
	 	clearing_batch_contents * request_contents * imaging_request_contents).\
			proj('clearing_progress','processing_request_date_submitted','processing_request_time_submitted',
			'imaging_progress','imager','species','processing_progress','processor',
			datetime_submitted='TIMESTAMP(processing_request_date_submitted,processing_request_time_submitted)')

	if current_user not in processing_admins:
		processing_request_contents = processing_request_contents & f'username="{current_user}"'
	
	""" Get all entries currently being processed """
	contents_being_processed = processing_request_contents & 'processing_progress="running"'

	being_processed_table_id = 'horizontal_being_processed_table'
	table_being_processed = dynamic_processing_management_table(contents_being_processed,
		table_id=being_processed_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Next get all entities that are ready to be processed '''
	contents_ready_to_process = processing_request_contents & 'imaging_progress="complete"' & \
	'processing_progress="incomplete"'
	ready_to_process_table_id = 'horizontal_ready_to_process_table'
	table_ready_to_process = dynamic_processing_management_table(contents_ready_to_process,
		table_id=ready_to_process_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Now get all entities on deck (ones that are in imaging stage) '''
	contents_on_deck = processing_request_contents & 'clearing_progress="complete"' & \
	 'imaging_progress!="complete"' & 'processing_progress!="complete"'
	on_deck_table_id = 'horizontal_on_deck_table'
	# asdf
	table_on_deck = dynamic_processing_management_table(contents_on_deck,table_id=on_deck_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Get all entities that have have failed processing '''
	contents_failed_processing = processing_request_contents & 'processing_progress="failed"'
	failed_processing_table_id = 'horizontal_failed_processing_table'
	table_failed_processing = dynamic_processing_management_table(contents_failed_processing,
		table_id=failed_processing_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Finally get all entities that have already been processed '''
	contents_already_processed = processing_request_contents & 'processing_progress="complete"'
	already_processed_table_id = 'horizontal_already_processed_table'
	table_already_processed = dynamic_processing_management_table(contents_already_processed,
		table_id=already_processed_table_id,
		sort_by=sort,sort_reverse=reverse)
	
	return render_template('processing/processing_management.html',
		table_failed_processing=table_failed_processing,
		table_being_processed=table_being_processed,
		table_ready_to_process=table_ready_to_process,table_on_deck=table_on_deck,
		table_already_processed=table_already_processed)

@processing.route("/processing/processing_entry/<username>/<request_name>/<sample_name>/<imaging_request_number>/<processing_request_number>",
	methods=['GET','POST'])
@logged_in
@logged_in_as_processor
@check_clearing_completed
@check_imaging_completed
@log_http_requests
def processing_entry(username,request_name,sample_name,imaging_request_number,processing_request_number):
	""" Route for the person assigned as data processor for a sample 
	to start the data processing. """
	logger.info(f"{session['user']} accessed start_processing route")
	
	sample_contents = (db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"')
	sample_dict = sample_contents.fetch1()
	# image_resolution_request_contents = db_lightsheet.Sample.ImagingResolutionRequest() & f'request_name="{request_name}"' & \
	# 			f'username="{username}"' & f'sample_name="{sample_name}"' & \
	# 			f'imaging_request_number="{imaging_request_number}"'

	# logger.debug(f'{username}, {request_name}, {sample_name}, {imaging_request_number}, {processing_request_number}')
	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			 f'imaging_request_number="{imaging_request_number}"' & \
			 f'processing_request_number="{processing_request_number}"'

	processing_resolution_request_contents = db_lightsheet.Request.ProcessingResolutionRequest() & f'request_name="{request_name}"' & \
				f'username="{username}"' & f'sample_name="{sample_name}"' & \
				f'imaging_request_number="{imaging_request_number}"' & \
				f'processing_request_number="{processing_request_number}"'
	# logger.debug(processing_request_contents)
	channel_contents = db_lightsheet.Request.ImagingChannel() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' # all of the channels for this sample
	channel_content_dict_list = channel_contents.fetch(as_dict=True)

	joined_contents = sample_contents * processing_request_contents * processing_resolution_request_contents 
	
	overview_table_id = 'horizontal_procsesing_table'
	overview_table = create_dynamic_processing_overview_table(joined_contents,table_id=overview_table_id)
	overview_table.table_id = overview_table_id

	form = StartProcessingForm()
	
	processing_progress = processing_request_contents.fetch1('processing_progress')

	if request.method == 'POST': # post request
		if processing_progress != 'incomplete':
			flash(f"Processing is {processing_progress} for this sample.  "
			"It cannot be re-processed. To open a new processing request, "
			"see your request page",'warning')
			return redirect(url_for('processing.processing_manager'))
		logger.info('post request')
		if form.validate_on_submit():
			logger.debug("form validated")
			''' Now update the db table with the data collected in the form'''
			
			""" loop through and update the atlas to be used based on what the user supplied """
			for form_resolution_dict in form.image_resolution_forms.data:
				this_image_resolution = form_resolution_dict['image_resolution']
				# logger.info(this_image_resolution)
				this_image_resolution_content = processing_resolution_request_contents & \
				f'image_resolution="{this_image_resolution}"'
				# logger.debug(this_image_resolution_content)
				atlas_name = form_resolution_dict['atlas_name']
				logger.info("updating atlas and notes_from_processing in ProcessingResolutionRequest() with user's form data")
				dj.Table._update(this_image_resolution_content,'atlas_name',atlas_name)
				dj.Table._update(this_image_resolution_content,'notes_from_processing',form.notes_from_processing.data)

			logger.info(f"Starting step0 without celery for testing")
			# run_step0.delay(username=username,request_name=request_name,sample_name=sample_name)
			''' Update the processing progress before starting the jobs on spock 
			to avoid a race condition (the pipeline also updates the processing_progress flag if it fails or succeeds) '''
			
			# try:
			run_spock_pipeline(username=username,request_name=request_name,sample_name=sample_name,
				imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number)
			dj.Table._update(processing_request_contents,'processing_progress','running')

			flash("Your data processing has begun. You will receive an email "
				  "when it is completed.","success")
			# except:
			# 	logger.info("Pipeline initialization failed. Updating processing progress to 'failed' ")
			# 	dj.Table._update(processing_request_contents,'processing_progress','failed')
			# 	abort(500)
			
			return redirect(url_for('requests.all_requests'))
		else:
			logger.debug(form.errors)
	
	elif request.method == 'GET': # get request
		channel_contents_lists = []
		while len(form.image_resolution_forms) > 0:
			form.image_resolution_forms.pop_entry()
		""" Figure out the unique number of image resolutions """
		unique_image_resolutions = sorted(list(set(channel_contents.fetch('image_resolution'))))

		for ii in range(len(unique_image_resolutions)):
			this_image_resolution = unique_image_resolutions[ii]
			processing_resolution_request_content = processing_resolution_request_contents & \
			 f'image_resolution="{this_image_resolution}"'

			channel_contents_list_this_resolution = (channel_contents & f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
			channel_contents_lists.append([])
			form.image_resolution_forms.append_entry()
			this_resolution_form = form.image_resolution_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution
			this_resolution_form.atlas_name.data = processing_resolution_request_content.fetch1('atlas_name')

			''' Now go and add the channel subforms to the image resolution form '''
			for jj in range(len(channel_contents_list_this_resolution)):
				channel_content = channel_contents_list_this_resolution[jj]
				channel_contents_lists[ii].append(channel_content)
				this_resolution_form.channel_forms.append_entry()
				this_channel_form = this_resolution_form.channel_forms[-1]
				this_channel_form.channel_name.data = channel_content['channel_name']

				""" figure out the channel purposes """
				used_imaging_modes = []
				for imaging_mode in current_app.config['IMAGING_MODES']:
					if channel_content[imaging_mode]:
						used_imaging_modes.append(imaging_mode)
				channel_purposes_str = ', '.join(mode for mode in used_imaging_modes)
				this_channel_form.channel_purposes_str.data = channel_purposes_str

	if processing_progress != 'incomplete':
		logger.info(f"Processing is currently {processing_progress} but accessing the processing entry page anyway")
		flash(f"Processing is {processing_progress} for this sample. "
			"This page is read only and hitting submit will do nothing",'warning')
	data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
	return render_template('processing/processing_entry.html',
		processing_request_number=processing_request_number,
		channel_contents_lists=channel_contents_lists,
		sample_dict=sample_dict,data_bucket_rootpath=data_bucket_rootpath,
		form=form,overview_table=overview_table)	

@processing.route("/processing/new_processing_request/<username>/<request_name>/<sample_name>/<imaging_request_number>",methods=['GET','POST'])
@logged_in
@log_http_requests
def new_processing_request(username,request_name,sample_name,imaging_request_number): 
	""" Route for user to submit a new processing request to an 
	already existing sample/imaging request combo 
	. This takes place after the initial request and it must correspond 
	to a particular imaging request because users are allowed 
	multiple imaging requests and we need to keep track of which 
	image set (for the same sample) this new processing request
	corresponds to. 
	and first imaging round took place. This can sometimes happen if
	someone is new to using the core facility and realizes after their 
	first imaging round that they want a different kind of imaging 
	for the same sample.  """
	logger.info(f"{session['user']} accessed new imaging request form")
	form = NewProcessingRequestForm(request.form)

	all_imaging_modes = current_app.config['IMAGING_MODES']

	sample_contents = db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"'								
	sample_dict = sample_contents.fetch1()
	# sample_table = SampleTable(sample_contents)
	channel_contents = (db_lightsheet.Request.ImagingChannel() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"')
	""" figure out the new processing request number to give the new request """
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' & \
	 		f'imaging_request_number="{imaging_request_number}"'
	previous_processing_resolution_request_contents = db_lightsheet.Request.ProcessingResolutionRequest() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' & \
	 		f'imaging_request_number="{imaging_request_number}"'  

	previous_processing_request_contents = db_lightsheet.Request.ProcessingRequest() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' & \
	 		f'imaging_request_number="{imaging_request_number}"' 

	previous_processing_request_numbers = np.unique(previous_processing_request_contents.\
		fetch('processing_request_number'))

	previous_max_processing_request_number = max(previous_processing_request_numbers)
	new_processing_request_number = previous_max_processing_request_number + 1
	
	existing_processing_table = ExistingProcessingTable(channel_contents * \
		previous_processing_request_contents * previous_processing_resolution_request_contents)
	imaging_overview_table = ImagingOverviewTable(channel_contents * imaging_request_contents)
	if request.method == 'POST':
		if form.validate_on_submit():
			logger.debug("form validated")
			connection = db_lightsheet.Request.ProcessingRequest.connection
			with connection.transaction:
				""" First handle the ImagingRequest() and ProcessingRequest() entries """
				now = datetime.now()
				date = now.strftime("%Y-%m-%d")
				time = now.strftime("%H:%M:%S") 
				
				""" ProcessingRequest """
				processing_request_insert_dict = {}
				processing_request_number = 1 # because the imaging request is just now being created there are no processing requests already for this imaging request
				processing_request_insert_dict['request_name'] = request_name
				processing_request_insert_dict['username'] = username 
				processing_request_insert_dict['sample_name'] = sample_name
				processing_request_insert_dict['imaging_request_number'] = imaging_request_number
				processing_request_insert_dict['processing_request_number'] = new_processing_request_number
				processing_request_insert_dict['processing_request_date_submitted'] = date
				processing_request_insert_dict['processing_request_time_submitted'] = time
				processing_request_insert_dict['processing_progress'] = "incomplete" 
				""" The user is always the "processor" - i.e. the person
				 who double-checks the processing form and hits GO """
				processing_request_insert_dict['processor'] = username

				logger.info("ProcessingRequest() insert:")
				logger.info(processing_request_insert_dict)
				logger.info("")
				db_lightsheet.Request.ProcessingRequest().insert1(processing_request_insert_dict)

				# logger.info("updating sample contents from form data")
				# dj.Table._update(sample_contents,'notes_from_processing',form.notes_from_processing.data)
				processing_resolution_insert_list = []
				""" loop through image resolution forms and make a new entry for each resolution """
				for form_resolution_dict in form.image_resolution_forms.data:
					logger.debug(form_resolution_dict)
					this_image_resolution = form_resolution_dict['image_resolution']
					processing_resolution_insert_dict = {}
					processing_resolution_insert_dict['request_name'] = request_name
					processing_resolution_insert_dict['username'] = username 
					processing_resolution_insert_dict['sample_name'] = sample_name
					processing_resolution_insert_dict['imaging_request_number'] = imaging_request_number
					processing_resolution_insert_dict['processing_request_number'] = new_processing_request_number
					processing_resolution_insert_dict['image_resolution'] = form_resolution_dict['image_resolution']
					processing_resolution_insert_dict['atlas_name'] = form_resolution_dict['atlas_name']
					processing_resolution_insert_list.append(processing_resolution_insert_dict)

				logger.info("ProcessingResolutionRequest() insert:")
				logger.info(processing_resolution_insert_list)
				logger.info("")
				db_lightsheet.Request.ProcessingResolutionRequest().insert1(processing_resolution_insert_dict)


			flash("Processing request successfully submitted. ","success")
			return redirect(url_for('processing.processing_manager'))
			
		else: # form not validated
			if 'submit' in form.errors:
				for error_str in form.errors['submit']:
					flash(error_str,'danger')
			
			logger.debug("Not validated! See error dict below:")
			logger.debug(form.errors)
			logger.debug("")
			flash_str = 'There were errors below. Correct them before proceeding'
			flash(flash_str,'danger')
			""" deal with errors in the image resolution subforms - those
			do not show up in the rendered tables like normal form errors """
			for obj in form.errors['image_resolution_forms']:
				if isinstance(obj,dict):
					for key,val in list(obj.items()):
						for error_str in val:
							flash(error_str,'danger')
				elif isinstance(obj,str):
					flash(obj,'danger')
	
	elif request.method == 'GET': # get request
		logger.info("GET request")
		channel_contents_lists = []
		while len(form.image_resolution_forms) > 0:
			form.image_resolution_forms.pop_entry()
		""" Figure out the unique number of image resolutions """
		unique_image_resolutions = sorted(list(set(channel_contents.fetch('image_resolution'))))
		for ii in range(len(unique_image_resolutions)):
			this_image_resolution = unique_image_resolutions[ii]
			image_resolution_request_content = db_lightsheet.Request.ImagingResolutionRequest() & \
			 f'request_name="{request_name}"' & f'username="{username}"' & \
			 f'sample_name="{sample_name}"' & f'imaging_request_number="{imaging_request_number}"' & \
			 f'image_resolution="{this_image_resolution}"'

			channel_contents_list_this_resolution = (channel_contents & f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
			channel_contents_lists.append([])
			form.image_resolution_forms.append_entry()
			this_resolution_form = form.image_resolution_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution
			# this_resolution_form.atlas_name.data = image_resolution_request_content.fetch1('atlas_name')

			''' Now go and add the channel subforms to the image resolution form '''
			for jj in range(len(channel_contents_list_this_resolution)):
				channel_content = channel_contents_list_this_resolution[jj]
				channel_contents_lists[ii].append(channel_content)
				this_resolution_form.channel_forms.append_entry()
				this_channel_form = this_resolution_form.channel_forms[-1]
				this_channel_form.channel_name.data = channel_content['channel_name']

				""" figure out the channel purposes """
				used_imaging_modes = []
				for imaging_mode in current_app.config['IMAGING_MODES']:
					if channel_content[imaging_mode] == True:
						this_channel_form[imaging_mode].data = 1
						used_imaging_modes.append(imaging_mode)
				channel_purposes_str = ', '.join(mode for mode in used_imaging_modes)
				this_channel_form.channel_purposes_str.data = channel_purposes_str

	return render_template('processing/new_processing_request.html',
		imaging_request_number=imaging_request_number,
		new_processing_request_number=new_processing_request_number,form=form,
		imaging_overview_table=imaging_overview_table,
		existing_processing_table=existing_processing_table,
		channel_contents_lists=channel_contents_lists,sample_dict=sample_dict)


@processing.route("/processing/processing_table/<username>/<request_name>/<sample_name>/<imaging_request_number>/<processing_request_number>",
	methods=['GET','POST'])
@logged_in
@log_http_requests
def processing_table(username,request_name,
	sample_name,imaging_request_number,processing_request_number): 
	""" Shows overview of a processing request  """
	logger.info(f"{session['user']} accessed processing table")
	sample_contents = (db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"')

	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			 f'imaging_request_number="{imaging_request_number}"' & \
			 f'processing_request_number="{processing_request_number}"'

	processing_resolution_request_contents = db_lightsheet.Request.ProcessingResolutionRequest() & f'request_name="{request_name}"' & \
				f'username="{username}"' & f'sample_name="{sample_name}"' & \
				f'imaging_request_number="{imaging_request_number}"' & \
				f'processing_request_number="{processing_request_number}"'
	# channel_contents = db_lightsheet.Request.ImagingChannel() & f'request_name="{request_name}"' & \
	# 		f'username="{username}"' & f'sample_name="{sample_name}"' & \
	# 		f'imaging_request_number="{imaging_request_number}"' # all of the channels for this sample
	# channel_content_dict_list = channel_contents.fetch(as_dict=True)

	joined_contents = sample_contents * processing_request_contents * processing_resolution_request_contents 
	
	overview_table_id = 'horizontal_procsesing_table'
	overview_table = create_dynamic_processing_overview_table(joined_contents,table_id=overview_table_id)

	processing_channel_contents = db_lightsheet.Request.ProcessingChannel() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' & \
			f'processing_request_number={processing_request_number}'
	processing_channel_table = ProcessingChannelTable(processing_channel_contents)
			 # all of the channels for this sample
	return render_template('processing/processing_log.html',overview_table=overview_table,
		processing_channel_table=processing_channel_table)