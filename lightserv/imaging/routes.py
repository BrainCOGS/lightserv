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
	SampleTable, ExistingImagingTable, ImagingChannelTable,ImagingBatchTable,
	RequestSummaryTable)
from .forms import (NewImagingRequestForm, ImagingBatchForm)
from . import tasks
from . import utils
from lightserv.main.tasks import send_email
from lightserv.processing.tasks import smartspim_stitch
import numpy as np
import datajoint as dj
import os,re
from datetime import datetime, timedelta
import logging
import glob
import copy
from PIL import Image
import concurrent.futures

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
	imaging_resolution_contents = db_lightsheet.Request.ImagingResolutionRequest()

	sample_joined_contents = clearing_batch_contents * sample_contents * \
    request_contents
	clearing_aggr_contents = dj.U('username','request_name',
	    'clearing_batch_number').aggr(
	    sample_joined_contents,
	    clearing_progress='MAX(clearing_progress)',
	    clearer='MIN(clearer)',
	    species='MIN(species)',
	    all_samples_cleared='SUM(IF(clearing_progress="complete",1,0))=count(*)',
	    )

	imaging_aggr_contents = dj.U('username','request_name',
	                             'imaging_request_number','imaging_batch_number').aggr(
	    imaging_batch_contents * imaging_resolution_contents,
	    imaging_request_date_submitted='MIN(imaging_request_date_submitted)',
	    imaging_request_time_submitted='MIN(imaging_request_time_submitted)',
	    all_samples_lavision='SUM(IF(microscope="lavision",1,0))=count(*)',
	    all_samples_smartspim='SUM(IF(microscope="smartspim",1,0))=count(*)').proj(
	    datetime_submitted='TIMESTAMP(imaging_request_date_submitted,imaging_request_time_submitted)',
	    all_samples_lavision='all_samples_lavision',
	    all_samples_smartspim='all_samples_smartspim'
	)
	imaging_joined_contents = (imaging_batch_contents * imaging_aggr_contents)
	all_joined_contents = clearing_aggr_contents * imaging_joined_contents

	if current_user not in imaging_admins:
		logger.info(f"{current_user} is not an imaging admin."
					 " They can see only entries where they designated themselves as the imager")
		all_joined_contents = all_joined_contents & f'imager="{current_user}"'
	
	
	contents_being_imaged = all_joined_contents & 'all_samples_cleared=1' & \
		'imaging_progress="in progress"'
	being_imaged_table_id = 'horizontal_being_imaged_table'
	
	table_being_imaged = dynamic_imaging_management_table(contents_being_imaged,
		table_id=being_imaged_table_id,
		sort_by=sort,sort_reverse=reverse)

	''' Next get all entities that are ready to be imaged '''
	contents_ready_to_image = all_joined_contents & 'all_samples_cleared=1' & \
	 'imaging_progress="incomplete"'
	ready_to_image_table_id = 'horizontal_ready_to_image_table'
	table_ready_to_image = dynamic_imaging_management_table(contents_ready_to_image,
		table_id=ready_to_image_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Now get all entities on deck (currently being cleared) '''
	contents_on_deck = all_joined_contents & 'clearing_progress!="complete"' & 'imaging_progress!="complete"'
	on_deck_table_id = 'horizontal_on_deck_table'
	table_on_deck = dynamic_imaging_management_table(contents_on_deck,table_id=on_deck_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Finally get all entities that have already been imaged '''
	contents_already_imaged = (all_joined_contents & 'imaging_progress="complete"').fetch(
		as_dict=True,order_by='datetime_submitted DESC',limit=10,)
	already_imaged_table_id = 'horizontal_already_imaged_table'
	table_already_imaged = dynamic_imaging_management_table(contents_already_imaged,
		table_id=already_imaged_table_id,
		sort_by=sort,sort_reverse=reverse)
	
	return render_template('imaging/image_management.html',
		table_being_imaged=table_being_imaged,
		table_ready_to_image=table_ready_to_image,table_on_deck=table_on_deck,
		table_already_imaged=table_already_imaged)

@imaging.route(("/imaging/imaging_batch_entry/<username>/<request_name>/"
			   "<clearing_batch_number>/<imaging_request_number>/<imaging_batch_number>"),
	methods=['GET','POST'])
@logged_in
@logged_in_as_imager
@log_http_requests
def imaging_batch_entry(username,request_name,clearing_batch_number,
	imaging_request_number,imaging_batch_number): 
	""" Route for handling form data entered for imaging 
	samples in batch entry form
	"""
	current_user = session['user']
	logger.info(f"{current_user} accessed imaging_batch_entry")

	form = ImagingBatchForm(request.form)
	rawdata_rootpath = os.path.join(
		current_app.config['DATA_BUCKET_ROOTPATH'],
		username,request_name)
	imaging_batch_restrict_dict = dict(
		username=username,request_name=request_name,
		clearing_batch_number=clearing_batch_number,
		imaging_batch_number=imaging_batch_number,
		imaging_request_number=imaging_request_number)

	sample_contents = db_lightsheet.Request.ImagingBatchSample() & imaging_batch_restrict_dict 
	sample_dict_list = sample_contents.fetch(as_dict=True)

	""" Figure out how many samples in this imaging batch """
	imaging_batch_contents = db_lightsheet.Request.ImagingBatch() & imaging_batch_restrict_dict
	number_in_batch = imaging_batch_contents.fetch1('number_in_imaging_batch')
	imaging_progress = imaging_batch_contents.fetch1('imaging_progress')

	""" Figure out which samples are already imaged """
	imaging_request_contents = (db_lightsheet.Request.ImagingRequest() * sample_contents)
	samples_imaging_progress_dict = {x['sample_name']:x['imaging_progress'] for x in imaging_request_contents.fetch(
		as_dict=True)}
	n_active_samples = len([x for x in samples_imaging_progress_dict if samples_imaging_progress_dict[x] != 'complete'])

	""" Assemble the list of resolution/channel dicts for filling out the 
	batch forms """
	first_sample_dict = sample_contents.fetch(as_dict=True,limit=1)[0]
	first_sample_name = first_sample_dict['sample_name']	
	channel_restrict_dict = {'username':username,'request_name':request_name,
		'imaging_request_number':imaging_request_number}
	channel_contents_all_samples = db_lightsheet.Request.ImagingChannel() & channel_restrict_dict

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
					
					for jj in range(len(batch_channel_forms)):
						batch_channel_form = batch_channel_forms[jj]
						batch_channel_name = batch_channel_form.channel_name.data
						logger.debug("Batch channel name:")
						logger.debug(batch_channel_name)
						if batch_channel_form.validate_on_submit():
							logger.debug("Batch channel form validated")
						else:
							logger.debug("Batch channel form NOT validated")
							logger.debug(batch_channel_form.errors)
							column_name = f"batch_resolution_{batch_image_resolution}_channel_{batch_channel_name}_row"

							return render_template('imaging/imaging_batch_entry.html',form=form,
								rawdata_rootpath=rawdata_rootpath,imaging_table=imaging_table,
								sample_dict_list=sample_dict_list,
								samples_imaging_progress_dict=samples_imaging_progress_dict,
								n_active_samples=n_active_samples,
								imaging_request_number=imaging_request_number,
								column_name=column_name)

				""" If validation of all batch channels in all 
				resolution forms passed then loop through 
				all samples in the form and try to make db inserts.
				It is possible that 
				sample forms are not homogenous anymore (due to user
				changing the individual imaging resolution of a single
				sample). In this case, the transaction might fail 
				and the application of batch parameters 
				will not be applied and the user will be notififed. 
				"""
			
				logger.debug("All batch channels validated")
				connection = db_lightsheet.Request.ImagingChannel.connection
				issues_applying_batch_parameters=False
				try: 
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
									
									db_lightsheet.Request.ImagingChannel().insert1(channel_insert_dict,replace=True)
					logger.info("Batch parameters successfully applied to samples")
					flash("Batch parameters successfully applied to samples","success")					
				except:
					logger.debug("Issues applying batch parameters to all samples")
					flash_str = (f"Issue applying batch parameters to all samples. "
								 "This is most likely because you modified "
								 "the individual sample forms before applying batch parameters. "
								 "Apply batch parameters BEFORE modifying sample forms.")
					flash(flash_str,"danger")

				return redirect(url_for('imaging.imaging_batch_entry',
							username=username,request_name=request_name,
							clearing_batch_number=clearing_batch_number,
							imaging_request_number=imaging_request_number,
							imaging_batch_number=imaging_batch_number))
			else:
				""" A few possibilites: 
				1) A sample submit button was pressed
				2) A skip_sample_imaging button was pressed
				2) A batch update resolution or add/delete image channel button was pressed
				3) A sample update resolution or add/delete image channel button was pressed
				"""

				""" First check if BATCH add/delete channel button pressed or 
				BATCH update resolution was pressed
				in any of the resolution subforms """
				for image_resolution_form in form.image_resolution_batch_forms:
					form_resolution_dict = image_resolution_form.data
					# logger.debug(form_resolution_dict)
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
							imaging_channel_entry_dict = copy.deepcopy(batch_channel_entry_dict)
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
							clearing_batch_number=clearing_batch_number,
							imaging_request_number=imaging_request_number,
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
						lavision_resolutions = current_app.config['LAVISION_RESOLUTIONS']
						smartspim_resolutions = current_app.config['SMARTSPIM_RESOLUTIONS']
						if this_image_resolution in lavision_resolutions:
							this_microscope = 'lavision'
						else:
							this_microscope = 'smartspim'
						if new_image_resolution in lavision_resolutions:
							new_microscope = 'lavision'
						else:
							new_microscope = 'smartspim'

						if new_microscope == this_microscope:
							same_microscope = True
						else:
							same_microscope = False
						logger.debug("New image resolution is:")
						logger.debug(new_image_resolution)
						logger.debug("Using same microscope as before?")
						logger.debug(same_microscope)
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
									processing_resolution_request_insert_dict['sample_name'] = this_sample_name
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
								if not same_microscope:
									if new_microscope == 'smartspim':
										for d in imaging_channel_insert_dict_list:
											channel_name = d['channel_name']
											new_channel_name = utils.translate_lavision_to_smartspim_channel(channel_name)
											d.update({'channel_name':new_channel_name})
									elif new_microscope == 'lavision':
										for d in imaging_channel_insert_dict_list:
											channel_name = d['channel_name']
											new_channel_name = utils.translate_smartspim_to_lavision_channel(channel_name)
											d.update({'channel_name':new_channel_name})
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
										if not same_microscope:
											if new_microscope == 'smartspim':
												for d in processing_channel_dicts_to_insert:
													channel_name = d['channel_name']
													new_channel_name = utils.translate_lavision_to_smartspim_channel(channel_name)
													d.update({'channel_name':new_channel_name})
											elif new_microscope == 'lavision':
												for d in processing_channel_dicts_to_insert:
													channel_name = d['channel_name']
													new_channel_name = utils.translate_smartspim_to_lavision_channel(channel_name)
													d.update({'channel_name':new_channel_name})
										logger.debug("Inserting ProcessingChannel() contents:")
										logger.debug(processing_channel_dicts_to_insert)
										db_lightsheet.Request.ProcessingChannel().insert(processing_channel_dicts_to_insert)
						
						return redirect(url_for('imaging.imaging_batch_entry',
							username=username,request_name=request_name,
							clearing_batch_number=clearing_batch_number,
							imaging_request_number=imaging_request_number,
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
									clearing_batch_number=clearing_batch_number,
									imaging_request_number=imaging_request_number,
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
											# restrict_processing_resolution_insert_dict = restrict_processing_resolution_dict.deepcopy()
											restrict_processing_resolution_insert_dict = copy.deepcopy(
												restrict_processing_resolution_dict)
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
									clearing_batch_number=clearing_batch_number,
									imaging_request_number=imaging_request_number,
									imaging_batch_number=imaging_batch_number))
								""" Create a new ImagingChannel() entry for this channel """

				""" Figure out if button press came from sample subforms """
				for sample_ii,sample_form in enumerate(form.sample_forms):
					this_sample_name = sample_form.sample_name.data
					logger.debug("checking sample forms for sample:")
					logger.debug(this_sample_name)
					""" Check if sample submit button pressed """
					if sample_form.submit.data:
						""" ############################ """
						""" SAMPLE SUBMIT BUTTON PRESSED """
						""" ############################ """

						logger.debug("Sample form submit button pressed:")
						logger.debug(this_sample_name)

						# First reset the choices of the add channel button in batch forms
						batch_image_resolution_forms = form.image_resolution_batch_forms
						for batch_image_resolution_form in batch_image_resolution_forms:
							batch_image_resolution = batch_image_resolution_form.image_resolution.data
							batch_channels_this_resolution = [x.channel_name.data for x in batch_image_resolution_form.channel_forms]
							if batch_image_resolution in current_app.config['LAVISION_RESOLUTIONS']:
								all_imaging_channels = current_app.config['LAVISION_IMAGING_CHANNELS']
							else:
								all_imaging_channels = current_app.config['SMARTSPIM_IMAGING_CHANNELS']

							batch_available_channels = [x for x in all_imaging_channels \
								if x not in batch_channels_this_resolution]
							batch_image_resolution_form.new_channel_dropdown.choices = \
								[(x,x) for x in batch_available_channels]
						""" Loop over image resolution subforms 
						to find the channel subforms within -- those
						need to be validated first """

						for resolution_ii,image_resolution_form in enumerate(sample_form.image_resolution_forms):
							image_resolution = image_resolution_form.image_resolution.data
							channels_this_resolution = [x.channel_name.data for x in image_resolution_form.channel_forms]
							# But first reset the choices for the new channels
							if image_resolution in current_app.config['LAVISION_RESOLUTIONS']:
								all_imaging_channels = current_app.config['LAVISION_IMAGING_CHANNELS']
							else:
								all_imaging_channels = current_app.config['SMARTSPIM_IMAGING_CHANNELS']

							available_channels = [x for x in all_imaging_channels \
								if x not in channels_this_resolution]
							image_resolution_form.new_channel_dropdown.choices = \
								[(x,x) for x in available_channels]
							
							logger.debug(f"Image resolution: {image_resolution}")
							
							""" Loop through all channels subforms in this 
							image resolution form and validate each one """
							for channel_ii,channel_form in enumerate(image_resolution_form.channel_forms):
								# set the new channel dropdown value to 
								channel_dict = channel_form.data
								channel_name = channel_dict['channel_name']
								logger.debug(f"Channel: {channel_name}")
								logger.debug(channel_dict)

								if channel_form.validate_on_submit():
									logger.debug("Channel form validated")
								else:
									logger.debug("Channel form NOT validated")
									logger.debug(channel_form.errors)
									column_name = f"sample_{sample_ii}_resolution_{image_resolution}_channel_{channel_name}_row"

									return render_template('imaging/imaging_batch_entry.html',form=form,
										rawdata_rootpath=rawdata_rootpath,imaging_table=imaging_table,
										sample_dict_list=sample_dict_list,
										samples_imaging_progress_dict=samples_imaging_progress_dict,
										n_active_samples=n_active_samples,
										imaging_request_number=imaging_request_number,
										column_name=column_name)
							""" Now that all channel subforms are validated,
							validate the image resolution form """
							
							if image_resolution_form.validate_on_submit():
								logger.debug("Image resolution form validated")
							else:
								logger.debug("Image resolution form NOT validated!")
								logger.debug(image_resolution_form.errors)
								flash_str = (f"Issues with parameters for Sample: {this_sample_name},"
											 f" image resolution: {image_resolution}, ")
								for key in image_resolution_form.errors:
									errors = image_resolution_form.errors[key] 
									for error in errors:
										flash_str += key + ": " + error + "; "
								flash(flash_str,"danger")
								return render_template('imaging/imaging_batch_entry.html',form=form,
									rawdata_rootpath=rawdata_rootpath,imaging_table=imaging_table,
									sample_dict_list=sample_dict_list,
									samples_imaging_progress_dict=samples_imaging_progress_dict,
									n_active_samples=n_active_samples,
									imaging_request_number=imaging_request_number)

								
						""" If we have made it this far then all image resolution forms
						and their channel subforms have been validated for this sample """
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
								imaging_resolution_request_contents = \
									db_lightsheet.Request.ImagingResolutionRequest & \
									imaging_request_restrict_dict
								""" Update notes_from_imaging field """ 
								imaging_resolution_update_dict = imaging_resolution_request_contents.fetch1()
								imaging_resolution_update_dict['notes_from_imaging'] = notes_from_imaging
								db_lightsheet.Request.ImagingResolutionRequest().update1(
									imaging_resolution_update_dict)

								if image_resolution in ["3.6x","15x"] :
									
									logger.debug(f"Have SmartSPIM {image_resolution} imaging")
									
									stitching_kwargs = dict(username=username,request_name=request_name,
											sample_name=this_sample_name,imaging_request_number=imaging_request_number,
											image_resolution=image_resolution,
											n_channels=0,
											channel_dict={})

									for form_channel_dict in form_resolution_dict['channel_forms']:
										channel_name = form_channel_dict['channel_name']
										ventral_up = form_channel_dict['ventral_up']
										rawdata_subfolder = form_channel_dict['rawdata_subfolder']
										stitching_kwargs['channel_dict'][channel_name] = {
											'ventral_up':ventral_up,
											'rawdata_subfolder':rawdata_subfolder}
										stitching_kwargs['n_channels'] += 1

										# Update ImagingChannel() to capture form submitted data
										channel_dict = {
											'sample_name':this_sample_name,
											'image_resolution':image_resolution,
											'imaging_request_number':imaging_request_number,
											'channel_name':channel_name,
											'ventral_up':ventral_up
										}
										channel_content = channel_contents_all_samples & channel_dict
										logger.debug("Channel content:")
										logger.debug(channel_content)
										channel_content_dict = channel_content.fetch1()
										channel_insert_dict = copy.deepcopy(channel_content_dict)
										
										''' Now replace (some of) the values in the dict from what we 
										got from the form '''
										keys_to_ignore = ['channel_name','image_resolution','imaging_request_number']
										for key,val in form_channel_dict.items():
											if key in channel_content_dict.keys() and key not in keys_to_ignore:
												channel_insert_dict[key] = val
										
										db_lightsheet.Request.ImagingChannel().update1(channel_insert_dict)

									if not os.environ['FLASK_MODE'] == 'TEST': 
										smartspim_stitch.delay(**stitching_kwargs)
										logger.debug("Smartspim stitching task sent with these kwargs:")
										logger.debug(stitching_kwargs)
									else:
										logger.debug("Not running stitching pipeline because we are in TEST mode")
									
									

								else: # lavision imaging
									subfolder_dict = {'dorsal':{},'ventral':{}} 
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
										# Find the top level key of the subfolder dict
										if ventral_up:
											topkey = 'ventral'
										else:
											topkey = 'dorsal'
										if rawdata_subfolder in subfolder_dict[topkey].keys():
											subfolder_dict[topkey][rawdata_subfolder].append(channel_dict)
										else:
											subfolder_dict[topkey][rawdata_subfolder] = [channel_dict]
										channel_index = len(subfolder_dict[topkey][rawdata_subfolder]) - 1
										''' Make a copy of the current row in a new dictionary which we will insert '''

										channel_insert_dict = copy.deepcopy(channel_content_dict)
									
										''' Now replace (some of) the values in the dict from what we 
										got from the form '''
										keys_to_ignore = ['channel_name','image_resolution','imaging_request_number']
										for key,val in form_channel_dict.items():
											if key in channel_content_dict.keys() and key not in keys_to_ignore:
												channel_insert_dict[key] = val
										channel_insert_dict['imspector_channel_index'] = channel_index
										
										db_lightsheet.Request.ImagingChannel().update1(channel_insert_dict)
										
										""" Kick off celery task for creating precomputed data from this
										raw data image dataset if there is stitching is not necessary.

										Otherwise, initiate the stitching job
										"""

										if tiling_scheme == '1x1':
											logger.info("Only one tile. "
												"Creating precomputed data for neuroglancer visualization. ")
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
															 request_name,this_sample_name,f"imaging_request_{imaging_request_number}",
															 "rawdata",f"resolution_{image_resolution}_ventral_up")
												channel_viz_dir = os.path.join(raw_viz_dir,f'channel_{channel_name}_ventral_up')
											else:
												imaging_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
															 request_name,this_sample_name,f"imaging_request_{imaging_request_number}",
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
													f"{raw_data_dir}/*RawDataStack*{lightsheet_index_code}*Filter000{channel_index}*tif")
												first_slice = all_slices[0]
												first_im = Image.open(first_slice)
												x_dim,y_dim = first_im.size
												precomputed_kwargs['x_dim'] = x_dim
												precomputed_kwargs['y_dim'] = y_dim
												first_im.close() 
												if not os.environ['FLASK_MODE'] == 'TEST': 
													logger.debug("submitting left lightsheet raw precomputed pipeline for kwargs:")
													logger.debug(precomputed_kwargs)
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
												all_slices = glob.glob(f"{raw_data_dir}/*RawDataStack*{lightsheet_index_code}*Filter000{channel_index}*tif")
												first_slice = all_slices[0]
												first_im = Image.open(first_slice)
												x_dim,y_dim = first_im.size
												precomputed_kwargs['x_dim'] = x_dim
												precomputed_kwargs['y_dim'] = y_dim
												first_im.close()
												if not os.environ['FLASK_MODE'] == 'TEST': 
													logger.debug("submitting right lightsheet raw precomputed pipeline for kwargs:")
													logger.debug(precomputed_kwargs)
													tasks.make_precomputed_rawdata.delay(**precomputed_kwargs) # pragma: no cover - used to exclude this line from calculating test coverage 
										
						""" Set imaging progress complete for this sample and 
									update imaging performed date """
						restrict_dict_imaging_request = {
							'username':username,
							'request_name':request_name,
							'sample_name':this_sample_name,
							'imaging_request_number':imaging_request_number}
						imaging_request_contents_this_sample = db_lightsheet.Request.ImagingRequest() & \
							restrict_dict_imaging_request
						imaging_request_update_dict = imaging_request_contents_this_sample.fetch1()
						imaging_request_update_dict['imaging_progress'] = 'complete'
						today = datetime.now()
						today_proper_format = today.date().strftime('%Y-%m-%d')
						imaging_request_update_dict['imaging_performed_date'] = today_proper_format
						logger.debug("Updating ImagingRequest() table with:")
						logger.debug(imaging_request_update_dict)
						db_lightsheet.Request.ImagingRequest().update1(imaging_request_update_dict)
						logger.debug("Updated ImagingRequest()!")

						flash(f"Imaging entry for sample {this_sample_name} was successful","success")
					
						return redirect(url_for('imaging.imaging_batch_entry',
									username=username,request_name=request_name,
									clearing_batch_number=clearing_batch_number,
									imaging_request_number=imaging_request_number,
									imaging_batch_number=imaging_batch_number))
					elif sample_form.skip_sample_button.data:
						""" Set imaging progress complete for this sample and 
									update imaging performed date """
						restrict_dict_imaging_request = {
							'username':username,
							'request_name':request_name,
							'sample_name':this_sample_name,
							'imaging_request_number':imaging_request_number}
						imaging_request_contents_this_sample = db_lightsheet.Request.ImagingRequest() & \
							restrict_dict_imaging_request
						imaging_request_update_dict = imaging_request_contents_this_sample.fetch1()
						imaging_request_update_dict['imaging_progress'] = 'complete'
						imaging_request_update_dict['imaging_skipped'] = True
						# today = datetime.now()
						# today_proper_format = today.date().strftime('%Y-%m-%d')
						# imaging_request_update_dict['imaging_performed_date'] = today_proper_format
						logger.debug("Updating ImagingRequest() table with:")
						logger.debug(imaging_request_update_dict)
						db_lightsheet.Request.ImagingRequest().update1(imaging_request_update_dict)
						logger.debug("Updated ImagingRequest()!")

						flash(f"Imaging for sample {this_sample_name} was successfully skipped and marked as complete","success")
					
						return redirect(url_for('imaging.imaging_batch_entry',
									username=username,request_name=request_name,
									clearing_batch_number=clearing_batch_number,
									imaging_request_number=imaging_request_number,
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
									clearing_batch_number=clearing_batch_number,
									imaging_request_number=imaging_request_number,
									imaging_batch_number=imaging_batch_number))
							
							elif update_resolution_button_pressed:
								""" ############################################# """
								""" SAMPLE CHANGE IMAGE RESOLUTION BUTTON PRESSED """
								""" ############################################# """
								logger.debug("Update image resolution button pressed!")
								new_image_resolution = form_resolution_dict['new_image_resolution']
								""" Figure out if microscope was switched """
								lavision_resolutions = current_app.config['LAVISION_RESOLUTIONS']
								smartspim_resolutions = current_app.config['SMARTSPIM_RESOLUTIONS']
								if this_image_resolution in lavision_resolutions:
									this_microscope = 'lavision'
								else:
									this_microscope = 'smartspim'
								if new_image_resolution in lavision_resolutions:
									new_microscope = 'lavision'
								else:
									new_microscope = 'smartspim'

								if new_microscope == this_microscope:
									same_microscope = True
								else:
									same_microscope = False
								logger.debug("New image resolution is:")
								logger.debug(new_image_resolution)
								logger.debug("Using same microscope as before?")
								logger.debug(same_microscope)
								""" Update image resolution in all locations in the database.
								Cannot use update1() because image_resolution is a primary key. 
								Need to delete entries and then reinsert them. """
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
										processing_resolution_request_insert_dict_list = processing_resolution_request_contents.fetch()
										processing_resolution_request_contents.delete(force=True)
									else:
										logger.debug("Making an entirely new ProcessingResolutionRequest() entry")
										processing_resolution_request_insert_dict = {}
										processing_resolution_request_insert_dict['request_name'] = request_name
										processing_resolution_request_insert_dict['username'] = username 
										processing_resolution_request_insert_dict['sample_name'] = this_sample_name
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
									""" channel names need to be updated if microscope was switched """
									if not same_microscope:
										if new_microscope == 'smartspim':
											for d in imaging_channel_insert_dict_list:
												channel_name = d['channel_name']
												new_channel_name = utils.translate_lavision_to_smartspim_channel(channel_name)
												d.update({'channel_name':new_channel_name})
										elif new_microscope == 'lavision':
											for d in imaging_channel_insert_dict_list:
												channel_name = d['channel_name']
												new_channel_name = utils.translate_smartspim_to_lavision_channel(channel_name)
												d.update({'channel_name':new_channel_name})

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

											if len(processing_resolution_request_contents) > 0:
												for processing_resolution_request_insert_dict in processing_resolution_request_insert_dict_list: 
													processing_resolution_request_insert_dict['image_resolution'] = new_image_resolution
													logger.debug("Inserting ProcessingResolutionRequest() contents:")
													logger.debug(processing_resolution_request_insert_dict)
													db_lightsheet.Request.ProcessingResolutionRequest().insert1(
														processing_resolution_request_insert_dict)
											""" Finally ProcessingChannel() """
											[d.update({'image_resolution':new_image_resolution}) for d in processing_channel_dicts_to_insert]
											""" channel names need to be updated if microscope was switched """
											if not same_microscope:
												if new_microscope == 'smartspim':
													for d in processing_channel_dicts_to_insert:
														channel_name = d['channel_name']
														new_channel_name = utils.translate_lavision_to_smartspim_channel(channel_name)
														d.update({'channel_name':new_channel_name})
												elif new_microscope == 'lavision':
													for d in processing_channel_dicts_to_insert:
														channel_name = d['channel_name']
														new_channel_name = utils.translate_smartspim_to_lavision_channel(channel_name)
														d.update({'channel_name':new_channel_name})
											logger.debug("Inserting ProcessingChannel() contents:")
											logger.debug(processing_channel_dicts_to_insert)
											db_lightsheet.Request.ProcessingChannel().insert(processing_channel_dicts_to_insert)
								
								return redirect(url_for('imaging.imaging_batch_entry',
									username=username,request_name=request_name,
									clearing_batch_number=clearing_batch_number,
									imaging_request_number=imaging_request_number,
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
											clearing_batch_number=clearing_batch_number,
											imaging_request_number=imaging_request_number,
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
											flipped_channel_dict = copy.deepcopy(existing_channel_dict)
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
												restrict_processing_resolution_insert_dict = copy.deepcopy(
													restrict_processing_resolution_dict)
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
											clearing_batch_number=clearing_batch_number,
											imaging_request_number=imaging_request_number,
											imaging_batch_number=imaging_batch_number))
		else: # final submit button pressed. No validation necessary since all done in each sample form
			
			logger.info("Final submit button pressed")
			imaging_progress = imaging_batch_contents.fetch1('imaging_progress')
			
			if imaging_progress == 'complete':
				logger.info("Imaging is already complete so hitting the submit button again did nothing")
				flash("Imaging is already complete so hitting the submit button again did nothing",
					"warning")
				return redirect(url_for('imaging.imaging_batch_entry',username=username,
					request_name=request_name,
					clearing_batch_number=clearing_batch_number,
					imaging_request_number=imaging_request_number,
					imaging_batch_number=imaging_batch_number))
			
						
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

			""" Figure out if there is processing to do for any of your samples """
			image_resolutions_no_processing = current_app.config['RESOLUTIONS_NO_PROCESSING']

			if any([x not in image_resolutions_no_processing for x in batch_unique_image_resolutions]):
				have_processing_requests = True
			else:
				have_processing_requests = False
			
			message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
						'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
						'The raw data your request:\n'
						f'request_name: "{request_name}"\n'
						f'are now available on bucket here: \n\n')
			sample_names = set(imaging_request_contents.fetch('sample_name'))

			for sample_name in sample_names:
				imaging_request_restrict_dict = {
				'sample_name':sample_name,
				'imaging_request_number':imaging_request_number,
					}
				this_imaging_request_contents = imaging_request_contents & imaging_request_restrict_dict
				imaging_skipped = this_imaging_request_contents.fetch1('imaging_skipped')

				sample_basepath = os.path.join(data_rootpath,username,request_name,
				sample_name,f'imaging_request_number_{imaging_request_number}',  
				'rawdata')
				channel_contents_this_sample = channel_contents_all_samples & f'sample_name="{sample_name}"' 
				message_body += f'Sample name: {sample_name}:\n'
				if imaging_skipped:
					message_body += "No images taken.\n"
					continue
				for channel_dict in channel_contents_this_sample:
					logger.debug("Channel dict:")
					logger.debug(channel_dict)
					channel_name = channel_dict['channel_name']
					image_resolution = channel_dict['image_resolution']
					ventral_up = channel_dict['ventral_up']
					rawdata_subfolder = channel_dict['rawdata_subfolder']
					if ventral_up:
						rawdata_fullpath = os.path.join(
							data_rootpath,username,request_name,sample_name,
							f'imaging_request_{imaging_request_number}',
							'rawdata',f'resolution_{image_resolution}_ventral_up',
							rawdata_subfolder)
						message_body += f'\tchannel {channel_name} (ventral up): {rawdata_fullpath}\n'
					else:
						rawdata_fullpath = os.path.join(
							data_rootpath,username,request_name,sample_name,
							f'imaging_request_{imaging_request_number}',
							'rawdata',f'resolution_{image_resolution}',
							rawdata_subfolder)
						message_body += f'\tchannel {channel_name}: {rawdata_fullpath}\n'
				message_body += '\n'
				
			if have_processing_requests:
				message_body += ('To start processing your data, '
						f'go to the processing management GUI: {processing_manager_url} '
						'and find your sample to process.\n\n')
			message_body += 'Thanks,\n\nThe Core Facility'

			recipients = [correspondence_email]
			if not os.environ['FLASK_MODE'] == 'TEST':
				send_email.delay(subject=subject,body=message_body,recipients=recipients) # pragma: no cover - used to exclude this line from calculating test coverage
			flash(f"""Imaging for this batch is complete. An email has been sent to {correspondence_email} 
				informing them that their raw data is now available on bucket.
				The processing pipeline is now ready to run. ""","success")
			imaging_batch_update_dict = imaging_batch_contents.fetch1()
			imaging_batch_update_dict['imaging_progress'] = 'complete'
			now = datetime.now()
			date = now.strftime('%Y-%m-%d')
			imaging_batch_update_dict['imaging_performed_date'] = date
			db_lightsheet.Request.ImagingBatch().update1(imaging_batch_update_dict)			
			return redirect(url_for('imaging.imaging_manager'))

	elif request.method == 'GET': # get request
		logger.debug("GET request")
		if imaging_progress == 'complete':
			logger.info("Imaging already complete but accessing the imaging entry page anyway.")
			flash("Imaging is already complete for this sample. "
				"This page is read only and hitting submit will do nothing",'warning')
		else:
			imaging_batch_update_dict = imaging_batch_contents.fetch1()
			imaging_batch_update_dict['imaging_progress'] = 'in progress'
			db_lightsheet.Request.ImagingBatch().update1(imaging_batch_update_dict)			

		""" INITIALIZE BATCH FORM """
		""" Clear out any previously existing image resolution forms """
		while len(form.image_resolution_batch_forms) > 0:
			form.image_resolution_batch_forms.pop_entry() # pragma: no cover - used to exclude this line from calculating test coverage
		for ii in range(len(batch_unique_image_resolutions)):
			this_image_resolution = batch_unique_image_resolutions[ii]
			logger.debug(this_image_resolution)
			image_resolution_restrict_dict = {'username':username,
				'request_name':request_name,'sample_name':first_sample_name,
				'imaging_request_number':imaging_request_number,
				'image_resolution':this_image_resolution}
			image_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & image_resolution_restrict_dict
			notes_for_imager = image_resolution_request_contents.fetch1('notes_for_imager')

			channel_contents_list_this_resolution = (
				batch_channel_contents & f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
			
			form.image_resolution_batch_forms.append_entry()
			this_resolution_form = form.image_resolution_batch_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution
			""" Set up options for new image resolution dropdown """
			all_image_resolutions = current_app.config['LAVISION_RESOLUTIONS'] + current_app.config['SMARTSPIM_RESOLUTIONS']
			this_resolution_form.new_image_resolution.choices = [(x,x) for x in all_image_resolutions if x!=this_image_resolution]
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
				this_channel_form.imaging_request_number.data = imaging_request_number
				this_channel_form.image_resolution.data = channel_content['image_resolution']
				used_channels.append(channel_name)
				""" Autofill based on current db contents """
				this_channel_form.ventral_up.data = channel_content['ventral_up']
				this_channel_form.tiling_scheme.data = channel_content['tiling_scheme']
				this_channel_form.tiling_overlap.data = channel_content['tiling_overlap']
				this_channel_form.z_step.data = channel_content['z_step']
				this_channel_form.left_lightsheet_used.data = channel_content['left_lightsheet_used']
				this_channel_form.right_lightsheet_used.data = channel_content['right_lightsheet_used']
			if this_image_resolution in current_app.config['LAVISION_RESOLUTIONS']:
				all_imaging_channels = current_app.config['LAVISION_IMAGING_CHANNELS']
			else:
				all_imaging_channels = current_app.config['SMARTSPIM_IMAGING_CHANNELS']

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
			sample_restrict_dict = {'sample_name':this_sample_name,
									'imaging_request_number':imaging_request_number,
									'imaging_batch_number':imaging_batch_number}
			this_sample_contents = db_lightsheet.Request.ClearingBatchSample() & sample_restrict_dict 
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
				""" Set up options for new image resolution dropdown """
				all_image_resolutions = current_app.config['LAVISION_RESOLUTIONS'] + current_app.config['SMARTSPIM_RESOLUTIONS']
				this_resolution_form.new_image_resolution.choices = [(x,x) for x in all_image_resolutions if x!=this_image_resolution]
				logger.debug("resolution form choices are now:")
				logger.debug(this_resolution_form.new_image_resolution.choices)
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
					this_channel_form.username.data = username
					this_channel_form.request_name.data = request_name
					this_channel_form.sample_name.data = this_sample_name
					this_channel_form.channel_name.data = channel_name
					this_channel_form.imaging_request_number.data = imaging_request_number
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
				if this_image_resolution in current_app.config['LAVISION_RESOLUTIONS']:
					all_imaging_channels = current_app.config['LAVISION_IMAGING_CHANNELS']
				else:
					all_imaging_channels = current_app.config['SMARTSPIM_IMAGING_CHANNELS']
				available_channels = [x for x in all_imaging_channels if x not in used_channels]
				logger.debug("Possible new channels to create are:")
				logger.debug(available_channels)
				this_resolution_form.new_channel_dropdown.choices = [(x,x) for x in available_channels]
				available_imaging_modes = current_app.config['IMAGING_MODES']
				if registration_channel_used:
					available_imaging_modes = [x for x in available_imaging_modes if x != 'registration']
				this_resolution_form.new_channel_purpose.choices = [(x,x) for x in available_imaging_modes]	
	n_active_samples = len([x for x in samples_imaging_progress_dict if samples_imaging_progress_dict[x] != 'complete'])
	logger.debug("samples_imaging_progress_dict:")
	logger.debug(samples_imaging_progress_dict)
	return render_template('imaging/imaging_batch_entry.html',form=form,
		rawdata_rootpath=rawdata_rootpath,imaging_table=imaging_table,
		sample_dict_list=sample_dict_list,
		samples_imaging_progress_dict=samples_imaging_progress_dict,
		n_active_samples=n_active_samples,
		imaging_request_number=imaging_request_number)

@imaging.route("/imaging/imaging_table/<username>/<request_name>/<sample_name>/<imaging_request_number>",methods=['GET','POST'])
@check_clearing_completed
@check_imaging_completed
@log_http_requests
def imaging_table(username,request_name,sample_name,imaging_request_number): 
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & \
			f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' 
	clearing_batch_sample_contents = db_lightsheet.Request.ClearingBatchSample() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' 
	imaging_overview_table = ImagingTable(imaging_request_contents*clearing_batch_sample_contents)
	imaging_progress = imaging_request_contents.fetch1('imaging_progress')
	
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & \
				f'request_name="{request_name}"' & \
				f'username="{username}"' & f'sample_name="{sample_name}"' & \
				f'imaging_request_number="{imaging_request_number}"' 
	imaging_channel_table = ImagingChannelTable(imaging_channel_contents)

	return render_template('imaging/imaging_log.html',
		imaging_overview_table=imaging_overview_table,
		imaging_channel_table=imaging_channel_table)


@imaging.route("/imaging/new_imaging_request/<username>/<request_name>",methods=['GET','POST'])
@logged_in
@log_http_requests
def new_imaging_request(username,request_name):
	""" Route for a user to enter a new request via a form """
	current_user = session['user']
	logger.info(f"{current_user} accessed new imaging request route")

	form = NewImagingRequestForm(request.form)
	request_contents = db_lightsheet.Request() & {'username':username,'request_name':request_name}
	species = request_contents.fetch1('species')
	correspondence_email = request_contents.fetch1('correspondence_email')
	all_imaging_modes = current_app.config['IMAGING_MODES']

	""" figure out the new imaging request number to give the new request """
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & f'request_name="{request_name}"' & \
			f'username="{username}"' 
	previous_imaging_request_numbers = np.unique(imaging_request_contents.fetch('imaging_request_number'))
	previous_max_imaging_request_number = max(previous_imaging_request_numbers)
	new_imaging_request_number = previous_max_imaging_request_number + 1
	all_imaging_modes = current_app.config['IMAGING_MODES']
	sample_contents = db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & \
			f'username="{username}"'
	number_of_samples = len(sample_contents)
	logger.debug("New imaging request number:")
	logger.debug(new_imaging_request_number)

	if request.method == 'POST':
		logger.info("POST request")
		if form.validate_on_submit():
			logger.info("Form validated")
			""" figure out which button was pressed """
			submit_keys = [x for x in form._fields.keys() if 'submit' in x and form[x].data == True]
			if len(submit_keys) == 1: # submit key was final submit button
				submit_key = submit_keys[0]
			else: # submit key came from within a sub-form, meaning one of the resolution table setup buttons
				logger.info("resolution table setup button pressed")
				""" find which sample this came from """
				submit_key = 'other'
				for ii in range(len(form.imaging_samples.data)):
					image_resolution_forms = form.imaging_samples[ii].image_resolution_forms
					imaging_dict = form.imaging_samples.data[ii]
					logger.debug("imaging dict:")
					logger.debug(imaging_dict)
					used_image_resolutions = [subform.image_resolution.data for subform in image_resolution_forms]
					if imaging_dict['new_image_resolution_form_submit'] == True:
						image_resolution_forsetup = imaging_dict['image_resolution_forsetup']
						logger.debug("setting up image resolution form for image resolution:")
						logger.debug(image_resolution_forsetup)
						image_resolution_forms.append_entry()
						resolution_table_index = len(image_resolution_forms.data)-1
						""" now pick out which form we currently just made """
						image_resolution_form = image_resolution_forms[resolution_table_index]
						image_resolution_form.image_resolution.data = image_resolution_forsetup
						used_image_resolutions.append(image_resolution_forsetup)
						""" Set the focus point for javascript to scroll to """
						if form.species.data == 'mouse' and image_resolution_forsetup !='2x':
							column_name = f'imaging_samples-{ii}-image_resolution_forms-{resolution_table_index}-channel_forms-0-registration'
						else:
							column_name = f'imaging_samples-{ii}-image_resolution_forms-{resolution_table_index}-channel_forms-0-generic_imaging'
							
						# Now make 4 new channel formfields and set defaults and channel names
						if image_resolution_forsetup in current_app.config['LAVISION_RESOLUTIONS']:
							all_imaging_channels = current_app.config['LAVISION_IMAGING_CHANNELS']
						else:
							all_imaging_channels = current_app.config['SMARTSPIM_IMAGING_CHANNELS']
						for x in range(4):
							channel_name = all_imaging_channels[x]
							logger.debug("Setting up channel form for channel:")
							logger.debug(channel_name)
							image_resolution_form.channel_forms[x].channel_name.data = channel_name
							
							if form.species.data == 'mouse' and channel_name == '488' and \
								(image_resolution_forsetup == "1.3x" or image_resolution_forsetup == "1.1x"):
								image_resolution_form.channel_forms[x].registration.data = 1
								
						resolution_choices = form.imaging_samples[ii].image_resolution_forsetup.choices
						logger.debug(resolution_choices)
						new_choices = [x for x in resolution_choices if x[0] not in used_image_resolutions]
						logger.debug(new_choices)
						form.imaging_samples[ii].image_resolution_forsetup.choices = new_choices
						break
				"""Now remove the image resolution the user just chose 
				from the list of choices for the next image resolution table """
				
			""" Handle all of the different "*submit*" buttons pressed """
			if submit_key == 'uniform_imaging_submit_button': # The uniform imaging button
				logger.info("uniform imaging button pressed")
				""" copy over all imaging/processing parameters from sample 1 to samples 2:last """
				sample1_imaging_sample_dict = form.imaging_samples[0].data
				sample1_image_resolution_form_dicts = sample1_imaging_sample_dict['image_resolution_forms']
				for ii in range(number_of_samples):
					if ii == 0: 
						continue
					this_sample_form = form.imaging_samples[ii]
					this_sample_form.reimaging_this_sample.data = True 
					""" Loop through the image resolutions and add each one """
					for jj in range(len(sample1_image_resolution_form_dicts)):

						sample1_image_resolution_form_dict = sample1_image_resolution_form_dicts[jj]
						sample1_image_resolution = sample1_image_resolution_form_dict['image_resolution']
						sample1_notes_for_imager = sample1_image_resolution_form_dict['notes_for_imager']
						sample1_notes_for_processor = sample1_image_resolution_form_dict['notes_for_processor']
						sample1_atlas_name = sample1_image_resolution_form_dict['atlas_name']
						form.imaging_samples[ii].image_resolution_forms.append_entry()
						this_image_resolution_form = form.imaging_samples[ii].image_resolution_forms[-1]
						this_image_resolution_form.image_resolution.data = sample1_image_resolution
						this_image_resolution_form.notes_for_imager.data = sample1_notes_for_imager
						this_image_resolution_form.notes_for_processor.data = sample1_notes_for_processor
						this_image_resolution_form.atlas_name.data = sample1_atlas_name
						sample1_channel_form_dicts = sample1_image_resolution_form_dict['channel_forms']
						""" Loop through channel dicts and copy the values for each key """
						for kk in range(len(sample1_channel_form_dicts)):
							sample1_channel_form_dict = sample1_channel_form_dicts[kk]
							sample1_channel_name = sample1_channel_form_dict['channel_name']
							sample1_channel_registration = sample1_channel_form_dict['registration']
							sample1_channel_injection_detection = sample1_channel_form_dict['injection_detection']
							sample1_channel_probe_detection = sample1_channel_form_dict['probe_detection']
							sample1_channel_cell_detection = sample1_channel_form_dict['cell_detection']
							sample1_channel_generic_imaging = sample1_channel_form_dict['generic_imaging']
							this_channel_form = this_image_resolution_form.channel_forms[kk]
							this_channel_form.channel_name.data = sample1_channel_name
							this_channel_form.registration.data = sample1_channel_registration
							this_channel_form.injection_detection.data = sample1_channel_injection_detection
							this_channel_form.probe_detection.data = sample1_channel_probe_detection
							this_channel_form.cell_detection.data = sample1_channel_cell_detection
							this_channel_form.generic_imaging.data = sample1_channel_generic_imaging
				column_name = 'uniform_imaging_submit_button'

			elif submit_key == 'submit': # The final submit button
				logger.debug("Final submission")

				""" Start a transaction for doing the inserts.
					This is done to avoid inserting only into Request()
					table but not any of the dependent tables if there is an error 
					at any point during any of the code block """
				connection = db_lightsheet.Request.connection
				with connection.transaction:
					now = datetime.now()
					date = now.strftime("%Y-%m-%d")
					time = now.strftime("%H:%M:%S") 

					''' Now loop through all samples and make the insert lists '''
					sample_insert_list = [] # only to keep track of certain things for other inserts
					clearing_batch_insert_list = []
					imaging_batch_insert_list = []
					imaging_request_insert_list = []
					imaging_resolution_insert_list = []
					processing_request_insert_list = []
					processing_resolution_insert_list = [] 
					channel_insert_list = []
					sample_imaging_dict = {} # keep track of what imaging needs to be done for each sample -- used for making imaging batches later 
					for ii in range(number_of_samples):
						sample_form_dict = form.imaging_samples[ii].data  
						sample_needs_reimaging = sample_form_dict['reimaging_this_sample']
						if not sample_needs_reimaging:
							continue    
						sample_name = sample_form_dict['sample_name']              
						sample_insert_dict = {}
						""" Set up sample insert dict """
						sample_insert_dict['request_name'] = request_name
						''' Add primary keys that are not in the form '''
						sample_insert_dict['username'] = username 
						sample_insert_dict['sample_name'] = sample_name
						sample_insert_list.append(sample_insert_dict)

						""" Now imaging batch """
						imaging_batch_insert_dict = {}
						imaging_batch_insert_dict['username'] = username 
						imaging_batch_insert_dict['request_name'] = request_name
						imaging_batch_insert_dict['imaging_request_number'] = new_imaging_request_number
						imaging_batch_insert_dict['imaging_request_date_submitted'] = date
						imaging_batch_insert_dict['imaging_request_time_submitted'] = time

						if form.self_imaging.data == True:
							logger.debug("Self imaging selected!")
							imaging_batch_insert_dict['imager'] = username
						else:
							logger.debug("Self imaging not selected")
						imaging_batch_insert_dict['imaging_progress'] = 'incomplete'
						imaging_res_channel_dict = {} 
						
					   
						""" Set up ImagingRequest and ProcessingRequest insert dicts """
						imaging_sample_form_dict = form.imaging_samples[ii].data
						""" When user submits this request form it is always 
						the first imaging request and processing request for this sample """

						""" ImagingRequest """
						imaging_request_insert_dict = {}
						imaging_request_insert_dict['request_name'] = request_name
						imaging_request_insert_dict['username'] = username 
						imaging_request_insert_dict['sample_name'] = sample_name
						imaging_request_insert_dict['imaging_request_number'] = new_imaging_request_number
						if form.self_imaging.data:
							imaging_request_insert_dict['imager'] = username
						imaging_request_insert_dict['imaging_request_date_submitted'] = date
						imaging_request_insert_dict['imaging_request_time_submitted'] = time
						imaging_request_insert_dict['imaging_progress'] = "incomplete"
						imaging_request_insert_list.append(imaging_request_insert_dict)
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

						logger.debug("Made raw, output and viz directories")

						""" ProcessingRequest - make it regardless of microscope or resolution used """
						processing_request_insert_dict = {}
						processing_request_number = 1
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
						processing_request_insert_list.append(processing_request_insert_dict)

						""" Now insert each image resolution/channel combo """
						
						for resolution_dict in imaging_sample_form_dict['image_resolution_forms']:
							# logger.debug(resolution_dict)
							image_resolution = resolution_dict['image_resolution']
							imaging_res_channel_dict[image_resolution] = []
							""" imaging entry first """
							imaging_resolution_insert_dict = {}
							imaging_resolution_insert_dict['request_name'] = request_name
							imaging_resolution_insert_dict['username'] = username 
							imaging_resolution_insert_dict['sample_name'] = sample_name
							imaging_resolution_insert_dict['imaging_request_number'] = new_imaging_request_number
							imaging_resolution_insert_dict['image_resolution'] = image_resolution
							if image_resolution in current_app.config['LAVISION_RESOLUTIONS']:
								microscope = 'LaVision'
								imaging_resolution_insert_dict['microscope'] = microscope
							elif image_resolution in current_app.config['SMARTSPIM_RESOLUTIONS']:
								microscope = 'SmartSPIM'
								imaging_resolution_insert_dict['microscope'] = microscope
							imaging_resolution_insert_dict['notes_for_imager'] = resolution_dict['notes_for_imager']
							imaging_resolution_insert_list.append(imaging_resolution_insert_dict)
							""" now processing entry (if not 2x imaging request)"""
							if image_resolution != '2x':
								processing_resolution_insert_dict = {}
								processing_resolution_insert_dict['request_name'] = request_name
								processing_resolution_insert_dict['username'] = username 
								processing_resolution_insert_dict['sample_name'] = sample_name
								processing_resolution_insert_dict['imaging_request_number'] = new_imaging_request_number
								processing_resolution_insert_dict['processing_request_number'] = processing_request_number
								processing_resolution_insert_dict['image_resolution'] = image_resolution
								processing_resolution_insert_dict['notes_for_processor'] = resolution_dict['notes_for_processor']
								processing_resolution_insert_dict['atlas_name'] = resolution_dict['atlas_name']
								processing_resolution_insert_dict['final_orientation'] = resolution_dict['final_orientation']
								processing_resolution_insert_list.append(processing_resolution_insert_dict)
					 

							""" now loop through the imaging channels and fill out the ImagingChannel entries """
							for imaging_channel_dict in resolution_dict['channel_forms']:
								""" The way to tell which channels were picked is to see 
								which have at least one imaging mode selected """
								
								used_imaging_modes = [key for key in all_imaging_modes if imaging_channel_dict[key] == True]
								if not any(used_imaging_modes):
									continue
								else:
									channel_name = imaging_channel_dict['channel_name']
									imaging_res_channel_dict[image_resolution].append(channel_name)
									channel_insert_dict = {}
									channel_insert_dict['imaging_request_number'] = new_imaging_request_number 
									channel_insert_dict['request_name'] = request_name    
									channel_insert_dict['username'] = username
									channel_insert_dict['sample_name'] = sample_name
									channel_insert_dict['image_resolution'] = resolution_dict['image_resolution']
									for key,val in imaging_channel_dict.items(): 
										if key == 'csrf_token': 
											continue # pragma: no cover - used to exclude this line from calculating test coverage
										channel_insert_dict[key] = val
									channel_insert_list.append(channel_insert_dict)
							# logger.info(channel_insert_list)
							imaging_batch_insert_dict['imaging_dict'] = imaging_res_channel_dict
						sample_imaging_dict[sample_name] = imaging_res_channel_dict
						imaging_batch_insert_list.append(imaging_batch_insert_dict)
					
					
					""" Figure out the ImagingBatch() entries
					and ImagingBatchSample() entries.
					An imaging batch is determined by a set of samples
					IN THE SAME CLEARING BATCH
					that need to be imaged at the same resolutions and same 
					imaging channels at those resolutions for a given request. """
					restrict_dict = {'username':username,'request_name':request_name}
					clearing_batch_sample_contents = db_lightsheet.Request.ClearingBatchSample() & \
						restrict_dict
					# Loop over existing imaging batch dictionaries  
					new_list = [] # dummy list of imaging dicts ('resolution1':[channel_name1,channel_name2,...],....)
					good_indices = [] # indices of original imaging_batch_insert_list that we will use in the end
					counts = [] # number in each batch, index shared with new_list
					notes_for_clearer_each_batch = [] # concatenated 
					for index,dict_ in enumerate(imaging_batch_insert_list):
						imaging_dict = dict_['imaging_dict']
						sample_name = sample_insert_list[index]['sample_name']
						# Figure out clearing batch number from our ClearingBatchSample() insert dicts
						clearing_batch_number = [d['clearing_batch_number'] for d in clearing_batch_sample_contents if d['sample_name'] == sample_name][0]
						imaging_dict['clearing_batch_number'] = clearing_batch_number
						try: 
							# if imaging dict in new_list, then find the index corresponding to this batch
							i = new_list.index(imaging_dict)
						except ValueError: 
							# a new imaging dict 
							counts.append(1)
							new_list.append(imaging_dict)
							good_indices.append(index)
						else: # only gets executed if try block doesn't generate an error
							counts[i] += 1 
					logger.debug("Figured out imaging batches:")
					logger.debug(new_list)
					logger.debug(good_indices)
					logger.debug(counts)
					""" remake imaging_batch_insert_list to only have unique entries """

					# Figure out how many clearing batches we have
					imaging_batch_insert_list = []
					imaging_batch_sample_insert_list = []
					n_clearing_batches = max([d['clearing_batch_number'] for d in clearing_batch_sample_contents])
					for clearing_batch_number in range(1,n_clearing_batches+1):
						# Figure out which samples are in this clearing batch
						samples_this_clearing_batch = [d['sample_name'] for d in clearing_batch_sample_contents if d['clearing_batch_number'] == clearing_batch_number]
						# Loop over the unique imaging dicts IN THIS CLEARING BATCH
						# and assign an imaging batch number and figure out how many samples are in each imaging batch
						imaging_dicts_this_clearing_batch = [d for d in new_list if d['clearing_batch_number'] == clearing_batch_number]
						imaging_batch_number = 1
						for imaging_dict in imaging_dicts_this_clearing_batch:
							imaging_batch_insert_dict = {
								'username':username,
								'request_name':request_name,
								'clearing_batch_number':clearing_batch_number,
								'imaging_request_number':new_imaging_request_number,
								'imaging_batch_number':imaging_batch_number,
								'imaging_request_date_submitted': date,
								'imaging_request_time_submitted': time,
								'imaging_dict':imaging_dict,
								}
							if form.self_imaging.data == True:
								logger.debug("Self imaging selected!")
								imaging_batch_insert_dict['imager'] = username
							else:
								logger.debug("Self imaging not selected")
							imaging_batch_insert_dict['imaging_progress'] = 'incomplete'
							n_samples_this_clearing_and_imaging_batch = 0
							for sample_name in samples_this_clearing_batch:
								try:
									this_sample_imaging_dict = sample_imaging_dict[sample_name]
									if this_sample_imaging_dict == imaging_dict:
										imaging_batch_sample_insert_dict = {
										'username':username,
										'request_name':request_name,
										'clearing_batch_number':clearing_batch_number,
										'imaging_request_number':new_imaging_request_number,
										'imaging_batch_number':imaging_batch_number,
										'sample_name':sample_name
										}
										imaging_batch_sample_insert_list.append(imaging_batch_sample_insert_dict)
										n_samples_this_clearing_and_imaging_batch += 1
								except:
									logger.debug(f"Sample {sample_name} not in imaging dict")
							imaging_batch_insert_dict['number_in_imaging_batch'] = n_samples_this_clearing_and_imaging_batch
							imaging_batch_number += 1
							imaging_batch_insert_list.append(imaging_batch_insert_dict)
					
					logger.info("ImagingBatch() insert ")
					logger.info(imaging_batch_insert_list)
					db_lightsheet.Request.ImagingBatch().insert(imaging_batch_insert_list,)
					
					logger.info("ImagingBatchSample() insert ")
					logger.info(imaging_batch_sample_insert_list)
					db_lightsheet.Request.ImagingBatchSample().insert(imaging_batch_sample_insert_list,)
					
					logger.debug("Sample imaging dict:")
					logger.debug(sample_imaging_dict)
					
					db_lightsheet.Request.ImagingRequest().insert(imaging_request_insert_list)
					# logger.info("ProcessingRequest() insert:")
					# logger.info(processing_request_insert_list)
					""" If there were no processing resolution requests (because all were 2x imaging requests),
					then don't make a processing request """
					if len(processing_resolution_insert_list) > 0:
						db_lightsheet.Request.ProcessingRequest().insert(processing_request_insert_list)
						""" Make the directory on /jukebox corresponding to this processing request """
					# logger.info("ImagingResolutionRequest() insert:")
					# logger.info(imaging_resolution_insert_list)
					db_lightsheet.Request.ImagingResolutionRequest().insert(imaging_resolution_insert_list)
					# logger.info("ProcessingResolutionRequest() insert:")
					# logger.info(processing_resolution_insert_list)
					if len(processing_resolution_insert_list) > 0:
						db_lightsheet.Request.ProcessingResolutionRequest().insert(processing_resolution_insert_list)
					# logger.info('channel insert:')
					# logger.info(channel_insert_list)
					
					db_lightsheet.Request.ImagingChannel().insert(channel_insert_list)
				
				flash("Your new imaging request was submitted successfully. You will receive an email at "
					  f"{correspondence_email} with further instructions ","success")
				flash("If you elected to clear or image any of your samples yourself "
					 "then head to Task Management -> All Imaging Tasks in the top Menu Bar "
					 "to start the imaging entry form when ready. "
					 "If not, your samples will be imaged by the Core Facility and "
					 "you will receive an email once they are done. You can check the "
					 "status of your samples at your request page (see table below).", "success")
				

				hosturl = os.environ['HOSTURL']
				imaging_manager_url = f'https://{hosturl}' + url_for('imaging.imaging_manager')
				samples_need_reimaging_str = ', '.join(d['sample_name'] for d in sample_insert_list)
				subject = 'Lightserv automated email: New Imaging request received'
				message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
					'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
					'A new imaging request for your request:\n'
					f'request_name: {request_name}\n'
					f'Samples that need re-imaging: {samples_need_reimaging_str}\n\n'
					f'has been received. Check the imaging management GUI: {imaging_manager_url}\n'
					'if you designated yourself as the imager for any of these samples\n\n'
					'Otherwise, the imaging will be handled by the Core Facility, and you will receive '
					'emails when the imaging is complete.\n\n'
					'Thanks,\nThe Histology and Brain Registration Core Facility.')
				request_contents = db_lightsheet.Request() & \
					{'username':username,'request_name':request_name}
				correspondence_email = request_contents.fetch1('correspondence_email')
				recipients = [correspondence_email]

				if not os.environ['FLASK_MODE'] == 'TEST':
					send_email.delay(subject=subject,body=message_body,recipients=recipients) # pragma: no cover - used to exclude this line from calculating test coverage

				""" Now send an email to the imaging managers if
				the person did not set themself as the imager """
				if not (form.self_imaging == True):
					subject = 'Lightserv automated email: New Imaging Request Submitted. Sample(s) ready for imaging'
					hosturl = os.environ['HOSTURL']
					message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
						'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
						'A new imaging request for a previously existing request:\n'
						f'username: "{username}"\n'
						f'request_name: "{request_name}"\n\n'
						'was just made.\n\n'
						f'Samples that need re-imaging are: {samples_need_reimaging_str}\n\n'
						f'The imaging batches containing these samples will now show up in the Imaging Management GUI: {imaging_manager_url}\n\n'
						'Thanks,\nThe Histology and Brain Registration Core Facility.')
					recipients = [x + '@princeton.edu' for x in current_app.config['IMAGING_ADMINS']]
					if not os.environ['FLASK_MODE'] == 'TEST':
						send_email.delay(subject=subject,body=message_body,recipients=recipients) 
				return redirect(url_for('requests.all_requests'))
			
		else: # post request but not validated. Need to handle some errors

			if 'submit' in form.errors:
				for error_str in form.errors['submit']:
					flash(error_str,'danger')
			
			logger.debug("Not validated! See error dict below:")
			logger.debug(form.errors)
			logger.debug("")
			flash_str = 'There were errors below. Correct them before proceeding'
			flash(flash_str,'danger')
			""" deal with errors in the samples section - those will not always 
			show up in the proper place """
			
			if 'imaging_samples' in form.errors:
				for obj in form.errors['imaging_samples']:
					flash(obj,'danger')
			if 'number_of_samples' in form.errors:
				for error_str in form.errors['number_of_samples']:
					flash(error_str,'danger')

	if request.method=='GET':
		logger.info("GET request")
		form.species.data = species
		form.number_of_samples.data = number_of_samples
		""" Clear out any previously existing imaging sample forms """
		while len(form.imaging_samples) > 0:
			form.imaging_samples.pop_entry() # pragma: no cover - used to exclude this line from calculating test coverage
		""" Make nsamples sets of sample fields and render them """
		for sample_dict in sample_contents:
			sample_name = sample_dict['sample_name']
			logger.debug("Sample form checked:")
			logger.debug(sample_dict)
			form.imaging_samples.append_entry()
			sample_form = form.imaging_samples[-1]
			sample_form.sample_name.data = sample_name

		column_name = 'imaging_samples-0-sample_name'
		# form.subject_fullname.choices = [('test','test')] 

	if 'column_name' not in locals():
		column_name = ''
	
	request_summary_table = RequestSummaryTable(request_contents)
	existing_imaging_contents = db_lightsheet.Request.ImagingChannel() & \
		{'username':username,'request_name':request_name}
	existing_imaging_table = ExistingImagingTable(existing_imaging_contents)

	logger.debug(f"Column name right before render is: {column_name}")

	return render_template('imaging/new_imaging_request.html',form=form,
		request_summary_table=request_summary_table,
		existing_imaging_table=existing_imaging_table,
		column_name=column_name)
