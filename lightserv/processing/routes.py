from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)
from lightserv.processing.forms import StartProcessingForm,PystripeEntryForm
from lightserv.processing.tables import (create_dynamic_processing_overview_table,
	dynamic_processing_management_table,ImagingOverviewTable,ExistingProcessingTable,
	ProcessingChannelTable,dynamic_pystripe_management_table)
from lightserv import db_lightsheet
from lightserv.main.utils import (logged_in, table_sorter,logged_in_as_processor,
	check_clearing_completed,check_imaging_completed,log_http_requests,mymkdir)
from lightserv.processing.tasks import run_lightsheet_pipeline, smartspim_pystripe
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

@processing.route("/processing/pystripe_manager",methods=['GET','POST'])
@logged_in
@log_http_requests
def pystripe_manager():
	"""  """
	sort = request.args.get('sort', 'request_name') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	current_user = session['user']
	logger.info(f"{current_user} accessed pystripe_manager")

	processing_admins = current_app.config['PROCESSING_ADMINS']
	
	# Select smartspim samples that have been fully imaged (all channels)
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() 
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() 
	imaged_channel_contents = imaging_channel_contents * imaging_request_contents &\
		{'imaging_progress':'complete'} & 'image_resolution="3.6x"'
	
	stitching_contents = db_lightsheet.Request.SmartspimStitchedChannel()
	
	imaged_aggr_contents = dj.U('username','request_name','sample_name',
		'imaging_request_number').aggr(
		imaged_channel_contents,
		n_channels_imaged='count(*)')
	
	stitched_aggr_contents = dj.U('username','request_name','sample_name',
		'imaging_request_number').aggr(
		stitching_contents,
		n_channels_stitched='sum(smartspim_stitching_spock_job_progress="COMPLETED")')
	
	imaged_and_stitched_contents = imaged_aggr_contents * stitched_aggr_contents &\
		'n_channels_imaged=n_channels_stitched'
	
	pystripe_channel_contents = db_lightsheet.Request.SmartspimPystripeChannel() 

	if current_user not in processing_admins:
		imaged_and_stitched_contents = imaged_and_stitched_contents & {'username':current_user}
		pystripe_channel_contents = pystripe_channel_contents & {'username':current_user}

	''' Get contents ready to be pystriped.
	These are entries of the stitching table that are not in the pystripe table yet. '''

	contents_ready_to_pystripe = imaged_and_stitched_contents - pystripe_channel_contents
	ready_to_pystripe_table_id = 'horizontal_ready_to_pystripe_table'
	table_ready_to_pystripe = dynamic_pystripe_management_table(contents_ready_to_pystripe,
		table_id=ready_to_pystripe_table_id,
		sort_by=sort,sort_reverse=reverse)

	combined_contents = imaged_and_stitched_contents * pystripe_channel_contents
	''' Figure out which imaging requests are currently being pystriped, ready to be pystriped
	and already completed being pystriped '''
	pystripe_imaging_requests = dj.U('username','request_name','sample_name',
    'imaging_request_number').aggr(combined_contents,
                                   username='username',
                                   n_channels_imaged='n_channels_imaged',
                                   n_channels_pystriped='sum(pystripe_performed)',
                                   n_channels_started='count(*)',
                                  )

	''' Get all entities that are currently being pystriped.'''

	imaging_requests_currently_being_pystriped = pystripe_imaging_requests &\
		'n_channels_pystriped!=n_channels_imaged' & 'n_channels_started>0' 

	currently_being_pystriped_table_id = 'horizontal_currently_being_pystriped_table'
	table_currently_being_pystriped = dynamic_pystripe_management_table(imaging_requests_currently_being_pystriped,
		table_id=currently_being_pystriped_table_id,
		sort_by=sort,sort_reverse=reverse)


	imaging_requests_already_pystriped = pystripe_imaging_requests &\
		'n_channels_pystriped=n_channels_imaged'

	already_pystriped_table_id = 'horizontal_already_pystriped_table'
	table_already_pystriped = dynamic_pystripe_management_table(imaging_requests_already_pystriped,
		table_id=already_pystriped_table_id,
		sort_by=sort,sort_reverse=reverse)
	
	return render_template('processing/pystripe_management.html',
		table_ready_to_pystripe=table_ready_to_pystripe,
		table_already_pystriped=table_already_pystriped,
		table_currently_being_pystriped=table_currently_being_pystriped)

