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
from .forms import (ImagingForm, NewImagingRequestForm, ImagingBatchForm)
from . import tasks
from lightserv.main.tasks import send_email
import numpy as np
import datajoint as dj
import os,re
from datetime import datetime, timedelta
import logging
import glob
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
	reverse = (request.args.get('direction', 'desc') == 'desc')

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
	contents_already_imaged = (imaging_request_contents & 'imaging_progress="complete"').fetch(
		as_dict=True,order_by='datetime_submitted DESC',limit=10,)
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
@logged_in_as_imager
@log_http_requests
def imaging_batch_entry(username,request_name,imaging_batch_number): 
	""" Route for handling form data entered for imaging 
	samples in batch entry form
	"""
	current_user = session['user']
	logger.info(f"{current_user} accessed imaging_batch_entry")

	form = ImagingBatchForm(request.form)
	rawdata_rootpath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
		username,request_name)
	imaging_request_number = 1 # TODO - make this variable to allow follow up imaging requests
	sample_contents = db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'imaging_batch_number={imaging_batch_number}' 
	
	sample_dict_list = sample_contents.fetch(as_dict=True)

	""" Figure out how many samples in this imaging batch """
	imaging_batch_restrict_dict = dict(username=username,request_name=request_name,
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
						flash_str_prefix = (f"Issue with batch parameters for image resolution: {batch_image_resolution},"
											f" channel: {channel_name}. ")
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

						else:
							try:
								n_rows = int(tiling_scheme.lower().split('x')[0])
								n_columns = int(tiling_scheme.lower().split('x')[1])
								if batch_image_resolution in ['1.1x','1.3x'] and (n_rows > 2 or n_columns > 2):
									flash_str = flash_str_prefix + ("Tiling scheme must not exceed 2x2 for this resolution")
									batch_channel_form.tiling_scheme.errors = ['Tiling scheme must not exceed 2x2 for this resolution']
									flash(flash_str,"danger")
									batch_validated=False
									
								elif batch_image_resolution in ['2x','4x'] and (n_rows > 4 or n_columns > 4):
									flash_str = flash_str_prefix + ("Tiling scheme must not exceed 4x4 for this resolution")
									batch_channel_form.tiling_scheme.errors = ['Tiling scheme must not exceed 4x4 for this resolution']
									flash(flash_str,"danger")
									batch_validated=False
								elif batch_image_resolution == '3.6x' and (n_rows > 10 or n_columns > 10):
									flash_str = flash_str_prefix + ("Tiling scheme must not exceed 10x10 for this resolution")
									batch_channel_form.tiling_scheme.errors = ['Tiling scheme must not exceed 10x10 for this resolution']
									flash(flash_str,"danger")
									batch_validated=False
							except:
								batch_channel_form.tiling_scheme.errors = ['Incorrect format']
								flash_str = flash_str_prefix + ("Tiling scheme is not in correct format."
												  " Make sure it is like: 3x4 with no spaces.")	
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
				try to make db inserts. It is possible that 
				sample forms are not homogenous anymore (due to user
				changing the individual imaging resolution of a single
				sample). In this case, don't batch apply.
				"""
				if all_batch_channels_validated:
					logger.debug("All batch channels validated")
					# logger.debug("Sample forms:")
					logger.debug(form.sample_forms.data)
					connection = db_lightsheet.Request.ImagingChannel.connection
					issues_applying_batch_parameters=False
					with connection.transaction:
						for sample_form in form.sample_forms:
							this_sample_name = sample_form.sample_name.data
							logger.debug("this sample name:")
							logger.debug(this_sample_name)

							for ii in range(len(batch_image_resolution_forms)):
								batch_image_resolution_form = batch_image_resolution_forms[ii]
								batch_image_resolution = batch_image_resolution_form.image_resolution.data
								logger.debug("this image resolution:")
								logger.debug(batch_image_resolution)
								sample_image_resolution_form = sample_form.image_resolution_forms[ii]
								batch_channel_forms = batch_image_resolution_form.channel_forms
								sample_channel_forms = sample_image_resolution_form.channel_forms
								all_batch_channels_validated = True 
								for jj in range(len(batch_channel_forms)):
									batch_channel_form = batch_channel_forms[jj]
									ventral_up = batch_channel_form.ventral_up.data
									logger.debug("Ventral up set to:")
									logger.debug(ventral_up)
									this_channel_name = batch_channel_form.channel_name.data
									logger.debug("this channel name:")
									logger.debug(this_channel_name)
									channel_insert_dict = {
										'username':username,
										'request_name':request_name,
										'sample_name':this_sample_name,
										'imaging_request_number':imaging_request_number,
										'image_resolution':batch_image_resolution,
										'channel_name':this_channel_name,
										'zoom_body_magnification':batch_channel_form.zoom_body_magnification.data,
										'image_orientation':batch_channel_form.image_orientation.data,
										'ventral_up':ventral_up,
										'left_lightsheet_used':batch_channel_form.left_lightsheet_used.data,
										'right_lightsheet_used':batch_channel_form.right_lightsheet_used.data,
										'tiling_scheme':batch_channel_form.tiling_scheme.data,
										'tiling_overlap':batch_channel_form.tiling_overlap.data,
										'z_step':batch_channel_form.z_step.data
									}
									logger.debug("channel insert:")
									logger.debug(channel_insert_dict)
									# try:
									db_lightsheet.Request.ImagingChannel().insert1(channel_insert_dict,replace=True)
									# except:
									# 	issues_applying_batch_parameters=True
									# 	logger.debug("Issue making channel insert: ")
									# 	logger.debug(channel_insert_dict)
									# 	flash_str = (f"Issue applying batch parameters from "
									# 				 f"image resolution: {batch_image_resolution}, "
									# 				 f"channel: {this_channel_name} "
									# 				 f"to sample_name: {this_sample_name}")
									# 	flash(flash_str,"warning")
					if not issues_applying_batch_parameters:
						flash("Batch parameters successfully applied to samples","success")
					else:
						flash("Otherwise parameters were applied OK ","warning")
				else:
					logger.debug("Batch channel validation failed. Not applying batch parameters to all samples")
				return redirect(url_for('imaging.imaging_batch_entry',
							username=username,request_name=request_name,
							imaging_batch_number=imaging_batch_number))
			else:
				""" A few possibilites: 
				1) A sample submit button was pressed
				2) A batch update resolution or add/delete image channel button was pressed
				3) A sample update resolution or add/delete image channel button was pressed
				"""

				""" First check if BATCH add/delete channel button pressed or 
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
						""" ################################ """
						""" BATCH ADD CHANNEL BUTTON PRESSED """
						""" ################################ """
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
						issues_adding_channels = False
						""" Now go through all of the samples in this batch 
						and make an insert in the db for a new channel """
						for sample_dict in sample_dict_list:
							this_sample_name = sample_dict['sample_name']
							imaging_channel_entry_dict = batch_channel_entry_dict.copy()
							imaging_channel_entry_dict['sample_name'] = this_sample_name
							logger.debug("Attempting to insert:")
							logger.debug(imaging_channel_entry_dict)
							try:					
								db_lightsheet.Request.ImagingChannel().insert1(imaging_channel_entry_dict)
							except:
								issues_adding_channels = True
								logger.debug(f"Issue adding channel entry to sample: {this_sample_name}")
								flash_str = (f"Issue adding channel to "
											 f"image resolution: {this_image_resolution}, "
											 f"channel: {new_channel_name} "
											 f"for sample_name: {this_sample_name}")
								flash(flash_str,"warning")
									
						""" restore safemode to whatever it was before we did the deletes """
						if not issues_adding_channels:
							flash(f"Channel {new_channel_name} successfully added to all samples","success")
						else:
							flash("Otherwise channel was added OK","warning")
						return redirect(url_for('imaging.imaging_batch_entry',
							username=username,request_name=request_name,
							imaging_batch_number=imaging_batch_number))
					
					elif update_resolution_button_pressed:
						""" ###################################### """
						""" BATCH CHANGE IMAGE RESOLUTION BUTTON PRESSED """
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
					else:
						""" Search the channel forms of this image resolution form to see
						if a channel delete or add flipped channel button was pressed """
						for channel_form in image_resolution_form.channel_forms:
							channel_form_dict = channel_form.data
							delete_channel_button_pressed = channel_form_dict['delete_channel_button']
							add_flipped_channel_button_pressed = channel_form_dict['add_flipped_channel_button']
							if delete_channel_button_pressed:
								""" ################################### """
								""" BATCH DELETE CHANNEL BUTTON PRESSED """
								""" ################################### """
								logger.debug("delete channel button pressed!")
								channel_name_to_delete = channel_form_dict['channel_name']
								this_image_resolution = channel_form_dict['image_resolution']
								ventral_up = channel_form_dict['ventral_up']
								logger.debug("Deleting channel:")
								logger.debug(channel_name_to_delete)

								""" Create a new ImagingChannel() entry for this channel """
								dj.config['safemode'] = False # disables integrity checks so delete can take place
								issues_deleting_channels = False
								for sample_dict in sample_dict_list:
									this_sample_name = sample_dict['sample_name']
									restrict_dict = {'sample_name':this_sample_name,
										'image_resolution':this_image_resolution,
										'channel_name':channel_name_to_delete,
										'ventral_up':ventral_up}
									imaging_channel_contents_to_delete = channel_contents_all_samples & restrict_dict
									logger.debug("Deleting entry:")
									logger.debug(imaging_channel_contents_to_delete.fetch1())
									if len(imaging_channel_contents_to_delete) > 0:
										try:
											imaging_channel_contents_to_delete.delete(force=True)
										except:
											issues_deleting_channels=True
											logger.debug("Issue deleting channel entry")
											flash_str = (f"Issue deleting channel from "
														 f"image resolution: {image_resolution}, "
														 f"channel: {channel_name_to_delete} "
														 f"for sample_name: {this_sample_name}")
											flash(flash_str,"warning")
									
								""" restore safemode to whatever it was before we did the deletes """
								dj.config['safemode'] = current_app.config['DJ_SAFEMODE']
								if not issues_deleting_channels:
									flash(f"Channel {channel_name_to_delete} successfully deleted for all samples","success")
								else:
									flash("Otherwise channel was deleted OK","warning")
								return redirect(url_for('imaging.imaging_batch_entry',
									username=username,request_name=request_name,
									imaging_batch_number=imaging_batch_number))
							if add_flipped_channel_button_pressed:
								""" ################################### """
								""" BATCH ADD FLIPPED CHANNEL BUTTON PRESSED """
								""" ################################### """
								logger.debug("add flipped channel button pressed!")
								channel_name_to_flip = channel_form_dict['channel_name']
								this_image_resolution = channel_form_dict['image_resolution']
								logger.debug("Flipping channel:")
								logger.debug(channel_name_to_flip)
								""" Validation """
								image_orientation = channel_form_dict['image_orientation'] 
								if image_orientation != 'horizontal':
									flash_str = (f"Can only add flipped imaging channel if "
													 "image orientation is horizontal in batch section for: "
													 f"image resolution: {this_image_resolution}, "
													 f"channel: {channel_name_to_flip}")
									flash(flash_str,"danger")
								else:
									""" Create a new ImagingChannel() entry for this channel,
									which is a duplicate of the existing channel entry with
									ventral_up=1 """

									""" Grab all matching channel entries for all samples """
									restrict_channel_dict = {}
									restrict_channel_dict['username'] = username
									restrict_channel_dict['request_name'] = request_name
									restrict_channel_dict['imaging_request_number'] = imaging_request_number
									restrict_channel_dict['image_resolution'] = this_image_resolution
									restrict_channel_dict['channel_name'] = channel_name_to_flip
									restrict_channel_dict['ventral_up'] = False
									existing_channel_contents = db_lightsheet.Request.ImagingChannel() & \
										restrict_channel_dict
									issues_adding_channels = False
									""" Now go through all of the samples in this batch 
									and make an insert in the db for a new channel """
									for sample_dict in sample_dict_list:
										this_sample_name = sample_dict['sample_name']
										existing_channel_content = existing_channel_contents & \
											{'sample_name':this_sample_name}

										imaging_channel_entry_dict = existing_channel_content.fetch1()
										imaging_channel_entry_dict['ventral_up'] = True
										logger.debug("Attempting to insert:")
										logger.debug(imaging_channel_entry_dict)
										try:					
											db_lightsheet.Request.ImagingChannel().insert1(imaging_channel_entry_dict)
										except:
											issues_adding_channels = True
											logger.debug(f"Issue adding channel entry to sample: {this_sample_name}")
											flash_str = (f"Issue adding channel to "
														 f"image resolution: {this_image_resolution}, "
														 f"channel: {channel_name_to_flip} "
														 f"for sample_name: {this_sample_name}")
											flash(flash_str,"warning")
										""" Also create a new ProcessingResolutionRequest() 
										for this image resolution/ventral_up combo if one
										does not already exist """
										restrict_processing_resolution_dict = {}
										restrict_processing_resolution_dict['username'] = username
										restrict_processing_resolution_dict['request_name'] = request_name
										restrict_processing_resolution_dict['sample_name'] = this_sample_name
										restrict_processing_resolution_dict['imaging_request_number'] = imaging_request_number
										restrict_processing_resolution_dict['processing_request_number'] = 1
										restrict_processing_resolution_dict['image_resolution'] = this_image_resolution
										restrict_processing_resolution_dict['ventral_up'] = 1
										processing_resolution_request_contents = \
											db_lightsheet.Request.ProcessingResolutionRequest & \
												restrict_processing_resolution_dict
										if len(processing_resolution_request_contents) == 0:
											restrict_processing_resolution_insert_dict = restrict_processing_resolution_dict.copy()
											restrict_processing_resolution_insert_dict['atlas_name'] = 'allen_2017' # default
											restrict_processing_resolution_insert_dict['final_orientation'] = 'sagittal' # default
											logger.debug("Creating ProcessingResolutionRequest() insert:")
											logger.debug(restrict_processing_resolution_insert_dict)
											db_lightsheet.Request.ProcessingResolutionRequest.insert1(
												restrict_processing_resolution_insert_dict)
												
									if not issues_adding_channels:
										flash(f"Channel {channel_name_to_flip} successfully added to all samples","success")
									else:
										flash("Otherwise channel was added OK","warning")
								return redirect(url_for('imaging.imaging_batch_entry',
									username=username,request_name=request_name,
									imaging_batch_number=imaging_batch_number))
								""" Create a new ImagingChannel() entry for this channel """

				""" Figure out if button press came from sample subforms """
				for sample_form in form.sample_forms:
					this_sample_name = sample_form.sample_name.data
					logger.debug("checking sample forms for sample:")
					logger.debug(this_sample_name)
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
								logger.debug("validating channel:")
								logger.debug(channel_name)
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
								else:
									try:
										n_rows = int(tiling_scheme.lower().split('x')[0])
										n_columns = int(tiling_scheme.lower().split('x')[1])
										if image_resolution in ['1.1x','1.3x'] and (n_rows > 2 or n_columns > 2):
											flash_str = flash_str_prefix + ("Tiling scheme must not exceed 2x2 for this resolution")
											channel_form.tiling_scheme.errors = ['Tiling scheme must not exceed 2x2 for this resolution']
											flash(flash_str,"danger")
											validated=False
											
										elif image_resolution in ['2x','4x'] and (n_rows > 4 or n_columns > 4):
											flash_str = flash_str_prefix + ("Tiling scheme must not exceed 4x4 for this resolution")
											channel_form.tiling_scheme.errors = ['Tiling scheme must not exceed 4x4 for this resolution']
											flash(flash_str,"danger")
											validated=False
										elif image_resolution == '3.6x' and (n_rows > 10 or n_columns > 10):
											flash_str = flash_str_prefix + ("Tiling scheme must not exceed 10x10 for this resolution")
											channel_form.tiling_scheme.errors = ['Tiling scheme must not exceed 10x10 for this resolution']
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
								ventral_up = channel_form.ventral_up.data
								if ventral_up:
									rawdata_fullpath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
										username,request_name,this_sample_name,'imaging_request_1',
										'rawdata',f'resolution_{image_resolution}_ventral_up',rawdata_subfolder)
								else:
									rawdata_fullpath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
										username,request_name,this_sample_name,'imaging_request_1',
										'rawdata',f'resolution_{image_resolution}',rawdata_subfolder)
								if rawdata_subfolder in subfolder_dict.keys():
									subfolder_dict[rawdata_subfolder].append(channel_dict)
								else:
									subfolder_dict[rawdata_subfolder] = [channel_dict]
								
								channel_index = len(subfolder_dict[rawdata_subfolder]) - 1
								""" Check that number of files is correct """
								if validated:
									logger.debug("Checking validation on rawdata subfolder")
									logger.debug(rawdata_fullpath)
									""" Count the number of files we actually find. """
									number_of_rawfiles_found = 0
									if image_resolution in ['3.6x','15x']:
										number_of_rawfiles_expected = number_of_z_planes*n_rows*n_columns

										""" For SmartSPIM
										Add up all the files in the deepest directories """
										walker = os.walk(rawdata_fullpath,followlinks=True)
										try:
											channel_dir, subdirs, files = next(walker)
											regex = re.compile(r'\d{6}')
											good_subdirs = [x for x in subdirs if regex.match(x)] # don't want to search through corrected/ or stitched/ dirs for example
											for subdir in good_subdirs:
												sub_subdirs = glob.glob(os.path.join(channel_dir,subdir,'*/'))
												for sub_subdir in sub_subdirs:
													filenames = glob.glob(sub_subdir + '/*tiff')
													number_of_rawfiles_found += len(filenames)
												
										except:	
											logger.debug("Problem checking raw data directory. Most likely directory doesn't exist")
										
									else:
										""" For LaVision
										We have to be careful here
										because the raw data filenames will include C00 if there
										is only one light sheet used, regardless of whether it is
										left or right. If both are used,
										then the left lightsheet files always have C00 in filenames
										and right lightsheet files always have C01 in filenames.
										"""
										number_of_rawfiles_expected = number_of_z_planes*(left_lightsheet_used+right_lightsheet_used)*n_rows*n_columns

										if left_lightsheet_used and right_lightsheet_used:
											number_of_rawfiles_found_left_lightsheet = \
												len(glob.glob(rawdata_fullpath + f'/*RawDataStack*_C00_*Filter000{channel_index}*'))	
											number_of_rawfiles_found += number_of_rawfiles_found_left_lightsheet
											number_of_rawfiles_found_right_lightsheet = \
												len(glob.glob(rawdata_fullpath + f'/*RawDataStack*_C01_*Filter000{channel_index}*'))	
											number_of_rawfiles_found += number_of_rawfiles_found_right_lightsheet
										else:
											# doesn't matter if its left or right lightsheet. Since there is only one, their glob patterns will be identical
											logger.debug("channel index:")
											logger.debug(channel_index)
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
							notes_from_imaging = sample_form.notes_from_imaging.data

							connection =  db_lightsheet.Request.ImagingResolutionRequest.connection 
							with connection.transaction:
								for form_resolution_dict in sample_form.image_resolution_forms.data:
									image_resolution = form_resolution_dict['image_resolution']
									imaging_request_restrict_dict = {'username':username,
										'request_name':request_name,
										'sample_name':this_sample_name,
										'imaging_request_number':imaging_request_number,
										'image_resolution':image_resolution}
									imaging_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest & \
										imaging_request_restrict_dict
									""" Update notes_from_imaging field """ 
									
									dj.Table._update(imaging_resolution_request_contents,
										'notes_from_imaging',notes_from_imaging)
									subfolder_dict = sample_subfolder_dicts[image_resolution]
									""" Make rawdata/ subdirectories for this resolution """
									imaging_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
													 request_name,this_sample_name,f"imaging_request_1",
													 "rawdata",f"resolution_{image_resolution}")
									mymkdir(imaging_dir)
									for form_channel_dict in form_resolution_dict['channel_forms']:
										channel_name = form_channel_dict['channel_name']
										ventral_up = form_channel_dict['ventral_up']
										channel_content = channel_contents_all_samples & \
											f'sample_name="{this_sample_name}"' & \
											f'image_resolution="{image_resolution}"' & \
											f'imaging_request_number={imaging_request_number}' & \
											f'channel_name="{channel_name}"' & \
											f'ventral_up="{ventral_up}"' 
										channel_content_dict = channel_content.fetch1()
										rawdata_subfolder = form_channel_dict['rawdata_subfolder']
										number_of_z_planes = form_channel_dict['number_of_z_planes']
										tiling_scheme = form_channel_dict['tiling_scheme']
										z_step = form_channel_dict['z_step']
										left_lightsheet_used = form_channel_dict['left_lightsheet_used']
										right_lightsheet_used = form_channel_dict['right_lightsheet_used']
										channel_names_this_subfolder = [x['channel_name'] for x in subfolder_dict[rawdata_subfolder]]

										channel_index = channel_names_this_subfolder.index(channel_name)
										logger.info(f" channel {channel_name} with image_resolution \
											 {image_resolution} has channel_index = {channel_index}")
										
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
										today = datetime.now()
										today_proper_format = today.date().strftime('%Y-%m-%d')
										dj.Table._update(imaging_request_contents_this_sample,'imaging_performed_date',
											today_proper_format)
										
										samples_imaging_progress_dict[this_sample_name] = 'complete'
										""" Kick off celery task for creating precomputed data from this
										raw data image dataset if there is more than one tile.
										"""
								flash(f"Imaging entry for sample {this_sample_name} was successful","success")
						else:
							logger.debug("Sample form not validated")
						return redirect(url_for('imaging.imaging_batch_entry',
									username=username,request_name=request_name,
									imaging_batch_number=imaging_batch_number))
					else:
						""" Either a sample update resolution or 
						add/delete image channel button was pressed.
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
								logger.debug("Adding new channel:")
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
								logger.debug(channel_entry_dict)
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
							else:
								""" Search the channel forms of this image resolution form to see
								if a channel delete button or add flipped channel button
								was pressed """
								for ii,channel_form in enumerate(image_resolution_form.channel_forms):
									channel_form_dict = channel_form.data
									channel_name = channel_form_dict['channel_name']
									delete_channel_button_pressed = channel_form_dict['delete_channel_button']
									add_flipped_channel_button_pressed = channel_form_dict[
										'add_flipped_channel_button']
									if delete_channel_button_pressed:
										""" #################################### """
										""" SAMPLE DELETE CHANNEL BUTTON PRESSED """
										""" #################################### """
										logger.debug("sample delete channel button pressed!")
										channel_name_to_delete = channel_form_dict['channel_name']
										ventral_up = channel_form_dict['ventral_up']
										logger.debug(channel_form_dict)
										logger.debug("Deleting channel:")
										logger.debug(channel_name_to_delete)

										dj.config['safemode'] = False # disables integrity checks so delete can take place
										issues_deleting_channels = False
										
										restrict_dict = {'sample_name':this_sample_name,
											'image_resolution':this_image_resolution,
											'channel_name':channel_name_to_delete,
											'ventral_up':ventral_up}
										imaging_channel_contents_to_delete = channel_contents_all_samples & restrict_dict
										if len(imaging_channel_contents_to_delete) > 0:
											try:
												imaging_channel_contents_to_delete.delete(force=True)
											except:
												issues_deleting_channels=True
												logger.debug("Issue deleting channel entry")
												flash_str = (f"Issue deleting channel from "
															 f"image resolution: {this_image_resolution}, "
															 f"channel: {channel_name_to_delete} "
															 f"for sample_name: {this_sample_name}")
												flash(flash_str,"warning")
											
										""" restore safemode to whatever it was before we did the deletes """
										dj.config['safemode'] = current_app.config['DJ_SAFEMODE']
										if not issues_deleting_channels:
											flash(f"Channel {channel_name_to_delete} successfully deleted for sample: {this_sample_name}","success")
										else:
											flash("Otherwise channel was deleted OK","warning")
										return redirect(url_for('imaging.imaging_batch_entry',
											username=username,request_name=request_name,
											imaging_batch_number=imaging_batch_number))
									elif add_flipped_channel_button_pressed:
										""" ######################################### """
										""" SAMPLE ADD FLIPPED CHANNEL BUTTON PRESSED """
										""" ######################################### """
										logger.debug("add flipped channel button pressed!")
										channel_name_to_flip = channel_form_dict['channel_name']
										logger.debug("Addding flipped copy of channel:")
										logger.debug(channel_name_to_flip)
										""" Validation """
										logger.debug(channel_form_dict)
										image_orientation = channel_form_dict['image_orientation'] 
										if image_orientation != 'horizontal':
											flash_str = (f"Can only add flipped imaging channel if "
															 "image orientation is horizontal for: "
															 f"sample_name: {this_sample_name}, "
															 f"image resolution: {this_image_resolution}, "
															 f"channel: {channel_name_to_flip}")
											flash(flash_str,"danger")
										else:

											""" Create a new ImagingChannel() entry for this channel,
											which is just a duplicate of the current db entry """

											restrict_channel_dict = {}
											restrict_channel_dict['username'] = username
											restrict_channel_dict['request_name'] = request_name
											restrict_channel_dict['sample_name'] = this_sample_name
											restrict_channel_dict['imaging_request_number'] = imaging_request_number
											restrict_channel_dict['image_resolution'] = this_image_resolution
											restrict_channel_dict['channel_name'] = channel_name_to_flip
											restrict_channel_dict['ventral_up'] = False
											existing_channel_dict = (db_lightsheet.Request.ImagingChannel() & \
												restrict_channel_dict).fetch1()
											flipped_channel_dict = existing_channel_dict.copy()
											flipped_channel_dict['ventral_up'] = 1
											logger.debug("inserting: ")
											logger.debug(flipped_channel_dict)
											db_lightsheet.Request.ImagingChannel().insert1(
												flipped_channel_dict)
											""" Also create a new ProcessingResolutionRequest() 
											for this image resolution/ventral_up combo if one
											does not already exist """
											restrict_processing_resolution_dict = {}
											restrict_processing_resolution_dict['username'] = username
											restrict_processing_resolution_dict['request_name'] = request_name
											restrict_processing_resolution_dict['sample_name'] = this_sample_name
											restrict_processing_resolution_dict['imaging_request_number'] = imaging_request_number
											restrict_processing_resolution_dict['processing_request_number'] = 1
											restrict_processing_resolution_dict['image_resolution'] = this_image_resolution
											restrict_processing_resolution_dict['ventral_up'] = 1
											processing_resolution_request_contents = \
												db_lightsheet.Request.ProcessingResolutionRequest & \
													restrict_processing_resolution_dict
											if len(processing_resolution_request_contents) == 0:
												restrict_processing_resolution_insert_dict = restrict_processing_resolution_dict.copy()
												restrict_processing_resolution_insert_dict['atlas_name'] = 'allen_2017' # default
												restrict_processing_resolution_insert_dict['final_orientation'] = 'sagittal' # default
												logger.debug("Creating ProcessingResolutionRequest() insert:")
												logger.debug(restrict_processing_resolution_insert_dict)
												db_lightsheet.Request.ProcessingResolutionRequest.insert1(
													restrict_processing_resolution_insert_dict)

											flash_str = (f"Successfully created flipped channel for: "
															 f"sample_name: {this_sample_name}, "
															 f"image resolution: {this_image_resolution}, "
															 f"channel: {channel_name_to_flip}")
											flash(flash_str,"success")
										return redirect(url_for('imaging.imaging_batch_entry',
											username=username,request_name=request_name,
											imaging_batch_number=imaging_batch_number))
		else: # final submit button pressed. No validation necessary since all done in each sample form
			
			logger.info("Final submit button pressed")
			imaging_progress = imaging_batch_contents.fetch1('imaging_progress')
			
			if imaging_progress == 'complete':
				logger.info("Imaging is already complete so hitting the submit button again did nothing")
				return redirect(url_for('imaging.imaging_batch_entry',username=username,
					request_name=request_name,sample_name=sample_name,
					imaging_batch_number=imaging_batch_number))
			""" For each sample, start the raw data precomputed pipeline 
			if no stitching necessary """
			for sample_dict in sample_dict_list:
				this_sample_name = sample_dict['sample_name']
				logger.debug("Sample name:")
				logger.debug(this_sample_name)
				restrict_dict = {'username':username,'request_name':request_name,
					'sample_name':this_sample_name,'imaging_request_number':imaging_request_number}
				imaging_channel_contents_this_sample = db_lightsheet.Request.ImagingChannel() & restrict_dict
				for imaging_channel_dict in imaging_channel_contents_this_sample:

					tiling_scheme = imaging_channel_dict['tiling_scheme']
					if tiling_scheme == '1x1':
						logger.info("Only one tile. Creating precomputed data for neuroglancer visualization. ")
						logger.debug(imaging_channel_dict)
						image_resolution = imaging_channel_dict['image_resolution']
						channel_name = imaging_channel_dict['channel_name']
						ventral_up = imaging_channel_dict['ventral_up']
						channel_index = imaging_channel_dict['imspector_channel_index']
						number_of_z_planes = imaging_channel_dict['number_of_z_planes']
						left_lightsheet_used = imaging_channel_dict['left_lightsheet_used']
						right_lightsheet_used = imaging_channel_dict['right_lightsheet_used']
						z_step = imaging_channel_dict['z_step']
						rawdata_subfolder = imaging_channel_dict['rawdata_subfolder']
						precomputed_kwargs = dict(username=username,request_name=request_name,
												sample_name=this_sample_name,imaging_request_number=imaging_request_number,
												image_resolution=image_resolution,channel_name=channel_name,
												channel_index=channel_index,number_of_z_planes=number_of_z_planes,
												left_lightsheet_used=left_lightsheet_used,
												right_lightsheet_used=right_lightsheet_used,
												ventral_up=ventral_up,
												z_step=z_step,rawdata_subfolder=rawdata_subfolder)

						
						raw_viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
								 f"{request_name}/{this_sample_name}/"
								 f"imaging_request_{imaging_request_number}/viz/raw")

						mymkdir(raw_viz_dir)
						if ventral_up:
							imaging_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
										 request_name,this_sample_name,f"imaging_request_1",
										 "rawdata",f"resolution_{image_resolution}_ventral_up")
							channel_viz_dir = os.path.join(raw_viz_dir,f'channel_{channel_name}_ventral_up')
						else:
							imaging_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
										 request_name,this_sample_name,f"imaging_request_1",
										 "rawdata",f"resolution_{image_resolution}")
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
			path_to_data = os.path.join(data_rootpath,username,request_name,
							 '{sample_name}',f'imaging_request_number_{imaging_request_number}', # sample_name is intentionally left in brackets 
							 'rawdata')
			""" Send email """
			subject = 'Lightserv automated email: Imaging complete'
			hosturl = os.environ['HOSTURL']

			processing_manager_url = f'https://{hosturl}' + url_for('processing.processing_manager')
			samples_str = ', '.join(x for x in sorted(list(samples_imaging_progress_dict.keys())))
			message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
						'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
						'The raw data your request:\n'
						f'request_name: "{request_name}"\n'
						f'sample names: "{samples_str}"\n'
						f'are now available on bucket here: {path_to_data}\n\n'
						 'To start processing your data, '
						f'go to the processing management GUI: {processing_manager_url} '
						'and find your sample to process.\n\n'
						 'Thanks,\n\nThe Core Facility')
			
			recipients = [correspondence_email]
			if not os.environ['FLASK_MODE'] == 'TEST':
				send_email.delay(subject=subject,body=message_body,recipients=recipients) # pragma: no cover - used to exclude this line from calculating test coverage
			flash(f"""Imaging for this batch is complete. An email has been sent to {correspondence_email} 
				informing them that their raw data is now available on bucket.
				The processing pipeline is now ready to run. ""","success")
			dj.Table._update(imaging_batch_contents,'imaging_progress','complete')
			now = datetime.now()
			date = now.strftime('%Y-%m-%d')
			dj.Table._update(imaging_batch_contents,'imaging_performed_date',date)
			
			""" Finally, set up the 4-day reminder email that will be sent if 
			user still has not submitted processing request (provided that there exists a processing 
			request for this imaging request) """

			# """ First check if there is a processing request for this imaging request.
			# This will be processing_request_number=1 because we are in the imaging entry
			# form here. """
			# restrict_dict = dict(username=username,request_name=request_name,
			# 	sample_name=sample_name,imaging_request_number=imaging_request_number,
			# 	processing_request_number=1)
			# processing_request_contents = db_lightsheet.Request.ProcessingRequest() & restrict_dict
			# if len(processing_request_contents) > 0:
			# 	subject = 'Lightserv automated email. Reminder to start processing.'
			# 	body = ('Hello, this is a reminder that you still have not started '
			# 			'the data processing pipeline for your sample:.\n\n'
			# 			f'request_name: {request_name}\n'
			# 			f'sample_name: {sample_name}\n\n'
			# 			'To start processing your data, '
			# 			f'go to the processing management GUI: {processing_manager_url} '
			# 			'and find your sample to process.\n\n'
			# 			'Thanks,\nThe Brain Registration and Histology Core Facility')    
			# 	logger.debug("Sending reminder email 4 days in the future")
			# 	request_contents = db_lightsheet.Request() & \
			# 					{'username':username,'request_name':request_name}
			# 	correspondence_email = request_contents.fetch1('correspondence_email')
			# 	recipients = [correspondence_email]
			# 	future_time = datetime.utcnow() + timedelta(days=4)
			# 	reminder_email_kwargs = restrict_dict.copy()
			# 	reminder_email_kwargs['subject'] = subject
			# 	reminder_email_kwargs['body'] = body
			# 	reminder_email_kwargs['recipients'] = recipients
			# 	if not os.environ['FLASK_MODE'] == 'TEST': # pragma: no cover - used to exclude this line from calculating test coverage
			# 		# tasks.send_processing_reminder_email.apply_async(
			# 		# 	kwargs=reminder_email_kwargs,eta=future_time) 
			# 		logger.debug("Not running celery task for reminder email while debugging.")
			return redirect(url_for('imaging.imaging_manager'))

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

			channel_contents_list_this_resolution = (
				batch_channel_contents & f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
			
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
				this_channel_form.ventral_up.data = channel_content['ventral_up']
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
			logger.debug("Initializing sample form:")
			logger.debug(this_sample_name)
			channel_contents_this_sample = channel_contents_all_samples & \
				f'sample_name="{this_sample_name}"'
			""" Figure out clearing batch and if there were notes_for_clearer """
			this_sample_contents = sample_contents & {'sample_name':this_sample_name}
			clearing_batch_number = this_sample_contents.fetch1('clearing_batch_number')
			clearing_batch_restrict_dict = dict(username=username,request_name=request_name,
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
				logger.debug("initializing image resolution form:")
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
					logger.debug("initializing channel form:")
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
					this_channel_form.ventral_up.data = channel_content['ventral_up']
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
