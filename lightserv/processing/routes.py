from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)
from lightserv.processing.forms import StartProcessingForm, NewProcessingRequestForm
from lightserv.processing.tables import (create_dynamic_channels_table_for_processing,
	dynamic_processing_management_table,ExistingProcessingTable)
from lightserv import db_lightsheet
from lightserv.main.utils import (logged_in, table_sorter,logged_in_as_processor,
	check_clearing_completed,check_imaging_completed)
from lightserv import cel,mail
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
	
	sample_contents = db_lightsheet.Sample()
	request_contents = db_lightsheet.Request()
	imaging_request_contents = db_lightsheet.Sample.ImagingRequest()
	processing_request_contents = (db_lightsheet.Sample.ProcessingRequest() * \
	 	sample_contents * request_contents * imaging_request_contents).\
			proj('clearing_progress','processing_request_date_submitted','processing_request_time_submitted',
			'imaging_progress','imager','species','processing_progress','processor',
			datetime_submitted='TIMESTAMP(processing_request_date_submitted,processing_request_time_submitted)')

	if current_user not in processing_admins:
		processing_request_contents = processing_request_contents & f'processor="{current_user}"'
	
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
@check_clearing_completed
@check_imaging_completed
# @logged_in_as_processor
def processing_entry(username,request_name,sample_name,imaging_request_number,processing_request_number):
	""" Route for the person assigned as data processor for a sample 
	to start the data processing. """
	logger.info(f"{session['user']} accessed start_processing route")
	
	sample_contents = (db_lightsheet.Sample() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"')
	sample_dict = sample_contents.fetch1()
	image_resolution_request_contents = db_lightsheet.Sample.ImageResolutionRequest() & f'request_name="{request_name}"' & \
				f'username="{username}"' & f'sample_name="{sample_name}"' & \
				f'imaging_request_number="{imaging_request_number}"'
	
	processing_request_contents = db_lightsheet.Sample.ProcessingRequest() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			 f'imaging_request_number="{imaging_request_number}"' & \
			 f'processing_request_number="{processing_request_number}"'
	logger.debug(processing_request_contents)
	channel_contents = db_lightsheet.Sample.ImagingChannel() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' # all of the channels for this sample
	channel_content_dict_list = channel_contents.fetch(as_dict=True)

	joined_contents = sample_contents * image_resolution_request_contents * processing_request_contents
	
	overview_table_id = 'horizontal_procsesing_table'
	overview_table = create_dynamic_channels_table_for_processing(joined_contents,table_id=overview_table_id)
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
			logger.info("updating sample contents from form data")
			dj.Table._update(sample_contents,'notes_from_processing',form.notes_from_processing.data)
			""" loop through and update the atlas to be used based on what the user supplied """
			for form_resolution_dict in form.image_resolution_forms.data:
				this_image_resolution = form_resolution_dict['image_resolution']
				logger.info(this_image_resolution)
				this_image_resolution_content = image_resolution_request_contents & \
				f'image_resolution="{this_image_resolution}"'
				logger.debug(this_image_resolution_content)
				atlas_name = form_resolution_dict['atlas_name']
				dj.Table._update(this_image_resolution_content,'atlas_name',atlas_name)

			logger.info(f"Starting step0 without celery for testing")
			# run_step0.delay(username=username,request_name=request_name,sample_name=sample_name)
			''' Update the processing progress before starting the jobs on spock 
			to avoid a race condition (the pipeline also updates the processing_progress flag if it fails or succeeds) '''
			dj.Table._update(processing_request_contents,'processing_progress','running')
			try:
				run_spock_pipeline(username=username,request_name=request_name,sample_name=sample_name,
					imaging_request_number=imaging_request_number,
					processing_request_number=processing_request_number)
				flash('Your data processing has begun. You will receive an email \
				when the first steps are completed.','success')
			except:
				logger.info("Pipeline initialization failed. Updating processing progress to 'failed' ")
				dj.Table._update(processing_request_contents,'processing_progress','failed')
				return redirect('errors.error_500')

			
			return redirect(url_for('main.home'))

	elif request.method == 'GET': # get request
		channel_contents_lists = []
		while len(form.image_resolution_forms) > 0:
			form.image_resolution_forms.pop_entry()
		""" Figure out the unique number of image resolutions """
		unique_image_resolutions = sorted(list(set(channel_contents.fetch('image_resolution'))))
		for ii in range(len(unique_image_resolutions)):
			this_image_resolution = unique_image_resolutions[ii]
			image_resolution_request_content = db_lightsheet.Sample.ImageResolutionRequest() & f'request_name="{request_name}"' & f'username="{username}"' & f'sample_name="{sample_name}"' & f'imaging_request_number="{imaging_request_number}"' & f'image_resolution="{this_image_resolution}"'

			channel_contents_list_this_resolution = (channel_contents & f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
			channel_contents_lists.append([])
			form.image_resolution_forms.append_entry()
			this_resolution_form = form.image_resolution_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution
			this_resolution_form.atlas_name.data = image_resolution_request_content.fetch1('atlas_name')

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
	return render_template('processing/processing_entry.html',
		channel_contents_lists=channel_contents_lists,
		sample_dict=sample_dict,form=form,overview_table=overview_table)	

@processing.route("/processing/new_processing_request/<username>/<request_name>/<sample_name>/<imaging_request_number>",methods=['GET','POST'])
@logged_in
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

	sample_contents = db_lightsheet.Sample() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"'								
	sample_dict = sample_contents.fetch1()
	# sample_table = SampleTable(sample_contents)
	channel_contents = (db_lightsheet.Sample.ImagingChannel() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"')
	""" figure out the new processing request number to give the new request """
	processing_request_contents = db_lightsheet.Sample.ProcessingRequest() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' & \
	 		f'imaging_request_number="{imaging_request_number}"' 
	previous_processing_request_numbers = np.unique(processing_request_contents.\
		fetch('processing_request_number'))
	previous_max_processing_request_number = max(previous_processing_request_numbers)
	new_processing_request_number = previous_max_processing_request_number + 1

	if request.method == 'POST':
		if form.validate_on_submit():
			logger.info("validated")
			""" figure out which button was pressed """
			submit_keys = [x for x in form._fields.keys() if 'submit' in x and form[x].data == True]
			if len(submit_keys) == 1: # submit key was either sample setup or final submit button
				submit_key = submit_keys[0]
			if submit_key == 'new_image_resolution_form_submit':
				logger.info("resolution table setup button pressed")		
				image_resolution_forsetup = form.data['image_resolution_forsetup']
				image_resolution_forms = form.image_resolution_forms
				image_resolution_forms.append_entry()
				resolution_table_index = len(image_resolution_forms.data)-1
				""" now pick out which form we currently just made """
				image_resolution_form = image_resolution_forms[resolution_table_index]
				image_resolution_form.image_resolution.data = image_resolution_forsetup
				
				column_name = f'image_resolution_forms-{resolution_table_index}-channels-0-registration'
				# Now make 4 new channel formfields and set defaults and channel names
				for x in range(4):
					channel_name = current_app.config['IMAGING_CHANNELS'][x]
					image_resolution_form.channels[x].channel_name.data = channel_name
					# Make the default for channel 488 to be 1.3x imaging with registration checked
					if channel_name == '488' and image_resolution_forsetup == "1.3x":
						image_resolution_form.channels[x].registration.data = 1
			elif submit_key == 'submit':

				connection = db_lightsheet.Sample.ImagingRequest.connection
				with connection.transaction:
					""" First insert the ImagingRequest() entry """
					now = datetime.now()
					date = now.strftime("%Y-%m-%d")
					time = now.strftime("%H:%M:%S") 
					imaging_request_insert_dict = {}
					imaging_request_insert_dict['request_name'] = request_name
					imaging_request_insert_dict['username'] = username 
					imaging_request_insert_dict['sample_name'] = sample_name
					imaging_request_insert_dict['imaging_request_number'] = new_imaging_request_number
					imaging_request_insert_dict['imaging_request_date_submitted'] = date
					imaging_request_insert_dict['imaging_request_time_submitted'] = time
					imaging_request_insert_dict['imaging_progress'] = "incomplete" # when it is submitted it starts out as incomplete
					if form.self_imaging.data == True:
						imaging_request_insert_dict['imager'] = username
					logger.info("ImagingRequest() insert:")
					logger.info(imaging_request_insert_dict)
					logger.info("")
					db_lightsheet.Sample.ImagingRequest().insert1(imaging_request_insert_dict)

					""" Now insert each image resolution/channel combo """
					resolution_insert_list = []
					channel_insert_list = []
					for resolution_dict in form.image_resolution_forms.data:
						logger.debug(resolution_dict)
						resolution_insert_dict = {}
						resolution_insert_dict['request_name'] = request_name
						resolution_insert_dict['username'] = username 
						resolution_insert_dict['sample_name'] = sample_name
						resolution_insert_dict['imaging_request_number'] = new_imaging_request_number
						resolution_insert_dict['image_resolution'] = resolution_dict['image_resolution']
						resolution_insert_dict['notes_for_imager'] = resolution_dict['notes_for_imager']
						resolution_insert_dict['notes_for_processor'] = resolution_dict['notes_for_processor']
						resolution_insert_dict['notes_for_processor'] = resolution_dict['notes_for_processor']
						resolution_insert_dict['atlas_name'] = resolution_dict['atlas_name']
						resolution_insert_list.append(resolution_insert_dict)
						""" Now loop through channels and make insert dict for each """
						for imaging_channel_dict in resolution_dict['channels']:
							logger.debug(imaging_channel_dict)
							""" The way to tell which channels were picked is to see 
							which have at least one imaging mode selected """
							used_imaging_modes = [key for key in all_imaging_modes if imaging_channel_dict[key] == True]
							if not any(used_imaging_modes):
								continue
							else:
								channel_insert_dict = {}
								""" When they submit this request form it is always for the first time
								 for this combination of request_name,sample_name,channel_name,image_resolution """
								channel_insert_dict['imaging_request_number'] = new_imaging_request_number 
								channel_insert_dict['image_resolution'] = resolution_dict['image_resolution'] 
								channel_insert_dict['request_name'] = request_name	
								channel_insert_dict['username'] = username
								channel_insert_dict['sample_name'] = sample_name
								for key,val in imaging_channel_dict.items(): 
									if key == 'csrf_token':
										continue
									channel_insert_dict[key] = val

								channel_insert_list.append(channel_insert_dict)
					
					logger.info('ImageResolutionRequest() insert:')
					logger.info(resolution_insert_list)
					db_lightsheet.Sample.ImageResolutionRequest().insert(resolution_insert_list)		
					
					logger.info('ImagingChannel() insert:')
					logger.info(channel_insert_list)
					db_lightsheet.Sample.ImagingChannel().insert(channel_insert_list)
					flash("Imaging request submitted successfully.", "success")
					return redirect(url_for('main.home'))
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
			image_resolution_request_content = db_lightsheet.Sample.ImageResolutionRequest() & f'request_name="{request_name}"' & f'username="{username}"' & f'sample_name="{sample_name}"' & f'imaging_request_number="{imaging_request_number}"' & f'image_resolution="{this_image_resolution}"'

			channel_contents_list_this_resolution = (channel_contents & f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
			channel_contents_lists.append([])
			form.image_resolution_forms.append_entry()
			this_resolution_form = form.image_resolution_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution
			this_resolution_form.atlas_name.data = image_resolution_request_content.fetch1('atlas_name')

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
	existing_processing_table = ExistingProcessingTable(channel_contents)

	return render_template('processing/new_processing_request.html',form=form,
		existing_processing_table=existing_processing_table,
		channel_contents_lists=channel_contents_lists,sample_dict=sample_dict)

# @cel.task()
def run_spock_pipeline(username,request_name,sample_name,imaging_request_number,processing_request_number):
	""" An asynchronous celery task (runs in a background process) which runs step 0 
	in the light sheet pipeline -- i.e. makes the parameter dictionary pickle file
	and grabs a bunch of metadata from the raw files to store in the database.  
	"""
	atlas_dict = current_app.config['ATLAS_NAME_FILE_DICTIONARY']
	atlas_annotation_dict = current_app.config['ATLAS_ANNOTATION_FILE_DICTIONARY']
	now = datetime.now()
	logger.info("In step 0")
	import tifffile
	from xml.etree import ElementTree as ET 
	
	''' Fetch the processing params from the table to run the code '''
	sample_contents = db_lightsheet.Sample() & f'username="{username}"' \
	& f'request_name="{request_name}"'  & f'sample_name="{sample_name}"'
	
	all_channel_contents = db_lightsheet.Sample.ImagingChannel() & f'username="{username}"' \
	& f'request_name="{request_name}"'  & f'sample_name="{sample_name}"' & \
	f'imaging_request_number="{imaging_request_number}"'
	channel_content_dict_list = all_channel_contents.fetch(as_dict=True)
	sample_contents_dict = sample_contents.fetch1() 
	sample_basepath = raw_basepath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
		request_name,sample_name)
	raw_basepath = os.path.join(sample_basepath,'rawdata')

	""" Can now go in and find the z=0 plane 
	which contains the metadata for each channel """

	""" Loop through the channels in sorted order of channel_name
	and figure out which z=0 plane is which within a directory
	because there can be more than one if multi-channel imaging 
	was performed """

	all_imaging_modes = current_app.config['IMAGING_MODES']
	connection = db_lightsheet.Sample.connection
	with connection.transaction:
		unique_image_resolutions = sorted(list(set(all_channel_contents.fetch('image_resolution'))))
		for image_resolution in unique_image_resolutions:
			this_image_resolution_content = db_lightsheet.Sample.ImageResolutionRequest() & \
			 f'request_name="{request_name}"' & f'username="{username}"' & \
			 f'sample_name="{sample_name}"' & f'imaging_request_number="{imaging_request_number}"' & \
			 f'image_resolution="{image_resolution}"'
			atlas_name = this_image_resolution_content.fetch1('atlas_name')
			atlas_file = atlas_dict[atlas_name]
			atlas_annotation_file = atlas_annotation_dict[atlas_name]

			channel_contents_this_resolution = \
				(all_channel_contents & f'image_resolution="{image_resolution}"')
			channel_contents_list_this_resolution = channel_contents_this_resolution.fetch(as_dict=True)

			""" Now find the channels belonging to the same rawdata_subfolder so I can  
			run the multi-imaging channels together in the code """
			unique_rawdata_subfolders = list(set(channel_contents_this_resolution.fetch('rawdata_subfolder')))
			for rawdata_subfolder in unique_rawdata_subfolders:
				rawdata_fullpath = os.path.join(raw_basepath,rawdata_subfolder)

				""" set up the parameter dictionary """
				param_dict = {}
				param_dict['systemdirectory'] = '/jukebox'
				output_directory = os.path.join(sample_basepath,'output',rawdata_subfolder)
				param_dict['outputdirectory'] = output_directory
				param_dict['blendtype'] = 'sigmoidal' # no exceptions
				param_dict['intensitycorrection'] = True # no exceptions
				param_dict['rawdata'] = True # no exceptions
				param_dict['AtlasFile'] = atlas_file
				param_dict['annotationfile'] = atlas_annotation_file

				""" figure out the resize factor based on resolution """
				if image_resolution == '1.3x':
					resizefactor = 3
					x_scale, y_scale = 5.0,5.0
				elif image_resolution == '4x':
					resizefactor = 5
					x_scale, y_scale = 1.63,1.63
				else:
					sys.exit("There was a problem finding the resizefactor")
				param_dict['resizefactor'] = resizefactor
				param_dict['finalorientation'] = ("2","1","0") # hardcoded for now but will need to be captured from the user 
				""" grab the metadata """
				# logger.info(f"finding metadata for channel {channel_name}")
					
				""" First find the z=0 plane for this channel """

				# ''' Always look in the Filter0000 z=0 file for the full metadata 
				# since it holds the info for the Filter0001, Filter00002, etc... files as well and 
				# the metadata in the z=0 planes for the Filter0001, ... files does not have the 
				# necessary information '''
				# z0_plane_path = glob.glob(rawdata_fullpath + \
				# 	f'/*RawDataStack*C00*Filter0000.ome.tif')[0] # C00 just means left lightsheet which should always be there
				# logger.info(f"Found Z=0 Filter0000 file: {z0_plane_path}")
				# """ Extract metadata """
				# with tifffile.TiffFile(z0_plane_path) as tif:
				# 	tags = tif.pages[0].tags
				# xml_description=tags['ImageDescription'].value

				# root = ET.fromstring(xml_description)

				# ''' NA '''
				# custom_attributes = root[-1]
				# prop_array = custom_attributes[0]
				# for child in prop_array:
				# 	if 'UltraII_Na_Value' in child.tag:
				# 		NA = float(child.attrib['Value'])
				# 		processing_insert_dict['numerical_aperture'] = NA

				# ''' pixel type '''
				# image_tag = root[2]
				# pixel_tag = image_tag[2]
				# pixel_dict = pixel_tag.attrib
				# pixel_type = pixel_dict['PixelType']
				# dj.Table._update(this_channel_content,'pixel_type',pixel_type)
				# # processing_insert_dict['pixel_type'] = pixel_type

				# ''' xyz_scale '''
				# x_scale = int(float(pixel_dict['PhysicalSizeX']))
				# y_scale = int(float(pixel_dict['PhysicalSizeY']))
				# z_scale = int(float(pixel_dict['PhysicalSizeZ']))
				# param_dict['xyz_scale'] = (x_scale,y_scale,z_scale)

				# ''' imspector version '''
				# try:
				# 	custom_attributes_image = image_tag[-1]
				# 	version_tag = [child for child in custom_attributes_image if 'ImspectorVersion' in child.tag][0]
				# 	imspector_version = version_tag.attrib['ImspectorVersion']
				# 	processing_insert_dict['imspector_version'] = imspector_version,	
				# except:
				# 	pass # do nothing. Those values will stay NULL
				# ''' Store all of the metadata as an xml string for later access if needed '''
				# processing_insert_dict['metadata_xml_string'] = xml_description			

				""" Loop through the channels themselves to make the input dictionary """
				inputdictionary = {}
				inputdictionary[rawdata_fullpath] = []
				channel_contents_this_subfolder = channel_contents_this_resolution & \
				 f'rawdata_subfolder="{rawdata_subfolder}"'
				channel_contents_dict_list_this_subfolder = channel_contents_this_subfolder.fetch(as_dict=True)
				for channel_dict in channel_contents_dict_list_this_subfolder:		
					channel_name = channel_dict['channel_name']
					channel_index = channel_dict['imspector_channel_index'] 
					processing_insert_dict = {'username':username,'request_name':request_name,
					'sample_name':sample_name,'imaging_request_number':imaging_request_number,
					'processing_request_number':processing_request_number,
					'image_resolution':image_resolution,'channel_name':channel_name,
					'intensity_correction':True,'datetime_processing_started':now}

					channel_imaging_modes = [key for key in all_imaging_modes if channel_dict[key] == True]
					this_channel_content = all_channel_contents & f'channel_name="{channel_name}"'
					logger.info("This channel content")
					logger.info(this_channel_content)
					""" grab the tiling, number of z planes info from the first entry since it has to be the same for all 
					channels in the same rawdata_subfolder"""
					if channel_index == 0:
						tiling_scheme,tiling_overlap,z_step = this_channel_content.fetch1('tiling_scheme','tiling_overlap','z_step')
						param_dict['tiling_overlap'] = tiling_overlap
						if tiling_scheme != '1x1':
							stitching_method = 'terastitcher'
						else:
							stitching_method = 'blending'
						param_dict['stitchingmethod'] = stitching_method
						
					""" Fill inputdictionary """

					if 'registration' in channel_imaging_modes:
						lightsheet_channel_str = 'regch'
					elif 'injection_detection' in channel_imaging_modes:
						lightsheet_channel_str = 'injch'
					elif 'probe_detection' in channel_imaging_modes:
						lightsheet_channel_str = 'injch'
					elif 'cell_detection' in channel_imaging_modes:
						lightsheet_channel_str = 'cellch'
					else:
						lightsheet_channel_str = 'gench'
					inputdictionary[rawdata_fullpath].append([lightsheet_channel_str,str(channel_index).zfill(2)])

					processing_insert_dict['lightsheet_channel_str'] = lightsheet_channel_str
					now = datetime.now()
					processing_insert_dict['datetime_processing_started'] = now
					logger.info("Inserting into ProcessingChannel()")
					logger.info(processing_insert_dict)
					db_lightsheet.Sample.ProcessingChannel().insert1(processing_insert_dict,replace=True)

				param_dict['inputdictionary'] = inputdictionary
				xyz_scale = (x_scale,y_scale,z_step)
				param_dict['xyz_scale'] = xyz_scale
				param_dict['slurmjobfactor'] = 50
				logger.info(param_dict)
				""" Prepare insert to processing db table """
				
				""" Now write the pickle file with the parameter dictionary """	
				try:
				    os.makedirs(output_directory)
				except OSError as exc: 
				    if exc.errno == errno.EEXIST and os.path.isdir(output_directory):
				        pass
				logger.info(f"Made directory: {output_directory}")
				pickle_fullpath = output_directory + '/param_dict.p'
				with open(pickle_fullpath,'wb') as pkl_file:
					pickle.dump(param_dict,pkl_file)
				logger.info(f"wrote pickle file: {pickle_fullpath}")

				""" Now run step 0 in the code via paramiko """
				hostname = 'spock.pni.princeton.edu'

				command = """cd %s;sbatch --export=output_directory='%s' main.sh """ % \
				(current_app.config['PROCESSING_CODE_DIR'],output_directory)
				port = 22
				try:
					client = paramiko.SSHClient()
					client.load_system_host_keys()
					client.set_missing_host_key_policy(paramiko.WarningPolicy)
					
					client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)

					stdin, stdout, stderr = client.exec_command(command)
					print(stdout.read(),stderr.read())

				finally:
					client.close()
	return "success"