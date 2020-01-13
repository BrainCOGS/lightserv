from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)
from lightserv import db_lightsheet, mail, cel

from lightserv.main.utils import (logged_in, logged_in_as_clearer,
								  logged_in_as_imager,check_clearing_completed,
								  image_manager,log_http_requests)
from lightserv.imaging.tables import (ImagingTable, dynamic_imaging_management_table,
	SampleTable, ExistingImagingTable)
from .forms import ImagingForm, NewImagingRequestForm
import numpy as np
import datajoint as dj
import re
from datetime import datetime
from flask_mail import Message
import logging
import glob
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/imaging_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

imaging = Blueprint('imaging',__name__)

@imaging.route("/imaging/imaging_manager",methods=['GET','POST'])
@logged_in
@log_http_requests
def imaging_manager(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed imaging manager")
	sort = request.args.get('sort', 'datetime_submitted') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')

	imaging_admins = current_app.config['IMAGING_ADMINS']

	request_contents = db_lightsheet.Request()
	sample_contents = db_lightsheet.Request.Sample()
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch()

	imaging_request_contents = (db_lightsheet.Request.ImagingRequest() \
		* clearing_batch_contents * sample_contents * request_contents).\
		proj('clearer','clearing_progress',
		'imaging_request_date_submitted','imaging_request_time_submitted',
		'imaging_progress','imager','species',
		datetime_submitted='TIMESTAMP(imaging_request_date_submitted,imaging_request_time_submitted)')
	if current_user not in imaging_admins:
		logger.info(f"{current_user} is not an imaging admin."
					 " They can see only entries where they designated themselves as the imager")
		imaging_request_contents = imaging_request_contents & f'imager="{current_user}"'
	
	# ''' First get all entities that are currently being imaged '''
	""" Get all entries currently being imaged """
	contents_being_imaged = imaging_request_contents & 'imaging_progress="in progress"'
	being_imaged_table_id = 'horizontal_being_imaged_table'
	table_being_imaged = dynamic_imaging_management_table(contents_being_imaged,
		table_id=being_imaged_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Next get all entities that are ready to be imaged '''
	contents_ready_to_image = imaging_request_contents & 'clearing_progress="complete"' & \
	 'imaging_progress="incomplete"'
	ready_to_image_table_id = 'horizontal_ready_to_image_table'
	table_ready_to_image = dynamic_imaging_management_table(contents_ready_to_image,
		table_id=ready_to_image_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Now get all entities on deck (currently being cleared) '''
	contents_on_deck = imaging_request_contents & 'clearing_progress!="complete"' & 'imaging_progress!="complete"'
	on_deck_table_id = 'horizontal_on_deck_table'
	table_on_deck = dynamic_imaging_management_table(contents_on_deck,table_id=on_deck_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Finally get all entities that have already been imaged '''
	contents_already_imaged = imaging_request_contents & 'imaging_progress="complete"'
	already_imaged_table_id = 'horizontal_already_imaged_table'
	table_already_imaged = dynamic_imaging_management_table(contents_already_imaged,
		table_id=already_imaged_table_id,
		sort_by=sort,sort_reverse=reverse)
	
	return render_template('imaging/image_management.html',
		table_being_imaged=table_being_imaged,
		table_ready_to_image=table_ready_to_image,table_on_deck=table_on_deck,
		table_already_imaged=table_already_imaged)

@imaging.route("/imaging/imaging_entry/<username>/<request_name>/<sample_name>/<imaging_request_number>",methods=['GET','POST'])
@logged_in
@logged_in_as_imager
@check_clearing_completed
@log_http_requests
def imaging_entry(username,request_name,sample_name,imaging_request_number): 
	form = ImagingForm(request.form)
	form.username.data = username
	form.request_name.data = request_name
	form.sample_name.data = sample_name
	form.imaging_request_number.data = imaging_request_number
	sample_contents = db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' 
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' & \
	 		f'imaging_request_number="{imaging_request_number}"' 
	''' If imaging is already complete (from before), then dont change imaging_progress '''
	imaging_progress = imaging_request_contents.fetch1('imaging_progress')
	
	channel_contents = (db_lightsheet.Request.ImagingChannel() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' & f'imaging_request_number="{imaging_request_number}"')
	channel_content_dict_list = channel_contents.fetch(as_dict=True)

	channel_contents_lists = []
	unique_image_resolutions = sorted(list(set(channel_contents.fetch('image_resolution'))))
	for ii in range(len(unique_image_resolutions)):
		this_image_resolution = unique_image_resolutions[ii]
		image_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
		f'username="{username}" ' & f'request_name="{request_name}" ' & \
		f'sample_name="{sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
		f'image_resolution="{this_image_resolution}" '
		channel_contents_list_this_resolution = (channel_contents & f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
		channel_contents_lists.append([])

		''' Now add the channel subforms to the image resolution form '''
		for jj in range(len(channel_contents_list_this_resolution)):
			channel_content = channel_contents_list_this_resolution[jj]
			channel_contents_lists[ii].append(channel_content)
	overview_dict = imaging_request_contents.fetch1()
	imaging_table = ImagingTable(imaging_request_contents)

	if request.method == 'POST':
		logger.info("Post request")
		if form.validate_on_submit():
			logger.info("form validated")
			imaging_progress = imaging_request_contents.fetch1('imaging_progress')
			
			if imaging_progress == 'complete':
				logger.info("Imaging is already complete so hitting the done button again did nothing")
				return redirect(url_for('imaging.imaging_entry',username=username,
				request_name=request_name,sample_name=sample_name,imaging_request_number=imaging_request_number))
			
			""" loop through the image resolution forms and find all channel entries"""

			""" Loop through the image resolution forms and find all channels in the form  
			and update the existing table entries with the new imaging information """
			

			for form_resolution_dict in form.image_resolution_forms.data:
				subfolder_dict = {}
				image_resolution = form_resolution_dict['image_resolution']
				for form_channel_dict in form_resolution_dict['channel_forms']:
					channel_name = form_channel_dict['channel_name']
					number_of_z_planes = form_channel_dict['number_of_z_planes']
					rawdata_subfolder = form_channel_dict['rawdata_subfolder']
					left_lightsheet_used = form_channel_dict['left_lightsheet_used']
					right_lightsheet_used = form_channel_dict['right_lightsheet_used']
					# logger.debug(left_lightsheet_used)
					# logger.debug(right_lightsheet_used)
					if rawdata_subfolder in subfolder_dict.keys():
						subfolder_dict[rawdata_subfolder].append(channel_name)
					else:
						subfolder_dict[rawdata_subfolder] = [channel_name]
					channel_index = subfolder_dict[rawdata_subfolder].index(channel_name)
					logger.info(f" channel {channel_name} with image_resolution \
						 {image_resolution} has channel_index = {channel_index}")

					""" Now look for the number of z planes in the raw data subfolder on bucket
						and validate that it is the same as the user specified 
					"""
					
					channel_content = channel_contents & f'channel_name="{channel_name}"' & \
					f'image_resolution="{image_resolution}"' & f'imaging_request_number={imaging_request_number}'
					# logger.debug(channel_contents)
					# logger.debug(channel_name)
					# logger.debug(image_resolution)
					# logger.debug(imaging_request_number)
					channel_content_dict = channel_content.fetch1()
					''' Make a copy of the current row in a new dictionary which we will insert '''
					channel_insert_dict = {}
				
					for key,val in channel_content_dict.items():
						channel_insert_dict[key] = val

					''' Now replace (some of) the values in the dict from whatever we 
					get from the form '''
					for key,val in form_channel_dict.items():
						if key in channel_content_dict.keys() and key not in ['channel_name','image_resolution','imaging_request_number']:
							channel_insert_dict[key] = val
							print(key,val)
					channel_insert_dict['imspector_channel_index'] = channel_index
					logger.info("Updating db entry with channel contents:")
					logger.info(channel_insert_dict)
			
					db_lightsheet.Request.ImagingChannel().insert1(channel_insert_dict,replace=True)
				
			correspondence_email = (db_lightsheet.Request() &\
			 f'request_name="{request_name}"').fetch1('correspondence_email')
			path_to_data = f'/jukebox/LightSheetData/lightserv_testing/{username}/{request_name}/\
				{sample_name}/rawdata/imaging_request_number_{imaging_request_number}'
			msg = Message('Lightserv automated email',
			          sender='lightservhelper@gmail.com',
			          recipients=['ahoag@princeton.edu']) # keep it to me while in DEV phase
			msg.body = ('Hello!\n    This is an automated email sent from lightserv, '
						'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
						'The raw data for your request:\n'
						f'request_name: "{request_name}"\n'
						f'sample_name: "{sample_name}"\n'
						f'are now available on bucket here: {path_to_data}')
			# mail.send(msg)
			flash(f"""Imaging is complete. An email has been sent to {correspondence_email} 
				informing them that their raw data is now available on bucket.
				The processing pipeline is now ready to run. ""","success")
			dj.Table._update(imaging_request_contents,'imaging_progress','complete')
			now = datetime.now()
			date = now.strftime('%Y-%m-%d')
			dj.Table._update(imaging_request_contents,'imaging_performed_date',date)
			return redirect(url_for('requests.request_overview',username=username,
				request_name=request_name,sample_name=sample_name))

		else:
			logger.info("Not validated")
			logger.info(form.errors)
			flash_str = 'There were errors below. Correct them before proceeding'
			flash(flash_str,'danger')
			if 'image_resolution_forms' in form.errors:
				for error in form.errors['image_resolution_forms']:
					flash(error,'danger')

	elif request.method == 'GET': # get request
		if imaging_progress == 'complete':
			logger.info("Imaging already complete but accessing the imaging entry page anyway.")
			flash("Imaging is already complete for this sample. "
				"This page is read only and hitting submit will do nothing",'warning')
		else:
			dj.Table._update(imaging_request_contents,'imaging_progress','in progress')
		
		for ii in range(len(unique_image_resolutions)):
			this_image_resolution = unique_image_resolutions[ii]
			image_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
			f'username="{username}" ' & f'request_name="{request_name}" ' & \
			f'sample_name="{sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
			f'image_resolution="{this_image_resolution}" '
			notes_for_imager = image_resolution_request_contents.fetch1('notes_for_imager')
			channel_contents_list_this_resolution = (channel_contents & f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
			while len(form.image_resolution_forms) > 0:
				form.image_resolution_forms.pop_entry()
			form.image_resolution_forms.append_entry()
			this_resolution_form = form.image_resolution_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution
			if notes_for_imager:
				this_resolution_form.notes_for_imager.data = notes_for_imager
			else:
				this_resolution_form.notes_for_imager.data = 'No special notes'
			''' Now add the channel subforms to the image resolution form '''
			for jj in range(len(channel_contents_list_this_resolution)):
				channel_content = channel_contents_list_this_resolution[jj]
				this_resolution_form.channel_forms.append_entry()
				this_channel_form = this_resolution_form.channel_forms[-1]
				this_channel_form.channel_name.data = channel_content['channel_name']
				logger.debug(channel_content)
				this_channel_form.image_resolution.data = channel_content['image_resolution']
				this_channel_form.rawdata_subfolder.data = 'test488'

	return render_template('imaging/imaging_entry.html',form=form,
		channel_contents_lists=channel_contents_lists,
		overview_dict=overview_dict,imaging_table=imaging_table)

@imaging.route("/imaging/new_imaging_request/<username>/<request_name>/<sample_name>/",methods=['GET','POST'])
@logged_in
@log_http_requests
def new_imaging_request(username,request_name,sample_name): 
	""" Route for user to submit a new imaging request to an 
	already existing sample - this takes place after the initial request
	and first imaging round took place. This can sometimes happen if
	someone is new to using the core facility and realizes after their 
	first imaging round that they want a different kind of imaging 
	for the same sample.  """
	logger.info(f"{session['user']} accessed new imaging request form")
	form = NewImagingRequestForm(request.form)

	all_imaging_modes = current_app.config['IMAGING_MODES']

	sample_contents = db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"'								
	
	sample_table = SampleTable(sample_contents)
	channel_contents = (db_lightsheet.Request.ImagingChannel() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"')
	""" figure out the new imaging request number to give the new request """
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' 
	previous_imaging_request_numbers = np.unique(imaging_request_contents.fetch('imaging_request_number'))
	previous_max_imaging_request_number = max(previous_imaging_request_numbers)
	new_imaging_request_number = previous_max_imaging_request_number + 1

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

				connection = db_lightsheet.Request.ImagingRequest.connection
				with connection.transaction:
					""" First handle the ImagingRequest() and ProcessingRequest() entries """
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

					""" ProcessingRequest """
					processing_request_insert_dict = {}
					processing_request_number = 1 # because the imaging request is just now being created there are no processing requests already for this imaging request
					processing_request_insert_dict['request_name'] = request_name
					processing_request_insert_dict['username'] = username 
					processing_request_insert_dict['sample_name'] = sample_name
					processing_request_insert_dict['imaging_request_number'] = new_imaging_request_number
					processing_request_insert_dict['processing_request_number'] = processing_request_number
					processing_request_insert_dict['processing_request_date_submitted'] = date
					processing_request_insert_dict['processing_request_time_submitted'] = time
					processing_request_insert_dict['processing_progress'] = "incomplete"
					""" The user is always the "processor" - i.e. the person
					 who double-checks the processing form and hits GO """
					processing_request_insert_dict['processor'] = username

					logger.info("ImagingRequest() insert:")
					logger.info(imaging_request_insert_dict)
					logger.info("")
					db_lightsheet.Request.ImagingRequest().insert1(imaging_request_insert_dict)

					logger.info("ProcessingRequest() insert:")
					logger.info(processing_request_insert_dict)
					logger.info("")
					db_lightsheet.Request.ProcessingRequest().insert1(processing_request_insert_dict)

					""" Now insert each image resolution/channel combo """
					imaging_resolution_insert_list = []
					processing_resolution_insert_list = []
					channel_insert_list = []
					for resolution_dict in form.image_resolution_forms.data:
						logger.debug(resolution_dict)
						""" imaging entry first """
						imaging_resolution_insert_dict = {}
						imaging_resolution_insert_dict['request_name'] = request_name
						imaging_resolution_insert_dict['username'] = username 
						imaging_resolution_insert_dict['sample_name'] = sample_name
						imaging_resolution_insert_dict['imaging_request_number'] = new_imaging_request_number
						imaging_resolution_insert_dict['image_resolution'] = resolution_dict['image_resolution']
						imaging_resolution_insert_dict['notes_for_imager'] = resolution_dict['notes_for_imager']
						imaging_resolution_insert_list.append(imaging_resolution_insert_dict)
						""" now processing entry """
						processing_resolution_insert_dict = {}
						processing_resolution_insert_dict['request_name'] = request_name
						processing_resolution_insert_dict['username'] = username 
						processing_resolution_insert_dict['sample_name'] = sample_name
						processing_resolution_insert_dict['imaging_request_number'] = new_imaging_request_number
						processing_resolution_insert_dict['processing_request_number'] = processing_request_number
						processing_resolution_insert_dict['image_resolution'] = resolution_dict['image_resolution']
						processing_resolution_insert_dict['notes_for_processor'] = resolution_dict['notes_for_processor']
						processing_resolution_insert_dict['atlas_name'] = resolution_dict['atlas_name']
						processing_resolution_insert_list.append(processing_resolution_insert_dict)
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
										continue # pragma: no cover - used to exclude this line from testing
									channel_insert_dict[key] = val

								channel_insert_list.append(channel_insert_dict)
					
					logger.info('ImagingResolutionRequest() insert:')
					logger.info(imaging_resolution_insert_list)
					db_lightsheet.Request.ImagingResolutionRequest().insert(imaging_resolution_insert_list)		

					logger.info('ProcessingResolutionRequest() insert:')
					logger.info(processing_resolution_insert_list)
					db_lightsheet.Request.ProcessingResolutionRequest().insert(processing_resolution_insert_list)	
					
					logger.info('ImagingChannel() insert:')
					logger.info(channel_insert_list)
					db_lightsheet.Request.ImagingChannel().insert(channel_insert_list)
					flash("Your new imaging request was submitted successfully.", "success")
					return redirect(url_for('requests.all_requests'))
		else:
			logger.debug("Not validated! See error dict below:")
			logger.debug(form.errors)
			logger.debug("")
			flash_str = 'There were errors below. Correct them before proceeding'
			flash(flash_str,'danger')
			""" deal with errors in the image resolution subforms - those
			do not show up in the rendered tables like normal form errors """
			for obj in form.errors['image_resolution_forms']:
				flash(obj,'danger')
	
	existing_imaging_table = ExistingImagingTable(channel_contents)

	return render_template('imaging/new_imaging_request.html',form=form,
		sample_table=sample_table,existing_imaging_table=existing_imaging_table)

