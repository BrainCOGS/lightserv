from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)
from werkzeug import MultiDict
from lightserv import db_lightsheet, cel, smtp_connect

from lightserv.main.utils import (logged_in, logged_in_as_clearer,
								  logged_in_as_imager,check_clearing_completed,
								  image_manager,log_http_requests,mymkdir,
								  check_imaging_completed)
from lightserv.imaging.tables import (ImagingTable, dynamic_imaging_management_table,
	SampleTable, ExistingImagingTable, ImagingChannelTable,ImagingBatchTable)
from .forms import (ImagingForm, NewImagingRequestForm, ImagingSetupForm,
	ImagingBatchForm)
from . import tasks
from lightserv.main.tasks import send_email
import numpy as np
import datajoint as dj
import re
from datetime import datetime, timedelta
import logging
import glob
import os
from PIL import Image

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
	imaging_batch_contents = db_lightsheet.Request.ImagingBatch()
	# imaging_channel_contents = db_lightsheet.Request.ImagingChannel()

	imaging_request_contents = (clearing_batch_contents * request_contents * imaging_batch_contents).\
		proj('clearer','clearing_progress',
		'imaging_request_date_submitted','imaging_request_time_submitted',
		'imaging_progress','imager','species','number_in_imaging_batch',
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
	# contents_ready_to_image = [x for x in grouped_imaging_results \
	# 	if x['clearing_progress']=='complete' and x['imaging_progress'] == 'incomplete']
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

@imaging.route("/imaging/imaging_batch_entry/<username>/<request_name>/<imaging_batch_number>",
	methods=['GET','POST'])
@logged_in
@log_http_requests
def imaging_batch_entry(username,request_name,imaging_batch_number): 
	""" Route for handling form data entered for imaging 
	samples in batch entry form
	"""
	current_user = session['user']
	logger.info(f"{current_user} accessed imaging_batch_entry")

	form = ImagingBatchForm(request.form)
	form_id = '_'.join([username,request_name,'imaging_batch',str(imaging_batch_number)]) 
	rawdata_rootpath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
		username,request_name)
	imaging_request_number = 1 # TODO - make this variable to allow follow up imaging requests
	sample_contents = db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'imaging_batch_number={imaging_batch_number}' 
	sample_dict_list = sample_contents.fetch(as_dict=True)

	""" Figure out how many samples in this imaging batch """
	imaging_batch_restrict_dict = dict(userame=username,request_name=request_name,
		imaging_batch_number=imaging_batch_number)
	imaging_batch_contents = db_lightsheet.Request.ImagingBatch() & imaging_batch_restrict_dict
	number_in_batch = imaging_batch_contents.fetch1('number_in_imaging_batch')
	
	imaging_progress = imaging_batch_contents.fetch1('imaging_progress')

	""" Figure out which samples are already imaged """
	imaging_request_contents = (db_lightsheet.Request.ImagingRequest() * sample_contents)

	samples_imaging_progress_dict = {x['sample_name']:x['imaging_progress'] for x in imaging_request_contents.fetch(
		as_dict=True)}
	
	""" Assemble the list of resolution/channel dicts for filling out the 
	batch forms """
	first_sample_dict = sample_contents.fetch(as_dict=True,limit=1)[0]
	first_sample_name = first_sample_dict['sample_name']	
	channel_contents_all_samples = (db_lightsheet.Request.ImagingChannel() & f'request_name="{request_name}"' & \
			f'username="{username}"' )
	batch_channel_contents = channel_contents_all_samples & f'sample_name="{first_sample_name}"'

	batch_unique_image_resolutions = sorted(set(batch_channel_contents.fetch('image_resolution')))
	
	overview_dict = imaging_batch_contents.fetch1()
	imaging_table = ImagingBatchTable(imaging_batch_contents)

	if request.method == 'POST':
		logger.info("Post request")
		if form.submit.data == False: 
			""" Any button except final submit pressed """
			if form.apply_batch_parameters_button.data == True: 
				""" The "apply batch parameters to all samples" button was pressed """
				logger.info("apply batch parameters button pressed")
				
				""" Validate batch entry form before copying 
				and db inserts can be done """
				batch_image_resolution_forms = form.image_resolution_batch_forms
				for ii in range(len(batch_image_resolution_forms)):
					batch_image_resolution_form = batch_image_resolution_forms[ii]
					batch_image_resolution = batch_image_resolution_form.image_resolution.data
					batch_channel_forms = batch_image_resolution_form.channel_forms
					all_batch_channels_validated = True 
					for jj in range(len(batch_channel_forms)):
						batch_channel_form = batch_channel_forms[jj]
						
						batch_validated=True # switch to false if any not validated
						""" Left and right light sheets """
						channel_name = batch_channel_form.channel_name.data
						flash_str_prefix = (f"Batch parameters for image resolution: {batch_image_resolution},"
											f" channel: {channel_name} ")
						left_lightsheet_used = batch_channel_form.left_lightsheet_used.data
						right_lightsheet_used = batch_channel_form.right_lightsheet_used.data
						if not (left_lightsheet_used or right_lightsheet_used):
							flash_str = flash_str_prefix + " At least one light sheet required."
							batch_channel_form.left_lightsheet_used.errors = ['This field is required']
							flash(flash_str,"danger")
							batch_validated=False
						""" tiling scheme """
						tiling_scheme = batch_channel_form.tiling_scheme.data
						if not tiling_scheme:
							flash_str = flash_str_prefix + "Tiling scheme required"
							batch_channel_form.tiling_scheme.errors = ['This field is required']
							flash(flash_str,"danger")
							batch_validated=False
						elif len(tiling_scheme) != 3:
							logger.debug("Tiling scheme length:")
							logger.debug(len(tiling_scheme))
							flash_str = flash_str_prefix + ("Tiling scheme is not in correct format."
												  " Make sure it is like: 1x1 with no spaces.")
							batch_channel_form.tiling_scheme.errors = ['Incorrect format']
							flash(flash_str,"danger")
							batch_validated=False
						else:
							try:
								n_rows = int(tiling_scheme.lower().split('x')[0])
								n_columns = int(tiling_scheme.lower().split('x')[1])
								if batch_image_resolution in ['1.1x','1.3x'] and (n_rows > 2 or n_columns > 2):
									flash_str = flash_str_prefix + ("Tiling scheme must not exceed 2x2 for this resolution")
									batch_channel_form.tiling_scheme.errors = ['Tiling scheme must not exceed 2x2 for this resolution']
									flash(flash_str,"danger")
									batch_validated=False
									
								elif batch_image_resolution in ['2x','4x','3.6x'] and (n_rows > 4 or n_columns > 4):
									flash_str = flash_str_prefix + ("Tiling scheme must not exceed 4x4 for this resolution")
									batch_channel_form.tiling_scheme.errors = ['Tiling scheme must not exceed 4x4 for this resolution']
									flash(flash_str,"danger")
									batch_validated=False
							except:
								logger.debug("Here")
								batch_channel_form.tiling_scheme.errors = ['Incorrect format']
								flash_str = flash_str_prefix + ("Tiling scheme is not in correct format."
												  " Make sure it is like: 1x1 with no spaces.")	
								flash(flash_str,"danger")
								batch_validated=False
						""" tiling overlap """
						tiling_overlap = batch_channel_form.tiling_overlap.data
						try:
							fl_val = float(tiling_overlap)
							if fl_val < 0.0 or fl_val >= 1.0:
								flash_str = flash_str_prefix + "Tiling overlap must be a number between 0 and 1"
								batch_channel_form.tiling_overlap.errors = ['Tiling overlap must be a number between 0 and 1']
								flash(flash_str,"danger")
								batch_validated=False
						except:
							flash_str = flash_str_prefix + "Tiling overlap must be a number between 0 and 1"
							batch_channel_form.tiling_overlap.errors = ['Tiling overlap must be a number between 0 and 1']
							flash(flash_str,"danger")
							batch_validated=False
						""" z step """
						z_step = batch_channel_form.z_step.data
						if not z_step:
							flash_str = flash_str_prefix + "z_step required"
							batch_channel_form.z_step.errors = ['This field is required']
							flash(flash_str,"danger")
							batch_validated=False
						else:
							try:
								fl_val = float(z_step)
								if fl_val < 2 or fl_val > 1000:
									flash_str = flash_str_prefix + "z_step must be a number between 2 and 1000 microns"
									batch_channel_form.z_step.errors = ["z_step must be a number between 2 and 1000 microns"]
									flash(flash_str,"danger")
									batch_validated=False
							except:
								flash_str = flash_str_prefix + "z_step must be a number between 2 and 1000 microns"
								batch_channel_form.z_step.errors = ["z_step must be a number between 2 and 1000 microns"]
								flash(flash_str,"danger")
								batch_validated=False
						if not batch_validated:
							all_batch_channels_validated = False

				""" If validation of all batch channels passed then
				copy over all batch parameters to all samples """
				if all_batch_channels_validated:
					for sample_form in form.sample_forms:
						this_sample_name = sample_form.sample_name.data

						for ii in range(len(batch_image_resolution_forms)):
							batch_image_resolution_form = batch_image_resolution_forms[ii]
							batch_image_resolution = batch_image_resolution_form.image_resolution.data
							sample_image_resolution_form = sample_form.image_resolution_forms[ii]
							batch_channel_forms = batch_image_resolution_form.channel_forms
							sample_channel_forms = sample_image_resolution_form.channel_forms
							all_batch_channels_validated = True 
							for jj in range(len(batch_channel_forms)):
								batch_channel_form = batch_channel_forms[jj]
								this_channel_name = batch_channel_form.channel_name.data
								channel_insert_dict = {
									'username':username,
									'request_name':request_name,
									'sample_name':this_sample_name,
									'imaging_request_number':imaging_request_number,
									'image_resolution':batch_image_resolution,
									'channel_name':this_channel_name,
									'zoom_body_magnification':batch_channel_form.zoom_body_magnification.data,
									'image_orientation':batch_channel_form.image_orientation.data,
									'left_lightsheet_used':batch_channel_form.left_lightsheet_used.data,
									'right_lightsheet_used':batch_channel_form.right_lightsheet_used.data,
									'tiling_scheme':batch_channel_form.tiling_scheme.data,
									'tiling_overlap':batch_channel_form.tiling_overlap.data,
									'z_step':batch_channel_form.z_step.data
								}
								db_lightsheet.Request.ImagingChannel().insert1(channel_insert_dict,replace=True)
					flash("Batch parameters successfully applied to all samples","success")
				return redirect(url_for('imaging.imaging_batch_entry',
							username=username,request_name=request_name,
							imaging_batch_number=imaging_batch_number))
			else:
				""" A few possibilites: 
				1) A sample submit button was pressed
				2) A batch update resolution or new image channel button was pressed
				3) A sample update resolution or new image channel button was pressed
				"""

				""" First check if BATCH new channel button pressed or 
				BATCH update resolution was pressed
				in any of the resolution subforms """
				for image_resolution_form in form.image_resolution_batch_forms:
					form_resolution_dict = image_resolution_form.data
					logger.debug(form_resolution_dict)
					this_image_resolution =  form_resolution_dict['image_resolution']
					logger.debug("Image resolution:")
					logger.debug(this_image_resolution)
					update_resolution_button_pressed = form_resolution_dict['update_resolution_button']
					new_channel_button_pressed = form_resolution_dict['new_channel_button']
					
					if new_channel_button_pressed:
						""" ########################## """
						""" NEW CHANNEL BUTTON PRESSED """
						""" ########################## """
						logger.debug("New channel button pressed!")
						new_channel_name = form_resolution_dict['new_channel_dropdown']
						new_channel_purpose = form_resolution_dict['new_channel_purpose']
						logger.debug("Have new channel:")
						logger.debug(new_channel_name)
						""" Create a new ImagingChannel() entry for this channel """
						batch_channel_entry_dict = {}
						batch_channel_entry_dict['username'] = username
						batch_channel_entry_dict['request_name'] = request_name
						batch_channel_entry_dict['imaging_request_number'] = imaging_request_number
						batch_channel_entry_dict['image_resolution'] = this_image_resolution
						batch_channel_entry_dict['channel_name'] = new_channel_name
						batch_channel_entry_dict[new_channel_purpose] = 1
						""" Now go through all of the samples in this batch 
						and make an insert in the db for a new channel """
						imaging_channel_entry_list = []
						for sample_dict in sample_dict_list:
							this_sample_name = sample_dict['sample_name']
							imaging_channel_entry_dict = batch_channel_entry_dict.copy()
							imaging_channel_entry_dict['sample_name'] = this_sample_name
							imaging_channel_entry_list.append(imaging_channel_entry_dict)
						db_lightsheet.Request.ImagingChannel().insert(imaging_channel_entry_list)
						return redirect(url_for('imaging.imaging_batch_entry',
							username=username,request_name=request_name,
							imaging_batch_number=imaging_batch_number))
					
					elif update_resolution_button_pressed:
						""" ###################################### """
						""" CHANGE IMAGE RESOLUTION BUTTON PRESSED """
						""" ###################################### """
						logger.debug("Update image resolution button pressed!")
						new_image_resolution = form_resolution_dict['new_image_resolution']
						logger.debug("New image resolution is:")
						logger.debug(new_image_resolution)
						""" Update image resolution in all locations in the database """
						
						sample_names_this_batch = [x['sample_name'] for x in sample_dict_list]
						connection = db_lightsheet.Request.ImagingResolutionRequest.connection
						with connection.transaction:
							for this_sample_name in sample_names_this_batch:
								image_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
									f'username="{username}" ' & f'request_name="{request_name}" ' & \
									f'imaging_request_number={imaging_request_number}' & \
									f'sample_name="{this_sample_name}"' & \
									f'image_resolution="{this_image_resolution}"'
								""" Fetch results now because we are going to delete the entry shortly
								Will be able to modify these results once they are in memory """
								image_resolution_request_insert_dict = image_resolution_request_contents.fetch1() 
								imaging_channel_request_contents = db_lightsheet.Request.ImagingChannel() & \
									f'username="{username}" ' & f'request_name="{request_name}" ' & \
									f'imaging_request_number={imaging_request_number}' & \
									f'sample_name="{this_sample_name}"' & \
									f'image_resolution="{this_image_resolution}" '
								""" Fetch results now because we are going to delete the entry shortly
								Will be able to modify these results once they are in memory """
								imaging_channel_insert_dict_list = imaging_channel_request_contents.fetch(as_dict=True) 
								
								""" First delete all ImagingChannel() entries """
								dj.config['safemode'] = False # disables integrity checks so delete can take place
								imaging_channel_request_contents.delete(force=True)
								""" And delete ProcessingChannel() entries tied to this imaging request as well,
								if they exist (they might not if somone had requested 2x imaging only) """
								processing_channel_request_contents = db_lightsheet.Request.ProcessingChannel() & \
									f'username="{username}" ' & f'request_name="{request_name}" ' & \
									f'sample_name="{this_sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
									f'image_resolution="{this_image_resolution}" '
								processing_channel_dicts_to_insert = processing_channel_request_contents.fetch(as_dict=True)
								if len(processing_channel_request_contents) > 0:
									processing_channel_request_contents.delete(force=True)

								""" Now delete ProcessingResolutionRequest() entry """
								processing_resolution_request_contents = db_lightsheet.Request.ProcessingResolutionRequest() & \
									f'username="{username}" ' & f'request_name="{request_name}" ' & \
									f'sample_name="{this_sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
									f'image_resolution="{this_image_resolution}"'
								
								if len(processing_resolution_request_contents) > 0: 
									logger.debug("ProcessingResolutionRequest() entry already existed")
									processing_resolution_request_insert_dict = processing_resolution_request_contents.fetch1()
									processing_resolution_request_contents.delete(force=True)
								else:
									logger.debug("Making an entirely new ProcessingResolutionRequest() entry")
									processing_resolution_request_insert_dict = {}
									processing_resolution_request_insert_dict['request_name'] = request_name
									processing_resolution_request_insert_dict['username'] = username 
									processing_resolution_request_insert_dict['sample_name'] = sample_name
									processing_resolution_request_insert_dict['imaging_request_number'] = imaging_request_number
									processing_resolution_request_insert_dict['processing_request_number'] = 1
									processing_resolution_request_insert_dict['image_resolution'] = new_image_resolution

								""" Now delete ImagingResolutionRequest() entry """
								image_resolution_request_contents.delete(force=True)
								""" Reset to whatever safemode was before the switch """
								dj.config['safemode'] = current_app.config['DJ_SAFEMODE']

								""" Now make the inserts with the updated image_resolution value """
								""" First ImagingResolutionRequest() """
								
								image_resolution_request_insert_dict['image_resolution'] = new_image_resolution
								logger.debug("inserting ImagingResolutionRequest() contents:")
								logger.debug(image_resolution_request_insert_dict)
								db_lightsheet.Request.ImagingResolutionRequest().insert1(
									image_resolution_request_insert_dict)
								
								""" Now ImagingChannel() """
								[d.update({'image_resolution':new_image_resolution}) for d in imaging_channel_insert_dict_list]
								logger.debug("inserting ImagingChannel() entries:")
								logger.debug(imaging_channel_insert_dict_list)
								db_lightsheet.Request.ImagingChannel().insert(imaging_channel_insert_dict_list)
								
								""" For processing inserts, make sure that at least one image resolution
								for this imaging request including the new resolution merits a processing request,
								i.e. at least one is in the list of resolutions we are capable of processing.
								If there are now no resolutions we can process, 
								then we need to remove the processing request if it exists """
								
								image_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
									f'username="{username}" ' & f'request_name="{request_name}" ' & \
									f'sample_name="{this_sample_name}" ' & f'imaging_request_number={imaging_request_number}'
								image_resolutions_used = set(image_resolution_request_contents.fetch('image_resolution'))
								bad_image_resolutions = current_app.config['RESOLUTIONS_NO_PROCESSING']
								any_good_resolutions = any([res not in bad_image_resolutions for res in image_resolutions_used])

								if not any_good_resolutions:
									logger.debug("There are no image resolutions that we can process")
									""" Remove processing request entry if it exists """
									processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
										f'username="{username}" ' & f'request_name="{request_name}" ' & \
										f'sample_name="{this_sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
										'processing_request_number=1'
									if len(processing_request_contents) > 0:
										dj.config['safemode'] = False
										processing_request_contents.delete(force=True)
										dj.config['safemode'] = current_app.config['DJ_SAFEMODE']
								else:
									""" There are some resolutions that we can process, so insert any entry 
									if none already exist """
									logger.debug("There is at least one image resolution we can process")						
									processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
										f'username="{username}" ' & f'request_name="{request_name}" ' & \
										f'sample_name="{this_sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
										'processing_request_number=1'
									
									if len(processing_request_contents) == 0:
										logger.debug("No existing processing request, so make an entirely new entry")
										now = datetime.now()
										date = now.strftime("%Y-%m-%d")
										time = now.strftime("%H:%M:%S") 
										processing_request_insert_dict = {}
										processing_request_number = 1
										processing_request_insert_dict['request_name'] = request_name
										processing_request_insert_dict['username'] = username 
										processing_request_insert_dict['sample_name'] = this_sample_name
										processing_request_insert_dict['imaging_request_number'] = imaging_request_number
										processing_request_insert_dict['processing_request_number'] = 1
										processing_request_insert_dict['processing_request_date_submitted'] = date
										processing_request_insert_dict['processing_request_time_submitted'] = time
										processing_request_insert_dict['processing_progress'] = "incomplete"
										
										db_lightsheet.Request.ProcessingRequest().insert1(processing_request_insert_dict)
										logger.debug("Inserted a ProcessingRequest() entry since one did not already exist")
									if new_image_resolution not in bad_image_resolutions:
										""" If this new resolution is one we can process 
										then add ProcessingResolutionRequest() and ProcessingChannel
										entries for it """

										""" Now ProcessingResolutionRequest() """
										processing_resolution_request_insert_dict['image_resolution'] = new_image_resolution
										logger.debug("Inserting ProcessingResolutionRequest() contents:")
										logger.debug(processing_resolution_request_insert_dict)
										db_lightsheet.Request.ProcessingResolutionRequest().insert1(
											processing_resolution_request_insert_dict)
										""" Finally ProcessingChannel() """
										[d.update({'image_resolution':new_image_resolution}) for d in processing_channel_dicts_to_insert]
										logger.debug("Inserting ProcessingChannel() contents:")
										logger.debug(processing_channel_dicts_to_insert)
										db_lightsheet.Request.ProcessingChannel().insert(processing_channel_dicts_to_insert)
						
						return redirect(url_for('imaging.imaging_batch_entry',
							username=username,request_name=request_name,
							imaging_batch_number=imaging_batch_number))	
				
				""" Figure out if button press came from sample subforms """
				for sample_form in form.sample_forms:
					logger.debug("checking sample forms")
					this_sample_name = sample_form.sample_name.data
					""" Check if sample submit button pressed """
					if sample_form.submit.data == True:
						""" ############################ """
						""" SAMPLE SUBMIT BUTTON PRESSED """
						""" ############################ """

						logger.debug("Sample form submit button pressed:")
						logger.debug(sample_form.sample_name.data)
						all_channels_validated = True
						sample_subfolder_dicts = {}
						for image_resolution_form in sample_form.image_resolution_forms:
							subfolder_dict = {}
							image_resolution = image_resolution_form.image_resolution.data
							sample_subfolder_dicts[image_resolution] = subfolder_dict
							for channel_form in image_resolution_form.channel_forms:
								channel_dict = channel_form.data
								""" VALIDATION """
								validated=True # switch to false if any not validated
								""" Left and right light sheets """
								channel_name = channel_form.channel_name.data
								flash_str_prefix = (f"Sample: {this_sample_name}, image resolution: {image_resolution},"
													f" channel: {channel_name} ")
								left_lightsheet_used = channel_form.left_lightsheet_used.data
								right_lightsheet_used = channel_form.right_lightsheet_used.data
								if not (left_lightsheet_used or right_lightsheet_used):
									flash_str = flash_str_prefix + " At least one light sheet required."
									channel_form.left_lightsheet_used.errors = ['This field is required']
									flash(flash_str,"danger")
									validated=False
								""" tiling scheme """
								tiling_scheme = channel_form.tiling_scheme.data
								if not tiling_scheme:
									flash_str = flash_str_prefix + "Tiling scheme required"
									channel_form.tiling_scheme.errors = ['This field is required']
									flash(flash_str,"danger")
									validated=False
								elif len(tiling_scheme) != 3:
									flash_str = flash_str_prefix + ("Tiling scheme is not in correct format."
														  " Make sure it is like: 1x1 with no spaces.")
									channel_form.tiling_scheme.errors = ['Incorrect format']
									flash(flash_str,"danger")
									validated=False
								else:
									try:
										n_rows = int(tiling_scheme.lower().split('x')[0])
										n_columns = int(tiling_scheme.lower().split('x')[1])
										if image_resolution in ['1.1x','1.3x'] and (n_rows > 2 or n_columns > 2):
											flash_str = flash_str_prefix + ("Tiling scheme must not exceed 2x2 for this resolution")
											channel_form.tiling_scheme.errors = ['Tiling scheme must not exceed 2x2 for this resolution']
											flash(flash_str,"danger")
											validated=False
											
										elif image_resolution in ['2x','4x','3.6x'] and (n_rows > 4 or n_columns > 4):
											flash_str = flash_str_prefix + ("Tiling scheme must not exceed 4x4 for this resolution")
											channel_form.tiling_scheme.errors = ['Tiling scheme must not exceed 4x4 for this resolution']
											flash(flash_str,"danger")
											validated=False
									except:
										channel_form.tiling_scheme.errors = ['Incorrect format']
										flash_str = flash_str_prefix + ("Tiling scheme is not in correct format."
														  " Make sure it is like: 1x1 with no spaces.")	
										flash(flash_str,"danger")
										validated=False
								""" tiling overlap """
								tiling_overlap = channel_form.tiling_overlap.data
								try:
									fl_val = float(tiling_overlap)
									if fl_val < 0.0 or fl_val >= 1.0:
										flash_str = flash_str_prefix + "Tiling overlap must be a number between 0 and 1"
										channel_form.tiling_overlap.errors = ['Tiling overlap must be a number between 0 and 1']
										flash(flash_str,"danger")
										validated=False
								except:
									flash_str = flash_str_prefix + "Tiling overlap must be a number between 0 and 1"
									channel_form.tiling_overlap.errors = ['Tiling overlap must be a number between 0 and 1']
									flash(flash_str,"danger")
									validated=False
								""" z step """
								z_step = channel_form.z_step.data
								if not z_step:
									flash_str = flash_str_prefix + "z_step required"
									channel_form.z_step.errors = ['This field is required']
									flash(flash_str,"danger")
									validated=False
								else:
									try:
										fl_val = float(z_step)
										if fl_val < 2 or fl_val > 1000:
											flash_str = flash_str_prefix + "z_step must be a number between 2 and 1000 microns"
											channel_form.z_step.errors = ["z_step must be a number between 2 and 1000 microns"]
											flash(flash_str,"danger")
											validated=False
									except:
										flash_str = flash_str_prefix + "z_step must be a number between 2 and 1000 microns"
										channel_form.z_step.errors = ["z_step must be a number between 2 and 1000 microns"]
										flash(flash_str,"danger")
										validated=False
								""" number of z planes """
								number_of_z_planes = channel_form.number_of_z_planes.data
								if not number_of_z_planes:
									flash_str = flash_str_prefix + "number_of_z_planes required"
									channel_form.number_of_z_planes.errors = ['This field is required']
									flash(flash_str,"danger")
									validated=False
								elif number_of_z_planes <= 0 or number_of_z_planes > 5500:
									flash_str = flash_str_prefix + "number_of_z_planes must be a number between 1 and 5500"
									channel_form.number_of_z_planes.errors = ["number_of_z_planes must be a number between 1 and 5500"]
									flash(flash_str,"danger")
									validated=False
								""" Rawdata subfolder """
								rawdata_subfolder = channel_form.rawdata_subfolder.data
								if not rawdata_subfolder:
									flash_str = flash_str_prefix + "rawdata_subfolder required"
									channel_form.rawdata_subfolder.errors = ['This field is required']
									flash(flash_str,"danger")
									validated=False
								rawdata_fullpath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
									username,request_name,this_sample_name,'imaging_request_1',
									'rawdata',f'resolution_{image_resolution}',rawdata_subfolder)
								
								if rawdata_subfolder in subfolder_dict.keys():
									subfolder_dict[rawdata_subfolder].append(channel_dict)
								else:
									subfolder_dict[rawdata_subfolder] = [channel_dict]
								
								channel_index = len(subfolder_dict[rawdata_subfolder]) - 1
								
								if validated:
									logger.debug("Checking validation on rawdata subfolder")
									number_of_rawfiles_expected = number_of_z_planes*(left_lightsheet_used+right_lightsheet_used)*n_rows*n_columns
									""" calculate the number we find. We have to be careful here
									because the raw data filenames will include C00 if there
									is only one light sheet used, regardless of whether it is
									left or right. If both are used,
									then the left lightsheet files always have C00 in filenames
									and right lightsheet files always have C01 in filenames. """
									number_of_rawfiles_found = 0
									if left_lightsheet_used and right_lightsheet_used:
										number_of_rawfiles_found_left_lightsheet = \
											len(glob.glob(rawdata_fullpath + f'/*RawDataStack*_C00_*Filter000{channel_index}*'))	
										number_of_rawfiles_found += number_of_rawfiles_found_left_lightsheet
										number_of_rawfiles_found_right_lightsheet = \
											len(glob.glob(rawdata_fullpath + f'/*RawDataStack*_C01_*Filter000{channel_index}*'))	
										number_of_rawfiles_found += number_of_rawfiles_found_right_lightsheet
									else:
										# doesn't matter if its left or right lightsheet. Since there is only one, their glob patterns will be identical
										number_of_rawfiles_found = \
											len(glob.glob(rawdata_fullpath + f'/*RawDataStack*_C00_*Filter000{channel_index}*'))	
									logger.debug(number_of_rawfiles_expected)
									logger.debug(number_of_rawfiles_found)
									if number_of_rawfiles_found != number_of_rawfiles_expected:
										error_str = (f"There should be {number_of_rawfiles_expected} raw files in rawdata folder, "
											  f"but found {number_of_rawfiles_found}")
										flash_str = flash_str_prefix + error_str
										channel_form.rawdata_subfolder.errors = [error_str]
										validated=False
										flash(flash_str,'danger')
									""" Now make sure imaging parameters are the same for all channels within the same subfolder """
									common_key_list = ['image_orientation','left_lightsheet_used',
										'right_lightsheet_used','tiling_scheme','tiling_overlap',
										'z_step','number_of_z_planes']
									all_tiling_schemes = [] # also keep track of tiling parameters for all subfolders at this resolution
									all_tiling_overlaps = [] # also keep track of tiling parameters for all subfolders at this resolution
									for subfolder in subfolder_dict.keys():
										channel_dict_list = subfolder_dict[subfolder]
										for d in channel_dict_list:
											all_tiling_schemes.append(d['tiling_scheme'])
											all_tiling_overlaps.append(d['tiling_overlap'])
										if not all([list(map(d.get,common_key_list)) == \
											list(map(channel_dict_list[0].get,common_key_list)) \
												for d in channel_dict_list]):
											
											error_str = (f"For raw data subfolder: {subfolder}. "
														  "Tiling and imaging parameters must be identical"
														  " for all channels in the same subfolder. Check your entries.")
											flash_str = flash_str_prefix + error_str
											validated=False
											flash(flash_str,'danger')
									""" Now make sure tiling parameters are same for all channels at each resolution """
									if (not all([x==all_tiling_overlaps[0] for x in all_tiling_overlaps]) 
									or (not all([x==all_tiling_schemes[0] for x in all_tiling_schemes]))):
										error_str = "All tiling parameters must be the same for each channel of a given resolution"
										flash_str = flash_str_prefix + error_str
										validated=False
										flash(flash_str,'danger')
								if not validated:
									all_channels_validated = False

						if all_channels_validated:
							logger.debug("Sample form validated")
							""" Loop through the image resolution forms and find all channels in the form  
							and update the existing table entries with the new imaging information """
							
							for form_resolution_dict in sample_form.image_resolution_forms.data:
								image_resolution = form_resolution_dict['image_resolution']
								subfolder_dict = sample_subfolder_dicts[image_resolution]
								""" Make rawdata/ subdirectories for this resolution """
								imaging_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
												 request_name,this_sample_name,f"imaging_request_1",
												 "rawdata",f"resolution_{image_resolution}")
								mymkdir(imaging_dir)
								for form_channel_dict in form_resolution_dict['channel_forms']:
									channel_name = form_channel_dict['channel_name']
									logger.debug(channel_name)
									rawdata_subfolder = form_channel_dict['rawdata_subfolder']
									number_of_z_planes = form_channel_dict['number_of_z_planes']
									tiling_scheme = form_channel_dict['tiling_scheme']
									z_step = form_channel_dict['z_step']
									left_lightsheet_used = form_channel_dict['left_lightsheet_used']
									right_lightsheet_used = form_channel_dict['right_lightsheet_used']
									logger.debug(subfolder_dict[rawdata_subfolder])
									channel_names_this_subfolder = [x['channel_name'] for x in subfolder_dict[rawdata_subfolder]]

									channel_index = channel_names_this_subfolder.index(channel_name)
									logger.info(f" channel {channel_name} with image_resolution \
										 {image_resolution} has channel_index = {channel_index}")
									
									channel_content = channel_contents & f'channel_name="{channel_name}"' & \
									f'image_resolution="{image_resolution}"' & f'imaging_request_number=1'
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
									
									db_lightsheet.Request.ImagingChannel().insert1(channel_insert_dict,replace=True)
									""" Set imaging progress complete for this sample """
									imaging_request_contents_this_sample = imaging_request_contents & \
										f'sample_name="{this_sample_name}"'
									dj.Table._update(imaging_request_contents_this_sample,'imaging_progress','complete')

									
									samples_imaging_progress_dict[this_sample_name] = 'complete'
									""" Kick off celery task for creating precomputed data from this
									raw data image dataset if there is more than one tile.
									"""
							flash(f"Imaging entry for sample {this_sample_name} successful","success")
						else:
							logger.debug("Sample form not validated")
						return redirect(url_for('imaging.imaging_batch_entry',
									username=username,request_name=request_name,
									imaging_batch_number=imaging_batch_number))
					else:
						""" Either a sample update resolution or 
						new image channel button was pressed.
						Loop through image resolution forms to find
						out which one """
						for image_resolution_form in sample_form.image_resolution_forms:
							form_resolution_dict = image_resolution_form.data
							this_image_resolution =  form_resolution_dict['image_resolution']
							logger.debug("Image resolution:")
							logger.debug(this_image_resolution)
							update_resolution_button_pressed = form_resolution_dict['update_resolution_button']
							new_channel_button_pressed = form_resolution_dict['new_channel_button']
							if new_channel_button_pressed:
								""" ########################## """
								""" SAMPLE NEW CHANNEL BUTTON PRESSED """
								""" ########################## """
								logger.debug("New channel button pressed!")
								new_channel_name = form_resolution_dict['new_channel_dropdown']
								new_channel_purpose = form_resolution_dict['new_channel_purpose']
								logger.debug("Have new channel:")
								logger.debug(new_channel_name)
								""" Create a new ImagingChannel() entry for this channel """
								channel_entry_dict = {}
								channel_entry_dict['username'] = username
								channel_entry_dict['request_name'] = request_name
								channel_entry_dict['sample_name'] = this_sample_name
								channel_entry_dict['imaging_request_number'] = imaging_request_number
								channel_entry_dict['image_resolution'] = this_image_resolution
								channel_entry_dict['channel_name'] = new_channel_name
								channel_entry_dict[new_channel_purpose] = 1
								
								db_lightsheet.Request.ImagingChannel().insert1(channel_entry_dict)
								return redirect(url_for('imaging.imaging_batch_entry',
									username=username,request_name=request_name,
									imaging_batch_number=imaging_batch_number))
							
							elif update_resolution_button_pressed:
								""" ###################################### """
								""" SAMPLE CHANGE IMAGE RESOLUTION BUTTON PRESSED """
								""" ###################################### """
								logger.debug("Update image resolution button pressed!")
								new_image_resolution = form_resolution_dict['new_image_resolution']
								logger.debug("New image resolution is:")
								logger.debug(new_image_resolution)
								""" Update image resolution in all locations in the database """
								
								connection = db_lightsheet.Request.ImagingResolutionRequest.connection
								with connection.transaction:
									image_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
										f'username="{username}" ' & f'request_name="{request_name}" ' & \
										f'imaging_request_number={imaging_request_number}' & \
										f'sample_name="{this_sample_name}"' & \
										f'image_resolution="{this_image_resolution}"'
									""" Fetch results now because we are going to delete the entry shortly
									Will be able to modify these results once they are in memory """
									image_resolution_request_insert_dict = image_resolution_request_contents.fetch1() 
									imaging_channel_request_contents = db_lightsheet.Request.ImagingChannel() & \
										f'username="{username}" ' & f'request_name="{request_name}" ' & \
										f'imaging_request_number={imaging_request_number}' & \
										f'sample_name="{this_sample_name}"' & \
										f'image_resolution="{this_image_resolution}" '
									""" Fetch results now because we are going to delete the entry shortly
									Will be able to modify these results once they are in memory """
									imaging_channel_insert_dict_list = imaging_channel_request_contents.fetch(as_dict=True) 
									
									""" First delete all ImagingChannel() entries """
									dj.config['safemode'] = False # disables integrity checks so delete can take place
									imaging_channel_request_contents.delete(force=True)
									""" And delete ProcessingChannel() entries tied to this imaging request as well,
									if they exist (they might not if somone had requested 2x imaging only) """
									processing_channel_request_contents = db_lightsheet.Request.ProcessingChannel() & \
										f'username="{username}" ' & f'request_name="{request_name}" ' & \
										f'sample_name="{this_sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
										f'image_resolution="{this_image_resolution}" '
									processing_channel_dicts_to_insert = processing_channel_request_contents.fetch(as_dict=True)
									if len(processing_channel_request_contents) > 0:
										processing_channel_request_contents.delete(force=True)

									""" Now delete ProcessingResolutionRequest() entry """
									processing_resolution_request_contents = db_lightsheet.Request.ProcessingResolutionRequest() & \
										f'username="{username}" ' & f'request_name="{request_name}" ' & \
										f'sample_name="{this_sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
										f'image_resolution="{this_image_resolution}"'
									
									if len(processing_resolution_request_contents) > 0: 
										logger.debug("ProcessingResolutionRequest() entry already existed")
										processing_resolution_request_insert_dict = processing_resolution_request_contents.fetch1()
										processing_resolution_request_contents.delete(force=True)
									else:
										logger.debug("Making an entirely new ProcessingResolutionRequest() entry")
										processing_resolution_request_insert_dict = {}
										processing_resolution_request_insert_dict['request_name'] = request_name
										processing_resolution_request_insert_dict['username'] = username 
										processing_resolution_request_insert_dict['sample_name'] = sample_name
										processing_resolution_request_insert_dict['imaging_request_number'] = imaging_request_number
										processing_resolution_request_insert_dict['processing_request_number'] = 1
										processing_resolution_request_insert_dict['image_resolution'] = new_image_resolution

									""" Now delete ImagingResolutionRequest() entry """
									image_resolution_request_contents.delete(force=True)
									""" Reset to whatever safemode was before the switch """
									dj.config['safemode'] = current_app.config['DJ_SAFEMODE']

									""" Now make the inserts with the updated image_resolution value """
									""" First ImagingResolutionRequest() """
									
									image_resolution_request_insert_dict['image_resolution'] = new_image_resolution
									logger.debug("inserting ImagingResolutionRequest() contents:")
									logger.debug(image_resolution_request_insert_dict)
									db_lightsheet.Request.ImagingResolutionRequest().insert1(
										image_resolution_request_insert_dict)
									
									""" Now ImagingChannel() """
									[d.update({'image_resolution':new_image_resolution}) for d in imaging_channel_insert_dict_list]
									logger.debug("inserting ImagingChannel() entries:")
									logger.debug(imaging_channel_insert_dict_list)
									db_lightsheet.Request.ImagingChannel().insert(imaging_channel_insert_dict_list)
									
									""" For processing inserts, make sure that at least one image resolution
									for this imaging request including the new resolution merits a processing request,
									i.e. at least one is in the list of resolutions we are capable of processing.
									If there are now no resolutions we can process, 
									then we need to remove the processing request if it exists """
									
									image_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
										f'username="{username}" ' & f'request_name="{request_name}" ' & \
										f'sample_name="{this_sample_name}" ' & f'imaging_request_number={imaging_request_number}'
									image_resolutions_used = set(image_resolution_request_contents.fetch('image_resolution'))
									bad_image_resolutions = current_app.config['RESOLUTIONS_NO_PROCESSING']
									any_good_resolutions = any([res not in bad_image_resolutions for res in image_resolutions_used])

									if not any_good_resolutions:
										logger.debug("There are no image resolutions that we can process")
										""" Remove processing request entry if it exists """
										processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
											f'username="{username}" ' & f'request_name="{request_name}" ' & \
											f'sample_name="{this_sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
											'processing_request_number=1'
										if len(processing_request_contents) > 0:
											dj.config['safemode'] = False
											processing_request_contents.delete(force=True)
											dj.config['safemode'] = current_app.config['DJ_SAFEMODE']
									else:
										""" There are some resolutions that we can process, so insert any entry 
										if none already exist """
										logger.debug("There is at least one image resolution we can process")						
										processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
											f'username="{username}" ' & f'request_name="{request_name}" ' & \
											f'sample_name="{this_sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
											'processing_request_number=1'
										
										if len(processing_request_contents) == 0:
											logger.debug("No existing processing request, so make an entirely new entry")
											now = datetime.now()
											date = now.strftime("%Y-%m-%d")
											time = now.strftime("%H:%M:%S") 
											processing_request_insert_dict = {}
											processing_request_number = 1
											processing_request_insert_dict['request_name'] = request_name
											processing_request_insert_dict['username'] = username 
											processing_request_insert_dict['sample_name'] = this_sample_name
											processing_request_insert_dict['imaging_request_number'] = imaging_request_number
											processing_request_insert_dict['processing_request_number'] = 1
											processing_request_insert_dict['processing_request_date_submitted'] = date
											processing_request_insert_dict['processing_request_time_submitted'] = time
											processing_request_insert_dict['processing_progress'] = "incomplete"
											
											db_lightsheet.Request.ProcessingRequest().insert1(processing_request_insert_dict)
											logger.debug("Inserted a ProcessingRequest() entry since one did not already exist")
										if new_image_resolution not in bad_image_resolutions:
											""" If this new resolution is one we can process 
											then add ProcessingResolutionRequest() and ProcessingChannel
											entries for it """

											""" Now ProcessingResolutionRequest() """
											processing_resolution_request_insert_dict['image_resolution'] = new_image_resolution
											logger.debug("Inserting ProcessingResolutionRequest() contents:")
											logger.debug(processing_resolution_request_insert_dict)
											db_lightsheet.Request.ProcessingResolutionRequest().insert1(
												processing_resolution_request_insert_dict)
											""" Finally ProcessingChannel() """
											[d.update({'image_resolution':new_image_resolution}) for d in processing_channel_dicts_to_insert]
											logger.debug("Inserting ProcessingChannel() contents:")
											logger.debug(processing_channel_dicts_to_insert)
											db_lightsheet.Request.ProcessingChannel().insert(processing_channel_dicts_to_insert)
								
								return redirect(url_for('imaging.imaging_batch_entry',
									username=username,request_name=request_name,
									imaging_batch_number=imaging_batch_number))	
		else: # final submit button pressed. No validation necessary since all done in each sample form
			pass
		# 	logger.info("Final submit button pressed")
		# 	logger.info("form validated")
		# 	imaging_progress = imaging_batch_contents.fetch1('imaging_progress')
			
		# 	if imaging_progress == 'complete':
		# 		logger.info("Imaging is already complete so hitting the submit button again did nothing")
		# 		return redirect(url_for('imaging.imaging_entry',username=username,
		# 		request_name=request_name,sample_name=sample_name,imaging_request_number=imaging_request_number))
			
		# 	""" loop through the image resolution forms and find all channel entries"""

		# 	""" Loop through the image resolution forms and find all channels in the form  
		# 	and update the existing table entries with the new imaging information """
			
		# 	for form_resolution_dict in form.image_resolution_forms.data:
		# 		subfolder_dict = {}
		# 		image_resolution = form_resolution_dict['image_resolution']
		# 		""" Make rawdata/ subdirectories for this resolution """
		# 		imaging_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
		# 						 request_name,sample_name,f"imaging_request_{imaging_request_number}",
		# 						 "rawdata",f"resolution_{image_resolution}")
		# 		mymkdir(imaging_dir)
		# 		for form_channel_dict in form_resolution_dict['channel_forms']:
		# 			channel_name = form_channel_dict['channel_name']
		# 			rawdata_subfolder = form_channel_dict['rawdata_subfolder']
		# 			number_of_z_planes = form_channel_dict['number_of_z_planes']
		# 			tiling_scheme = form_channel_dict['tiling_scheme']
		# 			z_step = form_channel_dict['z_step']
		# 			left_lightsheet_used = form_channel_dict['left_lightsheet_used']
		# 			right_lightsheet_used = form_channel_dict['right_lightsheet_used']
		# 			if rawdata_subfolder in subfolder_dict.keys():
		# 				subfolder_dict[rawdata_subfolder].append(channel_name)
		# 			else:
		# 				subfolder_dict[rawdata_subfolder] = [channel_name]
		# 			channel_index = subfolder_dict[rawdata_subfolder].index(channel_name)
		# 			logger.info(f" channel {channel_name} with image_resolution \
		# 				 {image_resolution} has channel_index = {channel_index}")

		# 			""" Now look for the number of z planes in the raw data subfolder on bucket
		# 				and validate that it is the same as the user specified 
		# 			"""
					
		# 			channel_content = channel_contents & f'channel_name="{channel_name}"' & \
		# 			f'image_resolution="{image_resolution}"' & f'imaging_request_number={imaging_request_number}'
		# 			channel_content_dict = channel_content.fetch1()
		# 			''' Make a copy of the current row in a new dictionary which we will insert '''
		# 			channel_insert_dict = {}
				
		# 			for key,val in channel_content_dict.items():
		# 				channel_insert_dict[key] = val

		# 			''' Now replace (some of) the values in the dict from whatever we 
		# 			get from the form '''
		# 			for key,val in form_channel_dict.items():
		# 				if key in channel_content_dict.keys() and key not in ['channel_name','image_resolution','imaging_request_number']:
		# 					channel_insert_dict[key] = val
		# 			channel_insert_dict['imspector_channel_index'] = channel_index
			
		# 			db_lightsheet.Request.ImagingChannel().insert1(channel_insert_dict,replace=True)
		# 			""" Kick off celery task for creating precomputed data from this
		# 			raw data image dataset if there is more than one tile.
		# 			"""
		# 			if tiling_scheme == '1x1':
		# 				logger.info("Only one tile. Creating precomputed data for neuroglancer visualization. ")
		# 				precomputed_kwargs = dict(username=username,request_name=request_name,
		# 										sample_name=sample_name,imaging_request_number=imaging_request_number,
		# 										image_resolution=image_resolution,channel_name=channel_name,
		# 										channel_index=channel_index,number_of_z_planes=number_of_z_planes,
		# 										left_lightsheet_used=left_lightsheet_used,
		# 										right_lightsheet_used=right_lightsheet_used,
		# 										z_step=z_step,rawdata_subfolder=rawdata_subfolder)
		# 				raw_viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
		# 						 f"{request_name}/{sample_name}/"
		# 						 f"imaging_request_{imaging_request_number}/viz/raw")

		# 				mymkdir(raw_viz_dir)
		# 				channel_viz_dir = os.path.join(raw_viz_dir,f'channel_{channel_name}')
		# 				mymkdir(channel_viz_dir)
		# 				raw_data_dir = os.path.join(imaging_dir,rawdata_subfolder)
		# 				logger.debug("raw data dir:")
		# 				logger.debug(raw_data_dir)
		# 				if left_lightsheet_used:
		# 					this_viz_dir = os.path.join(channel_viz_dir,'left_lightsheet')
		# 					mymkdir(this_viz_dir)
		# 					precomputed_kwargs['lightsheet'] = 'left'
		# 					precomputed_kwargs['viz_dir'] = this_viz_dir
		# 					layer_name = f'channel{channel_name}_raw_left_lightsheet'
		# 					precomputed_kwargs['layer_name'] = layer_name
		# 					layer_dir = os.path.join(this_viz_dir,layer_name)
		# 					mymkdir(layer_dir)
		# 					# Figure out what x and y dimensions are
		# 					lightsheet_index_code = 'C00' # always for left lightsheet
		# 					precomputed_kwargs['lightsheet_index_code'] = lightsheet_index_code
		# 					all_slices = glob.glob(
		# 						f"{raw_data_dir}/*RawDataStack[00 x 00*{lightsheet_index_code}*Filter000{channel_index}*tif")
		# 					first_slice = all_slices[0]
		# 					first_im = Image.open(first_slice)
		# 					x_dim,y_dim = first_im.size
		# 					precomputed_kwargs['x_dim'] = x_dim
		# 					precomputed_kwargs['y_dim'] = y_dim
		# 					first_im.close() 
		# 					if not os.environ['FLASK_MODE'] == 'TEST': 
		# 						tasks.make_precomputed_rawdata.delay(**precomputed_kwargs) # pragma: no cover - used to exclude this line from calculating test coverage 
		# 				if right_lightsheet_used:
		# 					this_viz_dir = os.path.join(channel_viz_dir,'right_lightsheet')
		# 					mymkdir(this_viz_dir)
		# 					precomputed_kwargs['lightsheet'] = 'right'
		# 					precomputed_kwargs['viz_dir'] = this_viz_dir
		# 					layer_name = f'channel{channel_name}_raw_right_lightsheet'
		# 					precomputed_kwargs['layer_name'] = layer_name
		# 					layer_dir = os.path.join(this_viz_dir,layer_name)
		# 					mymkdir(layer_dir)
							
		# 					# figure out whether to look for C00 or C01 files
		# 					if left_lightsheet_used:
		# 						lightsheet_index_code = 'C01'
		# 					else: 
		# 						# right light sheet was the only one used so looking for C00 files
		# 						lightsheet_index_code = 'C00'
		# 					precomputed_kwargs['lightsheet_index_code'] = lightsheet_index_code
		# 					# Figure out what x and y dimensions are
		# 					all_slices = glob.glob(f"{raw_data_dir}/*RawDataStack[00 x 00*{lightsheet_index_code}*Filter000{channel_index}*tif")
		# 					first_slice = all_slices[0]
		# 					first_im = Image.open(first_slice)
		# 					x_dim,y_dim = first_im.size
		# 					precomputed_kwargs['x_dim'] = x_dim
		# 					precomputed_kwargs['y_dim'] = y_dim
		# 					first_im.close()
		# 					if not os.environ['FLASK_MODE'] == 'TEST': 
		# 						tasks.make_precomputed_rawdata.delay(**precomputed_kwargs) # pragma: no cover - used to exclude this line from calculating test coverage 
		# 			else:
		# 				logger.info(f"Tiling scheme: {tiling_scheme} means there is more than one tile. "
		# 							 "Not creating precomputed data for neuroglancer visualization.")
				
		# 	correspondence_email = (db_lightsheet.Request() & f'username="{username}"' & \
		# 	 f'request_name="{request_name}"').fetch1('correspondence_email')
		# 	data_rootpath = current_app.config["DATA_BUCKET_ROOTPATH"]
		# 	path_to_data = (f'{data_rootpath}/{username}/{request_name}/'
		# 					 f'{sample_name}/imaging_request_number_{imaging_request_number}/rawdata')
		# 	""" Send email """
		# 	subject = 'Lightserv automated email: Imaging complete'
		# 	hosturl = os.environ['HOSTURL']

		# 	processing_manager_url = f'https://{hosturl}' + url_for('processing.processing_manager')

		# 	message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
		# 				'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
		# 				'The raw data for your request:\n'
		# 				f'request_name: "{request_name}"\n'
		# 				f'sample_name: "{sample_name}"\n'
		# 				f'are now available on bucket here: {path_to_data}\n\n'
		# 				 'To start processing your data, '
		# 				f'go to the processing management GUI: {processing_manager_url} '
		# 				'and find your sample to process.\n\n'
		# 				 'Thanks,\n\nThe Core Facility')
		# 	request_contents = db_lightsheet.Request() & \
		# 						{'username':username,'request_name':request_name}
		# 	correspondence_email = request_contents.fetch1('correspondence_email')
		# 	recipients = [correspondence_email]
		# 	if not os.environ['FLASK_MODE'] == 'TEST':
		# 		send_email.delay(subject=subject,body=message_body,recipients=recipients) # pragma: no cover - used to exclude this line from calculating test coverage
		# 	flash(f"""Imaging is complete. An email has been sent to {correspondence_email} 
		# 		informing them that their raw data is now available on bucket.
		# 		The processing pipeline is now ready to run. ""","success")
		# 	dj.Table._update(imaging_request_contents,'imaging_progress','complete')
		# 	now = datetime.now()
		# 	date = now.strftime('%Y-%m-%d')
		# 	dj.Table._update(imaging_request_contents,'imaging_performed_date',date)
			
		# 	""" Finally, set up the 4-day reminder email that will be sent if 
		# 	user still has not submitted processing request (provided that there exists a processing 
		# 	request for this imaging request) """

		# 	""" First check if there is a processing request for this imaging request.
		# 	This will be processing_request_number=1 because we are in the imaging entry
		# 	form here. """
		# 	restrict_dict = dict(username=username,request_name=request_name,
		# 		sample_name=sample_name,imaging_request_number=imaging_request_number,
		# 		processing_request_number=1)
		# 	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & restrict_dict
		# 	if len(processing_request_contents) > 0:
		# 		subject = 'Lightserv automated email. Reminder to start processing.'
		# 		body = ('Hello, this is a reminder that you still have not started '
		# 				'the data processing pipeline for your sample:.\n\n'
		# 				f'request_name: {request_name}\n'
		# 				f'sample_name: {sample_name}\n\n'
		# 				'To start processing your data, '
		# 				f'go to the processing management GUI: {processing_manager_url} '
		# 				'and find your sample to process.\n\n'
		# 				'Thanks,\nThe Brain Registration and Histology Core Facility')    
		# 		logger.debug("Sending reminder email 4 days in the future")
		# 		request_contents = db_lightsheet.Request() & \
		# 						{'username':username,'request_name':request_name}
		# 		correspondence_email = request_contents.fetch1('correspondence_email')
		# 		recipients = [correspondence_email]
		# 		future_time = datetime.utcnow() + timedelta(days=4)
		# 		reminder_email_kwargs = restrict_dict.copy()
		# 		reminder_email_kwargs['subject'] = subject
		# 		reminder_email_kwargs['body'] = body
		# 		reminder_email_kwargs['recipients'] = recipients
		# 		if not os.environ['FLASK_MODE'] == 'TEST': # pragma: no cover - used to exclude this line from calculating test coverage
		# 			# tasks.send_processing_reminder_email.apply_async(
		# 			# 	kwargs=reminder_email_kwargs,eta=future_time) 
		# 			logger.debug("Not running celery task for reminder email while debugging.")
		# 	return redirect(url_for('imaging.imaging_manager'))
		# else:
		# 	logger.info("Not validated")
		# 	logger.info(form.errors)
		# 	flash_str = 'There were errors below. Correct them before proceeding'
		# 	flash(flash_str,'danger')
		# 	if 'image_resolution_forms' in form.errors:
		# 		for error in form.errors['image_resolution_forms']:
		# 			if isinstance(error,dict):
		# 				continue
		# 			flash(error,'danger')

	elif request.method == 'GET': # get request
		logger.debug("GET request")
		if imaging_progress == 'complete':
			logger.info("Imaging already complete but accessing the imaging entry page anyway.")
			flash("Imaging is already complete for this sample. "
				"This page is read only and hitting submit will do nothing",'warning')
		else:
			dj.Table._update(imaging_batch_contents,'imaging_progress','in progress')
		
		""" INITIALIZE BATCH FORM """
		""" Clear out any previously existing image resolution forms """
		while len(form.image_resolution_batch_forms) > 0:
			form.image_resolution_batch_forms.pop_entry() # pragma: no cover - used to exclude this line from calculating test coverage
		for ii in range(len(batch_unique_image_resolutions)):
			this_image_resolution = batch_unique_image_resolutions[ii]
			logger.debug(this_image_resolution)
			image_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
				f'username="{username}" ' & f'request_name="{request_name}" ' & \
				f'sample_name="{first_sample_name}" ' & \
				f'image_resolution="{this_image_resolution}" '
			notes_for_imager = image_resolution_request_contents.fetch1('notes_for_imager')

			channel_contents_list_this_resolution = (batch_channel_contents & f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
			
			form.image_resolution_batch_forms.append_entry()
			this_resolution_form = form.image_resolution_batch_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution

			''' Now add the channel subforms to the image resolution form '''
			used_channels = []
			registration_channel_used = False
			for jj in range(len(channel_contents_list_this_resolution)):
				channel_content = channel_contents_list_this_resolution[jj]
				channel_name = channel_content['channel_name']
				registration_channel = channel_content['registration']
				if registration_channel:
					registration_channel_used = True
				this_resolution_form.channel_forms.append_entry()
				this_channel_form = this_resolution_form.channel_forms[-1]
				this_channel_form.channel_name.data = channel_name
				this_channel_form.image_resolution.data = channel_content['image_resolution']
				used_channels.append(channel_name)
				""" Autofill based on current db contents """
				this_channel_form.tiling_scheme.data = channel_content['tiling_scheme']
				this_channel_form.tiling_overlap.data = channel_content['tiling_overlap']
				this_channel_form.z_step.data = channel_content['z_step']
				this_channel_form.left_lightsheet_used.data = channel_content['left_lightsheet_used']
				this_channel_form.right_lightsheet_used.data = channel_content['right_lightsheet_used']
			all_imaging_channels = current_app.config['IMAGING_CHANNELS']
			available_channels = [x for x in all_imaging_channels if x not in used_channels]
			this_resolution_form.new_channel_dropdown.choices = [(x,x) for x in available_channels]
			available_imaging_modes = current_app.config['IMAGING_MODES']
			if registration_channel_used:
				available_imaging_modes = [x for x in available_imaging_modes if x != 'registration']
			this_resolution_form.new_channel_purpose.choices = [(x,x) for x in available_imaging_modes]
		""" ####################### """
		""" INITIALIZE SAMPLE FORMS """
		""" ####################### """
		while len(form.sample_forms) > 0:
			form.sample_forms.pop_entry() 
		for sample_dict in sample_dict_list:
			this_sample_name = sample_dict['sample_name']
			logger.debug("Initializing sample form for:")
			logger.debug(this_sample_name)
			channel_contents_this_sample = channel_contents_all_samples & \
				f'sample_name="{this_sample_name}"'
			""" Figure out clearing batch and if there were notes_for_clearer """
			this_sample_contents = sample_contents & {'sample_name':this_sample_name}
			clearing_batch_number = this_sample_contents.fetch1('clearing_batch_number')
			clearing_batch_restrict_dict = dict(userame=username,request_name=request_name,
				clearing_batch_number=clearing_batch_number)
			clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & clearing_batch_restrict_dict
			notes_for_clearer = clearing_batch_contents.fetch1('notes_for_clearer')

			form.sample_forms.append_entry()
			this_sample_form = form.sample_forms[-1]
			# this_sample_form.username.data = username
			# this_sample_form.request_name.data = request_name
			this_sample_form.sample_name.data = this_sample_name
			while len(this_sample_form.image_resolution_forms) > 0:
				this_sample_form.image_resolution_forms.pop_entry() # pragma: no cover - used to exclude this line from calculating test coverage
			image_resolution_request_contents_this_sample = db_lightsheet.Request.ImagingResolutionRequest() & \
					f'username="{username}" ' & f'request_name="{request_name}" ' & \
					f'sample_name="{this_sample_name}"' & \
					f'imaging_request_number="{imaging_request_number}" ' 
			unique_image_resolutions_this_sample = sorted(set(image_resolution_request_contents_this_sample.fetch(
				'image_resolution')))
			for ii in range(len(unique_image_resolutions_this_sample)):
				
				this_image_resolution = unique_image_resolutions_this_sample[ii]
				logger.debug("Initializing resolution form for:")
				logger.debug(this_image_resolution)
				this_image_resolution_request_contents = image_resolution_request_contents_this_sample & \
					f'image_resolution="{this_image_resolution}" '
				
				notes_for_imager = this_image_resolution_request_contents.fetch1('notes_for_imager')

				channel_contents_list_this_resolution = (channel_contents_this_sample & \
					f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
				
				this_sample_form.image_resolution_forms.append_entry()
				this_resolution_form = this_sample_form.image_resolution_forms[-1]
				this_resolution_form.image_resolution.data = this_image_resolution

				if notes_for_imager:
					this_resolution_form.notes_for_imager.data = notes_for_imager 
				else:
					this_resolution_form.notes_for_imager.data = 'No special notes'
				if notes_for_clearer:
					this_resolution_form.notes_for_clearer.data = notes_for_clearer 
				else:
					this_resolution_form.notes_for_clearer.data = 'No special notes'
				''' Now add the channel subforms to the image resolution form '''
				used_channels = []
				registration_channel_used = False
				for jj in range(len(channel_contents_list_this_resolution)):
					channel_content = channel_contents_list_this_resolution[jj]
					channel_name = channel_content['channel_name']
					logger.debug("Initializing channel form for:")
					logger.debug(channel_name)
					registration_channel = channel_content['registration']
					if registration_channel:
						registration_channel_used = True
					this_resolution_form.channel_forms.append_entry()
					this_channel_form = this_resolution_form.channel_forms[-1]
					this_channel_form.channel_name.data = channel_name
					this_channel_form.image_resolution.data = this_image_resolution
					used_channels.append(channel_name)
					""" Autofill based on current db contents """
					this_channel_form.tiling_scheme.data = channel_content['tiling_scheme']
					this_channel_form.tiling_overlap.data = channel_content['tiling_overlap']
					this_channel_form.z_step.data = channel_content['z_step']
					this_channel_form.left_lightsheet_used.data = channel_content['left_lightsheet_used']
					this_channel_form.right_lightsheet_used.data = channel_content['right_lightsheet_used']
					this_channel_form.number_of_z_planes.data = channel_content['number_of_z_planes']
					this_channel_form.rawdata_subfolder.data = channel_content['rawdata_subfolder']
				all_imaging_channels = current_app.config['IMAGING_CHANNELS']
				available_channels = [x for x in all_imaging_channels if x not in used_channels]
				this_resolution_form.new_channel_dropdown.choices = [(x,x) for x in available_channels]
				available_imaging_modes = current_app.config['IMAGING_MODES']
				if registration_channel_used:
					available_imaging_modes = [x for x in available_imaging_modes if x != 'registration']
				this_resolution_form.new_channel_purpose.choices = [(x,x) for x in available_imaging_modes]	
	n_active_samples = len([x for x in samples_imaging_progress_dict if samples_imaging_progress_dict[x] != 'complete'])
	
	return render_template('imaging/imaging_batch_entry.html',form=form,
		rawdata_rootpath=rawdata_rootpath,imaging_table=imaging_table,
		sample_dict_list=sample_dict_list,
		samples_imaging_progress_dict=samples_imaging_progress_dict,
		n_active_samples=n_active_samples)

@imaging.route("/imaging/imaging_entry/<username>/<request_name>/<imaging_batch_number>",methods=['GET','POST'])
@logged_in
@logged_in_as_imager
@check_clearing_completed
@log_http_requests
def imaging_entry(username,request_name,imaging_batch_number): 
	""" Route for handling form data for
	parameters used to image a dataset.
	"""

	form = ImagingForm(request.form)
	form.username.data = username
	form.request_name.data = request_name
	form.sample_name.data = sample_name
	form.imaging_request_number.data = imaging_request_number
	sample_contents = db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'imaging_batch_number="{imaging_batch_number}"' 
	clearing_protocol,antibody1,antibody2,clearing_batch_number = sample_contents.fetch1(
		'clearing_protocol',
		'antibody1','antibody2','clearing_batch_number')
	clearing_batch_restrict_dict = dict(userame=username,request_name=request_name,
		sample_name=sample_name,
		clearing_protocol=clearing_protocol,
		antibody1=antibody1,
		antibody2=antibody2,
		clearing_batch_number=clearing_batch_number)
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & clearing_batch_restrict_dict
	notes_for_clearer = clearing_batch_contents.fetch1('notes_for_clearer')
	# imaging_request_contents = db_lightsheet.Request.ImagingRequest() & f'request_name="{request_name}"' & \
	# 		f'username="{username}"' & f'sample_name="{sample_name}"' & \
	# 		f'imaging_request_number="{imaging_request_number}"' 

	""" Figure out how many samples in this imaging batch """
	imaging_batch_restrict_dict = dict(userame=username,request_name=request_name,
		imaging_batch_number=imaging_batch_number)
	imaging_batch_contents = db_lightsheet.Request.ImagingBatch() & imaging_batch_restrict_dict
	number_in_batch = imaging_batch_contents.fetch1('number_in_batch')
	logger.debug("Number in batch:")
	logger.debug(number_in_batch)
	
	imaging_progress = imaging_batch_contents.fetch1('imaging_progress')
	
	""" Assemble the imaging subforms """	
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
	overview_dict = imaging_batch_contents.fetch1()
	imaging_table = ImagingTable(imaging_batch_contents*sample_contents)


	if request.method == 'POST':
		logger.info("Post request")
		""" Check to see if a button other than the final submit was pressed """
		if form.submit.data == False:
			logger.debug("Update or new channel button pressed")
			""" Figure out which image resolution form this submit came from """
			for form_resolution_dict in form.image_resolution_forms.data:
				logger.debug(form_resolution_dict)
				this_image_resolution =  form_resolution_dict['image_resolution']
				logger.debug("Image resolution:")
				logger.debug(this_image_resolution)
				update_resolution_button_pressed = form_resolution_dict['update_resolution_button']
				new_channel_button_pressed = form_resolution_dict['new_channel_button']
				if new_channel_button_pressed:
					logger.debug("New channel button pressed!")
					new_channel_name = form_resolution_dict['new_channel_dropdown']
					new_channel_purpose = form_resolution_dict['new_channel_purpose']
					logger.debug("Have new channel:")
					logger.debug(new_channel_name)
					""" Create a new ImagingChannel() entry for this channel """
					imaging_channel_entry_dict = {}
					imaging_channel_entry_dict['username'] = username
					imaging_channel_entry_dict['request_name'] = request_name
					imaging_channel_entry_dict['sample_name'] = sample_name
					imaging_channel_entry_dict['imaging_request_number'] = imaging_request_number
					imaging_channel_entry_dict['image_resolution'] = this_image_resolution
					imaging_channel_entry_dict['channel_name'] = new_channel_name
					imaging_channel_entry_dict[new_channel_purpose] = 1
					db_lightsheet.Request.ImagingChannel().insert1(imaging_channel_entry_dict)
					return redirect(url_for('imaging.imaging_entry',
						username=username,request_name=request_name,sample_name=sample_name,imaging_request_number=imaging_request_number))
				elif update_resolution_button_pressed:
					logger.debug("Update image resolution button pressed!")
					new_image_resolution = form_resolution_dict['new_image_resolution']
					logger.debug("New image resolution is:")
					logger.debug(new_image_resolution)
					
					""" Update image resolution in all locations in the database """
					image_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
						f'username="{username}" ' & f'request_name="{request_name}" ' & \
						f'sample_name="{sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
						f'image_resolution="{this_image_resolution}"'
					
					image_resolution_request_insert_dict = image_resolution_request_contents.fetch1()
					
					imaging_channel_request_contents = db_lightsheet.Request.ImagingChannel() & \
						f'username="{username}" ' & f'request_name="{request_name}" ' & \
						f'sample_name="{sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
						f'image_resolution="{this_image_resolution}" '
					
					imaging_channel_dicts = imaging_channel_request_contents.fetch(as_dict=True)
					
					""" First delete each ImagingChannel() entry """
					imaging_channel_dicts_to_insert = [d for d in imaging_channel_dicts]
					dj.config['safemode'] = False
					imaging_channel_request_contents.delete(force=True)
					
					""" And delete ProcessingChannel() entries tied to this imaging request as well,
					if they exist (they might not if somone had requested 2x imaging only) """
					processing_channel_request_contents = db_lightsheet.Request.ProcessingChannel() & \
						f'username="{username}" ' & f'request_name="{request_name}" ' & \
						f'sample_name="{sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
						f'image_resolution="{this_image_resolution}" '
					processing_channel_dicts = processing_channel_request_contents.fetch(as_dict=True)
					processing_channel_dicts_to_insert = [d for d in processing_channel_dicts]
					if len(processing_channel_request_contents) > 0:
						processing_channel_request_contents.delete(force=True)
					""" Now delete ProcessingResolutionRequest() entry """
					processing_resolution_request_contents = db_lightsheet.Request.ProcessingResolutionRequest() & \
						f'username="{username}" ' & f'request_name="{request_name}" ' & \
						f'sample_name="{sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
						f'image_resolution="{this_image_resolution}"'
					
					if len(processing_resolution_request_contents) > 0: 
						logger.debug("ProcessingResolutionRequest() entry already existed")
						processing_resolution_request_insert_dict = processing_resolution_request_contents.fetch1()
						processing_resolution_request_contents.delete(force=True)
					else:
						logger.debug("Making an entirely new ProcessingResolutionRequest() entry")
						processing_resolution_request_insert_dict = {}
						processing_resolution_request_insert_dict['request_name'] = request_name
						processing_resolution_request_insert_dict['username'] = username 
						processing_resolution_request_insert_dict['sample_name'] = sample_name
						processing_resolution_request_insert_dict['imaging_request_number'] = imaging_request_number
						processing_resolution_request_insert_dict['processing_request_number'] = 1
						processing_resolution_request_insert_dict['image_resolution'] = new_image_resolution

					""" Now delete ImagingResolutionRequest() entry """
					image_resolution_request_contents.delete(force=True)
					""" Reset to whatever safemode was before the switch """
					dj.config['safemode'] = current_app.config['DJ_SAFEMODE']

					""" Now make the inserts with the updated image_resolution value """
					""" First ImagingResolutionRequest() """
					image_resolution_request_insert_dict['image_resolution'] = new_image_resolution
					db_lightsheet.Request.ImagingResolutionRequest().insert1(
						image_resolution_request_insert_dict)
					""" Now ImagingChannel() """
					[d.update({'image_resolution':new_image_resolution}) for d in imaging_channel_dicts_to_insert]
					db_lightsheet.Request.ImagingChannel().insert(imaging_channel_dicts_to_insert)
					
					""" For processing inserts, make sure that at least one image resolution
					for this imaging requests including the new resolution merits a processing request,
					i.e. it is in the list of resolutions we are capable processing.
					If there are now no resolutions we can process, 
					then we need to remove the processing request if it exists """
					image_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
						f'username="{username}" ' & f'request_name="{request_name}" ' & \
						f'sample_name="{sample_name}" ' & f'imaging_request_number={imaging_request_number}'
					image_resolutions_used = image_resolution_request_contents.fetch('image_resolution')
					bad_image_resolutions = current_app.config['RESOLUTIONS_NO_PROCESSING']
					any_good_resolutions = any([res not in bad_image_resolutions for res in image_resolutions_used])
					logger.debug(any_good_resolutions)
					logger.debug("image_resolutions_used:")
					logger.debug(image_resolutions_used)

					if not any_good_resolutions:
						logger.debug("There are no image resolutions that we can process")
						# Remove processing request entry if it exists
						processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
							f'username="{username}" ' & f'request_name="{request_name}" ' & \
							f'sample_name="{sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
							'processing_request_number=1'
						if len(processing_request_contents) > 0:
							dj.config['safemode'] = False
							processing_request_contents.delete(force=True)
							dj.config['safemode'] = current_app.config['DJ_SAFEMODE']
					else:
						""" There are some resolutions that we can process, so insert those 
						entries """
						
						# First make sure that there is a processing request, if not then make one
						
						processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
							f'username="{username}" ' & f'request_name="{request_name}" ' & \
							f'sample_name="{sample_name}" ' & f'imaging_request_number={imaging_request_number}' & \
							'processing_request_number=1'
						
						if len(processing_request_contents) == 0:
							now = datetime.now()
							date = now.strftime("%Y-%m-%d")
							time = now.strftime("%H:%M:%S") 
							processing_request_insert_dict = {}
							processing_request_number = 1
							processing_request_insert_dict['request_name'] = request_name
							processing_request_insert_dict['username'] = username 
							processing_request_insert_dict['sample_name'] = sample_name
							processing_request_insert_dict['imaging_request_number'] = imaging_request_number
							processing_request_insert_dict['processing_request_number'] = 1
							processing_request_insert_dict['processing_request_date_submitted'] = date
							processing_request_insert_dict['processing_request_time_submitted'] = time
							processing_request_insert_dict['processing_progress'] = "incomplete"
							
							db_lightsheet.Request.ProcessingRequest().insert1(processing_request_insert_dict)
							logger.debug("Inserted a ProcessingRequest() entry since one did not already exist")
						""" If this new resolution is one we can process then add resolution and channel entries for it """
						if new_image_resolution not in bad_image_resolutions:
							""" Now ProcessingResolutionRequest() """
							processing_resolution_request_insert_dict['image_resolution'] = new_image_resolution
							logger.debug("Going to insert:")
							logger.debug(processing_resolution_request_insert_dict)
							db_lightsheet.Request.ProcessingResolutionRequest().insert1(
								processing_resolution_request_insert_dict)
							""" Finally ProcessingChannel() """
							[d.update({'image_resolution':new_image_resolution}) for d in processing_channel_dicts_to_insert]
							db_lightsheet.Request.ProcessingChannel().insert(processing_channel_dicts_to_insert)
							logger.debug("Updated image resolution in all 4 tables: ")
							logger.debug("ImagingChannel(), ImagingResolutionRequest(), ProcessingChannel(), ProcessingResolutionRequest ")
					return redirect(url_for('imaging.imaging_entry',
						username=username,request_name=request_name,sample_name=sample_name,imaging_request_number=imaging_request_number))
		elif form.validate_on_submit():
			logger.info("form validated")
			imaging_progress = imaging_request_contents.fetch1('imaging_progress')
			
			if imaging_progress == 'complete':
				logger.info("Imaging is already complete so hitting the submit button again did nothing")
				return redirect(url_for('imaging.imaging_entry',username=username,
				request_name=request_name,sample_name=sample_name,imaging_request_number=imaging_request_number))
			
			""" loop through the image resolution forms and find all channel entries"""

			""" Loop through the image resolution forms and find all channels in the form  
			and update the existing table entries with the new imaging information """
			
			for form_resolution_dict in form.image_resolution_forms.data:
				subfolder_dict = {}
				image_resolution = form_resolution_dict['image_resolution']
				""" Make rawdata/ subdirectories for this resolution """
				imaging_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
								 request_name,sample_name,f"imaging_request_{imaging_request_number}",
								 "rawdata",f"resolution_{image_resolution}")
				mymkdir(imaging_dir)
				for form_channel_dict in form_resolution_dict['channel_forms']:
					channel_name = form_channel_dict['channel_name']
					rawdata_subfolder = form_channel_dict['rawdata_subfolder']
					number_of_z_planes = form_channel_dict['number_of_z_planes']
					tiling_scheme = form_channel_dict['tiling_scheme']
					z_step = form_channel_dict['z_step']
					left_lightsheet_used = form_channel_dict['left_lightsheet_used']
					right_lightsheet_used = form_channel_dict['right_lightsheet_used']
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
			
					db_lightsheet.Request.ImagingChannel().insert1(channel_insert_dict,replace=True)
					""" Kick off celery task for creating precomputed data from this
					raw data image dataset if there is more than one tile.
					"""
					if tiling_scheme == '1x1':
						logger.info("Only one tile. Creating precomputed data for neuroglancer visualization. ")
						precomputed_kwargs = dict(username=username,request_name=request_name,
												sample_name=sample_name,imaging_request_number=imaging_request_number,
												image_resolution=image_resolution,channel_name=channel_name,
												channel_index=channel_index,number_of_z_planes=number_of_z_planes,
												left_lightsheet_used=left_lightsheet_used,
												right_lightsheet_used=right_lightsheet_used,
												z_step=z_step,rawdata_subfolder=rawdata_subfolder)
						raw_viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
								 f"{request_name}/{sample_name}/"
								 f"imaging_request_{imaging_request_number}/viz/raw")

						mymkdir(raw_viz_dir)
						channel_viz_dir = os.path.join(raw_viz_dir,f'channel_{channel_name}')
						mymkdir(channel_viz_dir)
						raw_data_dir = os.path.join(imaging_dir,rawdata_subfolder)
						logger.debug("raw data dir:")
						logger.debug(raw_data_dir)
						if left_lightsheet_used:
							this_viz_dir = os.path.join(channel_viz_dir,'left_lightsheet')
							mymkdir(this_viz_dir)
							precomputed_kwargs['lightsheet'] = 'left'
							precomputed_kwargs['viz_dir'] = this_viz_dir
							layer_name = f'channel{channel_name}_raw_left_lightsheet'
							precomputed_kwargs['layer_name'] = layer_name
							layer_dir = os.path.join(this_viz_dir,layer_name)
							mymkdir(layer_dir)
							# Figure out what x and y dimensions are
							lightsheet_index_code = 'C00' # always for left lightsheet
							precomputed_kwargs['lightsheet_index_code'] = lightsheet_index_code
							all_slices = glob.glob(
								f"{raw_data_dir}/*RawDataStack[00 x 00*{lightsheet_index_code}*Filter000{channel_index}*tif")
							first_slice = all_slices[0]
							first_im = Image.open(first_slice)
							x_dim,y_dim = first_im.size
							precomputed_kwargs['x_dim'] = x_dim
							precomputed_kwargs['y_dim'] = y_dim
							first_im.close() 
							if not os.environ['FLASK_MODE'] == 'TEST': 
								tasks.make_precomputed_rawdata.delay(**precomputed_kwargs) # pragma: no cover - used to exclude this line from calculating test coverage 
						if right_lightsheet_used:
							this_viz_dir = os.path.join(channel_viz_dir,'right_lightsheet')
							mymkdir(this_viz_dir)
							precomputed_kwargs['lightsheet'] = 'right'
							precomputed_kwargs['viz_dir'] = this_viz_dir
							layer_name = f'channel{channel_name}_raw_right_lightsheet'
							precomputed_kwargs['layer_name'] = layer_name
							layer_dir = os.path.join(this_viz_dir,layer_name)
							mymkdir(layer_dir)
							
							# figure out whether to look for C00 or C01 files
							if left_lightsheet_used:
								lightsheet_index_code = 'C01'
							else: 
								# right light sheet was the only one used so looking for C00 files
								lightsheet_index_code = 'C00'
							precomputed_kwargs['lightsheet_index_code'] = lightsheet_index_code
							# Figure out what x and y dimensions are
							all_slices = glob.glob(f"{raw_data_dir}/*RawDataStack[00 x 00*{lightsheet_index_code}*Filter000{channel_index}*tif")
							first_slice = all_slices[0]
							first_im = Image.open(first_slice)
							x_dim,y_dim = first_im.size
							precomputed_kwargs['x_dim'] = x_dim
							precomputed_kwargs['y_dim'] = y_dim
							first_im.close()
							if not os.environ['FLASK_MODE'] == 'TEST': 
								tasks.make_precomputed_rawdata.delay(**precomputed_kwargs) # pragma: no cover - used to exclude this line from calculating test coverage 
					else:
						logger.info(f"Tiling scheme: {tiling_scheme} means there is more than one tile. "
									 "Not creating precomputed data for neuroglancer visualization.")
				
			correspondence_email = (db_lightsheet.Request() & f'username="{username}"' & \
			 f'request_name="{request_name}"').fetch1('correspondence_email')
			data_rootpath = current_app.config["DATA_BUCKET_ROOTPATH"]
			path_to_data = (f'{data_rootpath}/{username}/{request_name}/'
							 f'{sample_name}/imaging_request_number_{imaging_request_number}/rawdata')
			""" Send email """
			subject = 'Lightserv automated email: Imaging complete'
			hosturl = os.environ['HOSTURL']

			processing_manager_url = f'https://{hosturl}' + url_for('processing.processing_manager')

			message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
						'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
						'The raw data for your request:\n'
						f'request_name: "{request_name}"\n'
						f'sample_name: "{sample_name}"\n'
						f'are now available on bucket here: {path_to_data}\n\n'
						 'To start processing your data, '
						f'go to the processing management GUI: {processing_manager_url} '
						'and find your sample to process.\n\n'
						 'Thanks,\n\nThe Core Facility')
			request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
			correspondence_email = request_contents.fetch1('correspondence_email')
			recipients = [correspondence_email]
			if not os.environ['FLASK_MODE'] == 'TEST':
				send_email.delay(subject=subject,body=message_body,recipients=recipients) # pragma: no cover - used to exclude this line from calculating test coverage
			flash(f"""Imaging is complete. An email has been sent to {correspondence_email} 
				informing them that their raw data is now available on bucket.
				The processing pipeline is now ready to run. ""","success")
			dj.Table._update(imaging_request_contents,'imaging_progress','complete')
			now = datetime.now()
			date = now.strftime('%Y-%m-%d')
			dj.Table._update(imaging_request_contents,'imaging_performed_date',date)
			
			""" Finally, set up the 4-day reminder email that will be sent if 
			user still has not submitted processing request (provided that there exists a processing 
			request for this imaging request) """

			""" First check if there is a processing request for this imaging request.
			This will be processing_request_number=1 because we are in the imaging entry
			form here. """
			restrict_dict = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=1)
			processing_request_contents = db_lightsheet.Request.ProcessingRequest() & restrict_dict
			if len(processing_request_contents) > 0:
				subject = 'Lightserv automated email. Reminder to start processing.'
				body = ('Hello, this is a reminder that you still have not started '
						'the data processing pipeline for your sample:.\n\n'
						f'request_name: {request_name}\n'
						f'sample_name: {sample_name}\n\n'
						'To start processing your data, '
						f'go to the processing management GUI: {processing_manager_url} '
						'and find your sample to process.\n\n'
						'Thanks,\nThe Brain Registration and Histology Core Facility')    
				logger.debug("Sending reminder email 4 days in the future")
				request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
				correspondence_email = request_contents.fetch1('correspondence_email')
				recipients = [correspondence_email]
				future_time = datetime.utcnow() + timedelta(days=4)
				reminder_email_kwargs = restrict_dict.copy()
				reminder_email_kwargs['subject'] = subject
				reminder_email_kwargs['body'] = body
				reminder_email_kwargs['recipients'] = recipients
				if not os.environ['FLASK_MODE'] == 'TEST': # pragma: no cover - used to exclude this line from calculating test coverage
					# tasks.send_processing_reminder_email.apply_async(
					# 	kwargs=reminder_email_kwargs,eta=future_time) 
					logger.debug("Not running celery task for reminder email while debugging.")
			return redirect(url_for('imaging.imaging_manager'))
		else:
			logger.info("Not validated")
			logger.info(form.errors)
			flash_str = 'There were errors below. Correct them before proceeding'
			flash(flash_str,'danger')
			if 'image_resolution_forms' in form.errors:
				for error in form.errors['image_resolution_forms']:
					if isinstance(error,dict):
						continue
					flash(error,'danger')

	elif request.method == 'GET': # get request
		logger.debug("GET request")
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
				form.image_resolution_forms.pop_entry() # pragma: no cover - used to exclude this line from calculating test coverage
			form.image_resolution_forms.append_entry()
			this_resolution_form = form.image_resolution_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution

			if notes_for_imager:
				this_resolution_form.notes_for_imager.data = notes_for_imager 
			else:
				this_resolution_form.notes_for_imager.data = 'No special notes'
			if notes_for_clearer:
				this_resolution_form.notes_for_clearer.data = notes_for_clearer 
			else:
				this_resolution_form.notes_for_clearer.data = 'No special notes'
			''' Now add the channel subforms to the image resolution form '''
			used_channels = []
			registration_channel_used = False
			for jj in range(len(channel_contents_list_this_resolution)):
				channel_content = channel_contents_list_this_resolution[jj]
				channel_name = channel_content['channel_name']
				registration_channel = channel_content['registration']
				if registration_channel:
					registration_channel_used = True
				this_resolution_form.channel_forms.append_entry()
				this_channel_form = this_resolution_form.channel_forms[-1]
				this_channel_form.channel_name.data = channel_name
				this_channel_form.image_resolution.data = channel_content['image_resolution']
				used_channels.append(channel_name)
				""" Autofill for convenience in dev mode """
				if os.environ['FLASK_MODE'] == 'DEV':
					this_channel_form.tiling_scheme.data = "1x1"
					this_channel_form.tiling_overlap.data = 0.0
					this_channel_form.z_step.data = 5.0
					this_channel_form.number_of_z_planes.data = 1258
					this_channel_form.left_lightsheet_used.data = True

					# this_channel_form.rawdata_subfolder.data = '200221_20180220_jg_09_4x_647_008na_1hfds_z2um_100msec_15povlp_14-16-13'
					this_channel_form.rawdata_subfolder.data = 'test488'
			all_imaging_channels = current_app.config['IMAGING_CHANNELS']
			available_channels = [x for x in all_imaging_channels if x not in used_channels]
			this_resolution_form.new_channel_dropdown.choices = [(x,x) for x in available_channels]
			available_imaging_modes = current_app.config['IMAGING_MODES']
			if registration_channel_used:
				available_imaging_modes = [x for x in available_imaging_modes if x != 'registration']
			this_resolution_form.new_channel_purpose.choices = [(x,x) for x in available_imaging_modes]
	rawdata_filepath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
		overview_dict['username'],overview_dict['request_name'],
		overview_dict['sample_name'],
		'imaging_request_{}'.format(overview_dict['imaging_request_number']),
		'rawdata/')
	return render_template('imaging/imaging_entry.html',form=form,
		channel_contents_lists=channel_contents_lists,
		rawdata_filepath=rawdata_filepath,imaging_table=imaging_table)

