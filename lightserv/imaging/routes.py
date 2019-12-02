from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)
from lightserv import db_lightsheet, mail, cel

from lightserv.main.utils import (logged_in, logged_in_as_clearer,
								  logged_in_as_imager,check_clearing_completed,
								  image_manager)
from lightserv.imaging.tables import (ImagingTable, dynamic_imaging_management_table,
	SampleTable, ExistingImagingTable)
from .forms import ImagingForm, NewImagingRequestForm
import numpy as np
import datajoint as dj
import re
import datetime
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
@image_manager
def imaging_manager(): 
	sort = request.args.get('sort', 'datetime_submitted') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	sample_contents = db_lightsheet.Sample()
	request_contents = db_lightsheet.Request()
	imaging_request_contents = (db_lightsheet.Sample.ImagingRequest() * sample_contents * request_contents).\
		proj('clearing_progress',
		'imaging_request_date_submitted','imaging_request_time_submitted',
		'imaging_progress','imager','species',
		datetime_submitted='TIMESTAMP(imaging_request_date_submitted,imaging_request_time_submitted)')
	logger.info(imaging_request_contents)
	# channel_contents = db_lightsheet.Sample.ImagingChannel()
	# request_contents = db_lightsheet.Request()
	
	# ''' First get all entities that are currently being imaged '''
	""" Get all entries currently being imaged """
	contents_being_imaged = imaging_request_contents & 'imaging_progress="in progress"'
	# logger.info(contents_being_imaged)
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
	# ''' Finally get all entities that have already been imaged '''
	# contents_already_imaged = all_contents_unique_imaging_request_number & 'imaging_progress="complete"'
	# already_imaged_table_id = 'horizontal_already_imaged_table'
	# table_already_imaged = dynamic_imaging_management_table(contents_already_imaged,
	# 	table_id=already_imaged_table_id,
	# 	sort_by=sort,sort_reverse=reverse)
	
	return render_template('imaging/image_management.html',
		table_being_imaged=table_being_imaged,
		table_ready_to_image=table_ready_to_image,table_on_deck=table_on_deck)