@processing.route("/processing/pystripe_entry/<username>/<request_name>/<sample_name>/<imaging_request_number>",
	methods=['GET','POST'])
@logged_in
@check_clearing_completed
@check_imaging_completed
@log_http_requests
def pystripe_entry(username,request_name,sample_name,imaging_request_number):
	""" Route to start the pystripe script for a set of channels in a
	single imaging request for a single sample after a Flat has been generated. """
	logger.info(f"{session['user']} accessed pystripe_entry route")
	restrict_dict = {'username':username,
					 'request_name':request_name,
					 'sample_name':sample_name,
					 'imaging_request_number':imaging_request_number} 
	stitching_contents = db_lightsheet.Request.SmartspimStitchedChannel() & restrict_dict

	form = PystripeEntryForm(request.form)

	if request.method == 'POST': # post request
		logger.debug("POST request")
		
		""" loop through channels forms and find the one that was submitted,
		then do validation check  """
		for ii,channel_form in enumerate(form.channel_forms):
			submitted = channel_form.start_pystripe.data
			if submitted:
				logger.debug(f"Channel form {ii} submitted")
				logger.debug(channel_form.data)
				if channel_form.validate_on_submit():
					logger.debug("Channel form validated")
					channel_name = channel_form.channel_name.data
					ventral_up = int(channel_form.ventral_up.data) # for testing it turns 0 into '0' for some reason
					image_resolution = channel_form.image_resolution.data
					flat_name = channel_form.flat_name.data
					data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
					channel_names = current_app.config['SMARTSPIM_IMAGING_CHANNELS']
					channel_index = channel_names.index(channel_name)
					rawdata_subfolder = f'Ex_{channel_name}_Em_{channel_index}'
					if ventral_up:
						logger.debug("have ventral up imaging")
						flat_name_fullpath = os.path.join(data_bucket_rootpath,username,
							request_name,sample_name,
							f'imaging_request_{imaging_request_number}',
							'rawdata',f'resolution_{image_resolution}_ventral_up',
							f'{rawdata_subfolder}_stitched',flat_name)
					else:
						logger.debug("have dorsal up imaging")
						flat_name_fullpath = os.path.join(data_bucket_rootpath,username,
							request_name,sample_name,
							f'imaging_request_{imaging_request_number}',
							'rawdata',f'resolution_{image_resolution}',
							f'{rawdata_subfolder}_stitched',flat_name)
					
					# Now start pystripe task
					kwargs = dict(username=username,
							request_name=request_name,
							sample_name=sample_name,
							imaging_request_number=imaging_request_number,
							channel_name=channel_name,
							image_resolution=image_resolution,
							ventral_up=ventral_up,
							rawdata_subfolder=rawdata_subfolder,
							flat_name_fullpath = flat_name_fullpath)
					
					if not os.environ['FLASK_MODE'] == "TEST":
						smartspim_pystripe.delay(**kwargs)
					else:
						logger.debug("Not running pystripe async task because we are in TEST mode.")
					pystripe_channel_insert_dict = {
						'username':username,
						'request_name':request_name,
						'sample_name':sample_name,
						'imaging_request_number':imaging_request_number,
						'image_resolution':image_resolution,
						'channel_name':channel_name,
						'ventral_up':ventral_up,
						'flatfield_filename':os.path.basename(flat_name_fullpath),
						'smartspim_pystripe_spock_job_progress':"SUBMITTED",
					}
					db_lightsheet.Request.SmartspimPystripeChannel().insert1(
						pystripe_channel_insert_dict,skip_duplicates=True) # it is possible the async task makes the insert first
					ventral_up_str = 'ventral up' if ventral_up else 'dorsal up' 
					flash(f"Started pystripe for channel: {channel_name}, {ventral_up_str}","success")
					# Figure out if this is the last channel to be pystriped. If so, then reroute back to the pystripe manager
					
					pystripe_channel_contents = db_lightsheet.Request.SmartspimPystripeChannel() & restrict_dict
					if len(pystripe_channel_contents) == len(form.channel_forms):
						flash("Pystripe has been started for all channels in the sample.","success")
						return redirect(url_for('processing.pystripe_manager'))
					return redirect(url_for('processing.pystripe_entry',username=username,
						request_name=request_name,sample_name=sample_name,
						imaging_request_number=imaging_request_number))
				else:
					logger.debug("not validated")
					logger.debug("here are the errors")
					logger.debug(channel_form.errors)
					flash("There was an error. See below","danger")
	elif request.method == "GET":
		logger.debug("GET request")
		# Remove old forms and regenerate
		while len(form.channel_forms) > 0:
			form.channel_forms.pop_entry() # pragma: no cover - used to exclude this line from calculating test coverage
		# Loop over channels and add subform for each one
		for stitching_dict in stitching_contents:
			image_resolution = stitching_dict['image_resolution']
			channel_name = stitching_dict['channel_name']
			ventral_up = stitching_dict['ventral_up']
			
			form.channel_forms.append_entry()
			this_channel_form = form.channel_forms[-1]
			this_channel_form.username.data = username
			this_channel_form.request_name.data = request_name
			this_channel_form.sample_name.data = sample_name
			this_channel_form.imaging_request_number.data = imaging_request_number
			this_channel_form.image_resolution.data = image_resolution
			this_channel_form.channel_name.data = channel_name
			this_channel_form.ventral_up.data = ventral_up

	"""" If either GET or POST, loop over existing channel forms and 
	strike out any for which pystriped has already been started """
	n_remaining_channels = len(form.channel_forms)
	for this_channel_form in form.channel_forms:
		image_resolution = this_channel_form.image_resolution.data
		channel_name = this_channel_form.channel_name.data
		ventral_up = this_channel_form.ventral_up.data
		
		# Figure out if pystripe already started for this channel
		# This amounts to checking if there is an entry in the 
		# SmartspimPystripeChannel() table
		restrict_dict_pystripe = restrict_dict.copy()
		restrict_dict_pystripe['image_resolution'] = image_resolution
		restrict_dict_pystripe['channel_name'] = channel_name
		restrict_dict_pystripe['ventral_up'] = ventral_up
		pystripe_started_contents = db_lightsheet.Request.SmartspimPystripeChannel &\
			restrict_dict_pystripe
		if len(pystripe_started_contents) > 0:
			this_channel_form.pystripe_started.data = True
			flat_name,pystripe_status = pystripe_started_contents.fetch1(
				'flatfield_filename','smartspim_pystripe_spock_job_progress')
			this_channel_form.flat_name.data = flat_name
			this_channel_form.pystripe_status.data = pystripe_status
			n_remaining_channels-=1
	
	data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
	return render_template('processing/pystripe_entry.html',
		data_bucket_rootpath=data_bucket_rootpath,
		form=form,n_remaining_channels=n_remaining_channels)	


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

	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			 f'imaging_request_number="{imaging_request_number}"' & \
			 f'processing_request_number="{processing_request_number}"'

	processing_resolution_request_contents = db_lightsheet.Request.ProcessingResolutionRequest() & f'request_name="{request_name}"' & \
				f'username="{username}"' & f'sample_name="{sample_name}"' & \
				f'imaging_request_number="{imaging_request_number}"' & \
				f'processing_request_number="{processing_request_number}"'
	
	channel_contents = db_lightsheet.Request.ImagingChannel() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' # all of the channels for this sample
	
	channel_content_dict_list = channel_contents.fetch(as_dict=True)

	joined_contents = sample_contents * processing_request_contents * processing_resolution_request_contents 
	
	overview_table_id = 'horizontal_procsesing_table'
	overview_table = create_dynamic_processing_overview_table(joined_contents,table_id=overview_table_id)
	overview_table.table_id = overview_table_id

	form = StartProcessingForm(request.form)
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
			logger.debug("form data after POST request")
			logger.debug(form.data)
			''' Now update the db table with the data collected in the form'''
			
			""" loop through and update the atlas to be used based on what the user supplied """
			for image_resolution_form in form.image_resolution_forms:

				# logger.debug("form resolution dict:")
				# logger.debug(form_resolution_dict)
				this_image_resolution = image_resolution_form.image_resolution.data
				this_image_resolution = this_image_resolution if 'ventral_up' not in this_image_resolution else this_image_resolution.strip('_ventral_up')
				ventral_up = image_resolution_form.ventral_up.data
				logger.debug("Image resolution:")				
				logger.debug(this_image_resolution)
				logger.debug("ventral_up?")
				logger.debug(ventral_up)
				atlas_name = image_resolution_form.atlas_name.data
				logger.debug("Atlas name:")
				logger.debug(atlas_name)
				logger.debug(type(atlas_name))
				""" Make processing path on /jukebox """
				if ventral_up: 
					processing_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
					username,request_name,sample_name,f'imaging_request_{imaging_request_number}',
					'output',f'processing_request_{processing_request_number}',
					f'resolution_{this_image_resolution}_ventral_up')
				else:
					processing_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
					username,request_name,sample_name,f'imaging_request_{imaging_request_number}',
					'output',f'processing_request_{processing_request_number}',
					f'resolution_{this_image_resolution}')
				mymkdir(processing_path_to_make)
				restrict_dict = {'image_resolution':this_image_resolution,'ventral_up':ventral_up}
				this_processing_resolution_content = processing_resolution_request_contents & restrict_dict
				""" If a processing resolution request does not already exist for this resolution/ventral_up 
				combination then just make a new one """
				if len(this_processing_resolution_content) == 0:
					logger.debug("Making a new ProcessingResolutionRequest insert since one did not exist")
					image_resolution_to_insert = this_image_resolution if 'ventral_up' not in this_image_resolution else this_image_resolution.strip("_ventral_up")
					processing_resolution_request_insert_dict = dict(
						username=username,request_name=request_name,
						sample_name=sample_name,
						image_resolution=image_resolution_to_insert,
						imaging_request_number=imaging_request_number,
						processing_request_number=processing_request_number,
						ventral_up=ventral_up,
						atlas_name=atlas_name,
						final_orientation='sagittal',
						)
					db_lightsheet.Request.ProcessingResolutionRequest().insert1(
						processing_resolution_request_insert_dict
					)
					this_processing_resolution_content = db_lightsheet.Request.ProcessingResolutionRequest() & \
						f'image_resolution="{image_resolution_to_insert}"' & f'ventral_up={ventral_up}'

				logger.info("updating atlas and notes_from_processing in ProcessingResolutionRequest() with user's form data")
				processing_resolution_insert_dict = this_processing_resolution_content.fetch1()
				processing_resolution_insert_dict['atlas_name'] = atlas_name
				processing_resolution_insert_dict['notes_from_processing'] = form.notes_from_processing.data
				db_lightsheet.Request.ProcessingResolutionRequest().insert1(processing_resolution_insert_dict,replace=True)
			logger.info(f"Starting light sheet pipeline task")

			if not os.environ['FLASK_MODE'] == 'TEST': # pragma: no cover - used to exclude this line from calculating test coverage
				run_lightsheet_pipeline.delay(username=username,request_name=request_name,sample_name=sample_name,
					imaging_request_number=imaging_request_number,
					processing_request_number=processing_request_number)
			dj.Table._update(processing_request_contents,'processing_progress','running')
			logger.debug("Updated processing_progress in ProcessingRequest() table")
			flash("Your data processing has begun. You will receive an email "
				  "when it is completed.","success")
		
			
			return redirect(url_for('requests.all_requests'))
		else:
			logger.debug(form.errors) # pragma: no cover - used to exclude this line from calculating test coverage
	
	channel_contents_lists = [] # list of lists. [resolution1_list,resolution2_list,...]
	no_registration=True # start it out as True, set to false if we find any registration channels
	while len(form.image_resolution_forms) > 0:
		form.image_resolution_forms.pop_entry() # pragma: no cover - used to exclude this line from calculating test coverage
	""" Figure out the unique number of image resolutions """
	unique_image_resolutions = sorted(list(set(channel_contents.fetch('image_resolution'))))
	""" for each unique image resolution figure out if there is ventral up imaging.
	If there is, then we need to create a new image resolution subform """
	resolution_list_index = 0
	for ii in range(len(unique_image_resolutions)):
		this_image_resolution = unique_image_resolutions[ii]
		logger.debug("Making form for image resolution:")
		logger.debug(this_image_resolution)
		
		channel_contents_this_resolution = channel_contents & f'image_resolution="{this_image_resolution}"'
		dorsal_channel_contents = channel_contents_this_resolution & 'ventral_up=0'
		ventral_channel_contents = channel_contents_this_resolution & 'ventral_up=1'
		if dorsal_channel_contents:
			logger.debug("Have dorsal up channels")
			processing_resolution_request_content = processing_resolution_request_contents & \
			 f'image_resolution="{this_image_resolution}"' & f'ventral_up=0'
			atlas_name_this_resolution = processing_resolution_request_content.fetch1('atlas_name') 
			dorsal_channel_list = dorsal_channel_contents.fetch(as_dict=True)
			channel_contents_lists.append([])
			form.image_resolution_forms.append_entry()
			this_resolution_form = form.image_resolution_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution
			this_resolution_form.atlas_name.data = atlas_name_this_resolution
			this_resolution_form.ventral_up.data = 0

			''' Now go and add the channel subforms to the image resolution form '''
			for jj in range(len(dorsal_channel_list)):
				channel_content = dorsal_channel_list[jj]
				this_channel_name = channel_content['channel_name']
				logger.debug("Adding subform for channel:")
				logger.debug(this_channel_name)
				channel_contents_lists[resolution_list_index].append(channel_content)
				this_resolution_form.channel_forms.append_entry()
				this_channel_form = this_resolution_form.channel_forms[-1]
				this_channel_form.channel_name.data = this_channel_name
				this_channel_form.ventral_up.data = 0

				""" figure out the channel purposes """
				used_imaging_modes = []
				for imaging_mode in current_app.config['IMAGING_MODES']:
					if channel_content[imaging_mode]:
						used_imaging_modes.append(imaging_mode)
				channel_purposes_str = ', '.join(mode for mode in used_imaging_modes)
				if 'registration' in channel_purposes_str:
					no_registration=False
				this_channel_form.channel_purposes_str.data = channel_purposes_str
			resolution_list_index+=1
		if ventral_channel_contents:
			logger.debug("Have ventral up channels")
			processing_resolution_request_content = processing_resolution_request_contents & \
			 f'image_resolution="{this_image_resolution}"' & 'ventral_up=1'
			atlas_name_this_resolution = processing_resolution_request_content.fetch1('atlas_name') 
			ventral_channel_list = ventral_channel_contents.fetch(as_dict=True)
			channel_contents_lists.append([])
			form.image_resolution_forms.append_entry()
			this_resolution_form = form.image_resolution_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution
			this_resolution_form.atlas_name.data = atlas_name_this_resolution
			this_resolution_form.ventral_up.data = 1

			''' Now go and add the channel subforms to the image resolution form '''
			for jj in range(len(ventral_channel_list)):
				channel_content = ventral_channel_list[jj]
				this_channel_name = channel_content['channel_name']
				logger.debug("Adding subform for channel:")
				logger.debug(this_channel_name)
				channel_contents_lists[resolution_list_index].append(channel_content)
				this_resolution_form.channel_forms.append_entry()
				this_channel_form = this_resolution_form.channel_forms[-1]
				this_channel_form.channel_name.data = this_channel_name
				this_channel_form.ventral_up.data = 1

				""" figure out the channel purposes """
				used_imaging_modes = []
				for imaging_mode in current_app.config['IMAGING_MODES']:
					if channel_content[imaging_mode]:
						used_imaging_modes.append(imaging_mode)
				channel_purposes_str = ', '.join(mode for mode in used_imaging_modes)
				if 'registration' in channel_purposes_str:
					no_registration=False
				this_channel_form.channel_purposes_str.data = channel_purposes_str
			resolution_list_index+=1
	# logger.debug("Form going into GET request is:")
	# logger.debug(form.data)
	if processing_progress != 'incomplete':
		logger.info(f"Processing is currently {processing_progress} but accessing the processing entry page anyway")
		flash(f"Processing is {processing_progress} for this sample. "
			"This page is read only and hitting submit will do nothing",'warning')
	data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
	return render_template('processing/processing_entry.html',
		processing_request_number=processing_request_number,
		no_registration=no_registration,
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
	logger.info(f"{session['user']} accessed new processing request form")
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
					processing_resolution_insert_dict['image_resolution'] = this_image_resolution
					processing_resolution_insert_dict['atlas_name'] = form_resolution_dict['atlas_name']
					processing_resolution_insert_dict['notes_from_processing'] = form.data['notes_from_processing']
					processing_resolution_insert_list.append(processing_resolution_insert_dict)
					""" Make processing path on /jukebox """
					processing_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
					username,request_name,sample_name,f'imaging_request_{imaging_request_number}',
					'output',f'processing_request_{new_processing_request_number}',
					f'resolution_{this_image_resolution}')
					mymkdir(processing_path_to_make)

				logger.info("ProcessingResolutionRequest() insert:")
				logger.info(processing_resolution_insert_list)
				logger.info("")
				db_lightsheet.Request.ProcessingResolutionRequest().insert1(processing_resolution_insert_dict)


			flash("Processing request successfully submitted. ","success")
			return redirect(url_for('processing.processing_manager'))
			
		else: # form not validated
			
			logger.debug("Not validated! See error dict below:")
			logger.debug(form.errors)
			logger.debug("")
			flash_str = 'There were errors below. Correct them before proceeding'
			flash(flash_str,'danger')
			""" deal with errors in the image resolution subforms - those
			do not show up in the rendered tables like normal form errors """
			
			for orig_key in form.errors:
				error_list = form.errors[orig_key]
				for item in error_list:
					if isinstance(item,str):
						flash(item,'danger')
					else:
						for key,val in list(item.items()):
							for error_str in val:
								flash(error_str,'danger')
	
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
	
	overview_table_id = 'horizontal_processing_table'
	overview_table = create_dynamic_processing_overview_table(joined_contents,table_id=overview_table_id)

	processing_channel_contents = db_lightsheet.Request.ProcessingChannel() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' & \
			f'processing_request_number={processing_request_number}'
	processing_channel_table = ProcessingChannelTable(processing_channel_contents)
			 # all of the channels for this sample
	return render_template('processing/processing_log.html',overview_table=overview_table,
		processing_channel_table=processing_channel_table)