@imaging.route("/imaging/new_imaging_request/<username>/<request_name>/<sample_name>/",
	methods=['GET','POST'])
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
	request_contents = db_lightsheet.Request() & {'username':username,'request_name':request_name}
	species = request_contents.fetch1('species')
	form.species.data = species
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

					""" Make the directory on /jukebox corresponding to this imaging request """
					raw_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
						username,request_name,sample_name,f'imaging_request_{new_imaging_request_number}',
						'rawdata')
					output_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
						username,request_name,sample_name,f'imaging_request_{new_imaging_request_number}',
						'output')
					viz_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
						username,request_name,sample_name,f'imaging_request_{new_imaging_request_number}',
						'viz')
					mymkdir(raw_path_to_make)
					mymkdir(output_path_to_make)
					mymkdir(viz_path_to_make)

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


					""" Now set up inserts for each image resolution/channel combo """
					imaging_resolution_insert_list = []
					processing_resolution_insert_list = []
					channel_insert_list = []
					for resolution_dict in form.image_resolution_forms.data:
						image_resolution = resolution_dict['image_resolution']
						""" imaging entry first """
						imaging_resolution_insert_dict = {}
						imaging_resolution_insert_dict['request_name'] = request_name
						imaging_resolution_insert_dict['username'] = username 
						imaging_resolution_insert_dict['sample_name'] = sample_name
						imaging_resolution_insert_dict['imaging_request_number'] = new_imaging_request_number
						imaging_resolution_insert_dict['image_resolution'] = image_resolution
						imaging_resolution_insert_dict['notes_for_imager'] = resolution_dict['notes_for_imager']
						imaging_resolution_insert_list.append(imaging_resolution_insert_dict)
						""" now processing entry """
						if image_resolution != '2x':
							processing_resolution_insert_dict = {}
							processing_resolution_insert_dict['request_name'] = request_name
							processing_resolution_insert_dict['username'] = username 
							processing_resolution_insert_dict['sample_name'] = sample_name
							processing_resolution_insert_dict['imaging_request_number'] = new_imaging_request_number
							processing_resolution_insert_dict['processing_request_number'] = processing_request_number
							processing_resolution_insert_dict['image_resolution'] = image_resolution
							processing_resolution_insert_dict['notes_for_processor'] = resolution_dict['notes_for_processor']
							processing_resolution_insert_dict['final_orientation'] = resolution_dict['final_orientation']
							processing_resolution_insert_dict['atlas_name'] = resolution_dict['atlas_name']
							processing_resolution_insert_list.append(processing_resolution_insert_dict)
							""" Make processing path on /jukebox """
							processing_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
							username,request_name,sample_name,f'imaging_request_{new_imaging_request_number}',
							'output',f'processing_request_{processing_request_number}',f'resolution_{image_resolution}')
							mymkdir(processing_path_to_make)

						""" Now loop through channels and make insert dict for each """
						for imaging_channel_dict in resolution_dict['channels']:
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
										continue # pragma: no cover - used to exclude this line from calculating test coverage
									channel_insert_dict[key] = val

								channel_insert_list.append(channel_insert_dict)
					
					logger.info('ImagingResolutionRequest() insert:')
					logger.info(imaging_resolution_insert_list)
					db_lightsheet.Request.ImagingResolutionRequest().insert(imaging_resolution_insert_list)		

					""" Only enter a processing request if there are processing resolution requests,
					i.e. image resolutions that are not 2x. We do not process 2x data sets. """
					if len(processing_resolution_insert_list) > 0:
						logger.info('ProcessingRequest() insert:')
						logger.info(processing_request_insert_dict)
						db_lightsheet.Request.ProcessingRequest().insert1(processing_request_insert_dict)
						processing_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
							username,request_name,sample_name,f'imaging_request_{new_imaging_request_number}',
							'output',f'processing_request_{processing_request_number}')
						mymkdir(processing_path_to_make)

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

@imaging.route("/imaging/imaging_table/<username>/<request_name>/<sample_name>/<imaging_request_number>",methods=['GET','POST'])
@check_clearing_completed
@check_imaging_completed
@log_http_requests
def imaging_table(username,request_name,sample_name,imaging_request_number): 
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & \
			f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' 
	sample_contents = db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' 
	imaging_overview_table = ImagingTable(imaging_request_contents*sample_contents)
	imaging_progress = imaging_request_contents.fetch1('imaging_progress')
	
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & \
				f'request_name="{request_name}"' & \
				f'username="{username}"' & f'sample_name="{sample_name}"' & \
				f'imaging_request_number="{imaging_request_number}"' 
	imaging_channel_table = ImagingChannelTable(imaging_channel_contents)

	return render_template('imaging/imaging_log.html',
		imaging_overview_table=imaging_overview_table,
		imaging_channel_table=imaging_channel_table)