@imaging.route("/imaging/imaging_entry/<username>/<request_name>/<imaging_request_number>/<sample_name>",methods=['GET','POST'])
@logged_in
@logged_in_as_imager
@check_clearing_completed
def imaging_entry(username,request_name,sample_name,imaging_request_number): 
	form = ImagingForm(request.form)

	sample_contents = db_lightsheet.Sample() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' 
	imaging_request_contents = db_lightsheet.Sample.ImagingRequest() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' & \
	 		f'imaging_request_number="{imaging_request_number}"' 
	''' If imaging is already complete (from before), then dont change imaging_progress '''
	# imaging_progress = sample_contents.fetch1('imaging_progress')
	# logger.debug(imaging_progress)
	# if imaging_progress == 'complete':
	# 	logger.info("Imaging already complete but accessing the imaging entry page anyway")
	# 	flash("Imaging is already complete for this sample. "
	# 		"This page is read only and hitting submit will do nothing",'warning')
	# else:
	# 	dj.Table._update(sample_contents,'imaging_progress','in progress')

	channel_contents = (db_lightsheet.Sample.ImagingChannel() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"' & f'imaging_request_number="{imaging_request_number}"')
	channel_content_dict_list = channel_contents.fetch(as_dict=True)
	if request.method == 'POST':
		logger.info("Post request")
		if form.validate_on_submit():
			logger.info("form validated")
			imaging_progress = imaging_request_contents.fetch1('imaging_progress')
			
			if imaging_progress == 'complete':
				logger.info("Imaging is already complete so hitting the done button again did nothing")
				return redirect(url_for('requests.request',username=username,
				request_name=request_name,sample_name=sample_name))
			
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
					if rawdata_subfolder in subfolder_dict.keys():
						subfolder_dict[rawdata_subfolder].append(channel_name)
					else:
						subfolder_dict[rawdata_subfolder] = [channel_name]
					channel_index = subfolder_dict[rawdata_subfolder].index(channel_name)
					logger.info(f" channel {channel_name} with image_resolution {image_resolution} has channel_index = {channel_index}")
					""" Now look for the number of z planes in the raw data subfolder on bucket
					 and validate that it is the same as the user specified """
					# rawdata_fullpath = os.path.join(current_app.config['RAWDATA_ROOTPATH'],username,
					# 	request_name,sample_name,rawdata_subfolder) 
					# number_of_z_planes_found = len(glob.glob(rawdata_fullpath + f'/*RawDataStack*Filter000{channel_index}*'))
					# if number_of_z_planes_found != number_of_z_planes:
					# 	flash(f"You entered that for channel: {channel_name} there should be {number_of_z_planes} z planes, "
					# 		  f"but found {number_of_z_planes_found} in raw data folder: "
					# 		  f"{rawdata_fullpath}","danger")
					# 	return redirect(url_for('imaging.imaging_entry',username=username,
					# 		request_name=request_name,sample_name=sample_name))
					channel_content = channel_contents & f'channel_name="{channel_name}"' & \
					f'image_resolution="{image_resolution}"' & f'imaging_request_number={imaging_request_number}'
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
					channel_insert_dict['imspector_channel_index'] = channel_index
					logger.info("Updating db entry with channel contents:")
					logger.info(channel_insert_dict)
			
					db_lightsheet.Sample.ImagingChannel().insert1(channel_insert_dict,replace=True)
				
			correspondence_email = (db_lightsheet.Request() &\
			 f'request_name="{request_name}"').fetch1('correspondence_email')
			path_to_data = f'/jukebox/LightSheetData/lightserv_testing/{username}/{request_name}/{sample_name}'
			msg = Message('Lightserv automated email',
			          sender='lightservhelper@gmail.com',
			          recipients=['ahoag@princeton.edu']) # keep it to me while in DEV phase
			msg.body = ('Hello!\n    This is an automated email sent from lightserv, the Light Sheet Microscopy portal. '
						'The raw data for your experiment:\n'
						f'request_name: "{request_name}"\n'
						f'sample_name: "{sample_name}"\n'
						f'are now available on bucket here: {path_to_data}')
			# mail.send(msg)
			flash(f"""Imaging is complete. An email has been sent to {correspondence_email} 
				informing them that their raw data is now available on bucket.
				The processing pipeline is now ready to run. ""","success")
			# dj.Table._update(sample_contents,'imaging_progress','complete')

			return redirect(url_for('requests.request_overview',username=username,
				request_name=request_name,sample_name=sample_name))

		else:
			logger.info("Not validated")
			logger.info(form.errors)
			for channel in form.channels:
				print(channel.tiling_scheme.errors)
	elif request.method == 'GET': # get request
		channel_contents_lists = []

		unique_image_resolutions = sorted(list(set(channel_contents.fetch('image_resolution'))))
		for ii in range(len(unique_image_resolutions)):
			this_image_resolution = unique_image_resolutions[ii]
			channel_contents_list_this_resolution = (channel_contents & f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
			channel_contents_lists.append([])
			form.image_resolution_forms.append_entry()
			this_resolution_form = form.image_resolution_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution
			''' Now add the channel subforms to the image resolution form '''
			for jj in range(len(channel_contents_list_this_resolution)):
				channel_content = channel_contents_list_this_resolution[jj]
				channel_contents_lists[ii].append(channel_content)
				this_resolution_form.channel_forms.append_entry()
				this_channel_form = this_resolution_form.channel_forms[-1]
				this_channel_form.channel_name.data = channel_content['channel_name']
				this_channel_form.image_resolution.data = channel_content['image_resolution']

	overview_dict = imaging_request_contents.fetch1()
	imaging_table = ImagingTable(imaging_request_contents)

	return render_template('imaging/imaging_entry.html',form=form,
		channel_contents_lists=channel_contents_lists,
		overview_dict=overview_dict,imaging_table=imaging_table)

@imaging.route("/imaging/imaging_entry/<username>/<request_name>/<sample_name>/new_imaging_request",methods=['GET','POST'])
@logged_in
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

	sample_contents = db_lightsheet.Sample() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"'								
	sample_table = SampleTable(sample_contents)
	channel_contents = (db_lightsheet.Sample.ImagingChannel() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"')

	if request.method == 'POST':
		if form.validate_on_submit():
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
				""" figure out the new imaging request number to give the new request """
				previous_imaging_request_numbers = np.unique(channel_contents.fetch('imaging_request_number'))
				previous_max_imaging_request_number = max(previous_imaging_request_numbers)
				new_imaging_request_number = previous_max_imaging_request_number + 1
				""" Now insert each image resolution/channel combo """
				channel_insert_list = []
				for resolution_dict in form.image_resolution_forms.data:
					logger.debug(resolution_dict)
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
							channel_insert_dict['atlas_name'] = resolution_dict['atlas_name']
							channel_insert_dict['request_name'] = request_name	
							channel_insert_dict['username'] = username
							channel_insert_dict['sample_name'] = sample_name
							channel_insert_dict['image_resolution'] = resolution_dict['image_resolution']
							for key,val in imaging_channel_dict.items(): 
								if key == 'csrf_token':
									continue
								channel_insert_dict[key] = val

							channel_insert_list.append(channel_insert_dict)

					logger.info(channel_insert_list)
						
				
				logger.info('channel insert:')
				logger.info(channel_insert_list)
				db_lightsheet.Sample.ImagingChannel().insert(channel_insert_list)
				flash("Imaging request submitted successfully.", "success")
				return redirect(url_for('main.home'))
		else:
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
	existing_imaging_table = ExistingImagingTable(channel_contents)

	return render_template('imaging/new_imaging_request.html',form=form,
		sample_table=sample_table,existing_imaging_table=existing_imaging_table)

