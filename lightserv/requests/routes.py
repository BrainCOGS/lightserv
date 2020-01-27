from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)

from lightserv.requests.forms import NewRequestForm, UpdateNotesForm
from lightserv.requests.tables import (AllRequestTable,
	RequestOverviewTable, create_dynamic_samples_table,
	AllSamplesTable)
from lightserv import db_lightsheet
from lightserv.main.utils import (logged_in, table_sorter,logged_in_as_processor,
	check_clearing_completed,check_imaging_completed,log_http_requests)
from lightserv import cel,mail
from flask_mail import Message
import datajoint as dj

from functools import partial
# from lightsheet_py3
import glob

import secrets

# import neuroglancer
# import cloudvolume
import numpy as np

import pymysql
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/experiment_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

# neuroglancer.set_static_content_source(url='https://neuromancer-seung-import.appspot.com')

requests = Blueprint('requests',__name__)

@requests.route("/requests/all_requests")
@log_http_requests
@logged_in
def all_requests(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed all_requests page")
	request_contents = db_lightsheet.Request()
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch()
	imaging_request_contents = db_lightsheet.Request.ImagingRequest()
	processing_request_contents = db_lightsheet.Request.ProcessingRequest()
	if current_user in ['ahoag','zmd','ll3','kellyms','jduva']:
		legend = 'All core facility requests'
	else:
		legend = 'Your core facility requests'
		request_contents = request_contents & f'username="{current_user}"'
		# sample_contents = sample_contents & f'username="{current_user}"'
		imaging_request_contents = imaging_request_contents & f'username="{current_user}"'
		processing_request_contents = processing_request_contents & f'username="{current_user}"'
	# logger.debug(request_contents)
	''' Now figure out what fraction of the samples in each request are cleared/imaged/processed '''	
	replicated_args = dict(number_of_samples='number_of_samples',description='description',
		species='species',datetime_submitted='datetime_submitted')

	sample_joined_contents = dj.U('username','request_name').aggr(
		request_contents * clearing_batch_contents,
		number_of_samples='number_of_samples',
		description='description',
		species='species',
		datetime_submitted='TIMESTAMP(date_submitted,time_submitted)',
		n_cleared='CONVERT(SUM(clearing_progress="complete"),char)').proj(
		**replicated_args,
			fraction_cleared='CONCAT(n_cleared,"/",CONVERT(number_of_samples,char))')

	imaging_joined_contents = dj.U('username','request_name').aggr(
	sample_joined_contents * imaging_request_contents,
	**replicated_args,
	fraction_cleared='fraction_cleared',
	n_imaged='CONVERT(SUM(imaging_progress="complete"),char)',
	total_imaging_requests='CONVERT(COUNT(*),char)'
	).proj(**replicated_args,
		fraction_cleared='fraction_cleared',
		fraction_imaged='CONCAT(n_imaged,"/",total_imaging_requests)'
		)

	processing_joined_contents = dj.U('username','request_name').aggr(
	imaging_joined_contents * processing_request_contents,
	**replicated_args,
	fraction_cleared='fraction_cleared',
	fraction_imaged='fraction_imaged',
	n_processed='CONVERT(SUM(processing_progress="complete"),char)',
	total_processing_requests='CONVERT(COUNT(*),char)'
	).proj(
		**replicated_args,
		fraction_cleared='fraction_cleared',
		fraction_imaged='fraction_imaged',
		fraction_processed='CONCAT(n_processed,"/",total_processing_requests)'
		)

	sort = request.args.get('sort', 'request_name') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	sorted_results = sorted(processing_joined_contents.fetch(as_dict=True),
		key=partial(table_sorter,sort_key=sort),reverse=reverse) # partial allows you to pass in a parameter to the function

	table = AllRequestTable(sorted_results,sort_by=sort,
					  sort_reverse=reverse)
	table.table_id = 'horizontal'
	return render_template('requests/all_requests.html',request_contents=processing_joined_contents,request_table=table,legend=legend)

@requests.route("/request_overview/<username>/<request_name>",)
@logged_in
@log_http_requests
def request_overview(username,request_name):
	""" A route for displaying a single request. """

	request_contents = db_lightsheet.Request() & f'request_name="{request_name}"' & \
			f'username="{username}"'
	request_contents = request_contents.proj('description','species','number_of_samples',
		datetime_submitted='TIMESTAMP(date_submitted,time_submitted)')
	samples_contents = db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & f'username="{username}"' 
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & \
	f'request_name="{request_name}"' & f'username="{username}"' 
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & \
	 f'request_name="{request_name}"' & f'username="{username}"' 
	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
	 f'request_name="{request_name}"' & f'username="{username}"' 

	combined_contents = (samples_contents * clearing_batch_contents * \
		imaging_request_contents * processing_request_contents)

	all_contents_dict_list = combined_contents.fetch(as_dict=True)
	logger.debug(all_contents_dict_list)

	keep_keys = ['username','request_name','sample_name','species',
				 'clearing_protocol','antibody1','antibody2','clearing_progress',
				 'clearing_batch_number','datetime_submitted']
	final_dict_list = []

	for d in all_contents_dict_list:
		username = d.get('username')
		request_name = d.get('request_name')
		current_sample_name = d.get('sample_name')
		
		# clearing_batch_query_dict = dict(
		# 	username=username,request_name=request_name,
		# 	clearing_protocol=d.get('clearing_protocol'),
		# 	antibody1=d.get('antibody1'),
		# 	antibody2=d.get('antibody2'),
		# 	clearing_batch_number=d.get('clearing_batch_number')
		# 	)
		
		# clearing_batch_contents = db_lightsheet & clearing_batch_query_dict
		# clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
		imaging_request_number = d.get('imaging_request_number')

		imager = d.get('imager')
		imaging_progress = d.get('imaging_progress')
		imaging_request_dict = {'username':username,'request_name':request_name,
							    'sample_name':current_sample_name,
								'imaging_request_number':imaging_request_number,
							   'imager':imager,'imaging_progress':imaging_progress}
		processing_request_number = d.get('processing_request_number')
		processor = d.get('processor')
		processing_progress = d.get('processing_progress')
		processing_request_dict = {'username':username,'request_name':request_name,
								   'sample_name':current_sample_name,
								   'imaging_request_number':imaging_request_number,
								   'processing_request_number':processing_request_number,
								   'processor':processor,'processing_progress':processing_progress}
		existing_sample_names = [x.get('sample_name') for x in final_dict_list]

		if current_sample_name not in existing_sample_names: # Then new sample, new imaging request, new processing request
			new_dict_values = list(map(d.get,keep_keys))
			new_dict = {keep_keys[ii]:new_dict_values[ii] for ii in range(len(keep_keys))}
			new_dict['imaging_requests'] = []
			imaging_request_dict['processing_requests'] = [processing_request_dict]
			new_dict['imaging_requests'].append(imaging_request_dict)
			final_dict_list.append(new_dict)
		else:
			# A repeated sample name could either be
			# a new imaging request or a new processing request at the same imaging request
			existing_index = existing_sample_names.index(current_sample_name)
			existing_dict = final_dict_list[existing_index]
			existing_imaging_request_dicts = existing_dict['imaging_requests']
			existing_imaging_request_numbers = [x.get('imaging_request_number') for x in existing_imaging_request_dicts]
			if imaging_request_number not in existing_imaging_request_numbers: # Then its a new imaging request and processing request
				imaging_request_dict['processing_requests'] = [processing_request_dict]
				existing_dict['imaging_requests'].append(imaging_request_dict)
			else: # Then it's an old imaging request and new processing request
				existing_imaging_request_index = existing_imaging_request_numbers.index(imaging_request_number)
				existing_imaging_request_dict = existing_imaging_request_dicts[existing_imaging_request_index]
				existing_imaging_request_dict['processing_requests'].append(processing_request_dict)
	# logger.debug(final_dict_list)
	# The first time page is loaded, sort, reverse, table_id are all not set so they become their default
	sort = request.args.get('sort', 'request_name') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	samples_table_id = 'horizontal_samples_table'
	samples_table = create_dynamic_samples_table(final_dict_list,
		sort_by=sort,sort_reverse=reverse,table_id=samples_table_id,ignore_columns=['notes_for_clearer'])
	request_table = RequestOverviewTable(request_contents)

	samples_table.table_id = samples_table_id
	return render_template('requests/request_overview.html',request_contents=request_contents,
		request_table=request_table,samples_table=samples_table)

@requests.route("/requests/all_samples")
@logged_in
@log_http_requests
def all_samples(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed all_samples page")
	request_contents = db_lightsheet.Request()
	sample_contents = db_lightsheet.Request.Sample()
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch()
	imaging_request_contents = db_lightsheet.Request.ImagingRequest()
	processing_request_contents = db_lightsheet.Request.ProcessingRequest()
	if current_user in ['ahoag','zmd','ll3','kellyms','jduva']:
		legend = 'All core facility samples (from all requests)'
	else:
		legend = 'Your core facility samples (from all of your requests)'
		sample_contents = sample_contents & f'username="{current_user}"'
		request_contents = request_contents & f'username="{current_user}"'
		clearing_batch_contents = clearing_batch_contents & f'username="{current_user}"'
		imaging_request_contents = imaging_request_contents & f'username="{current_user}"'
		processing_request_contents = processing_request_contents & f'username="{current_user}"'
	
	clearing_joined_contents = (sample_contents * request_contents * clearing_batch_contents).proj(
		request_name='request_name',sample_name='sample_name',
		species='species',clearing_protocol='clearing_protocol',
		clearing_progress='clearing_progress',
		datetime_submitted='TIMESTAMP(date_submitted,time_submitted)')
	''' Now figure out what fraction of imaging requests have been fulfilled '''	
	replicated_args = dict(species='species',clearing_protocol='clearing_protocol',
	imaging_request_number='imaging_request_number',imager='imager',
	imaging_progress='imaging_progress',
	clearing_progress='clearing_progress',
	antibody1='antibody1',antibody2='antibody2',
	clearing_batch_number='clearing_batch_number',
	datetime_submitted='datetime_submitted')

	imaging_joined_contents = dj.U('username','request_name','sample_name').aggr(
		clearing_joined_contents*imaging_request_contents,
		**replicated_args)

	processing_joined_contents = dj.U('username','request_name','sample_name').aggr(
		imaging_joined_contents*processing_request_contents,
		**replicated_args,processing_request_number='processing_request_number',
	processor='processor',processing_progress='processing_progress')

	all_contents_dict_list = processing_joined_contents.fetch(as_dict=True)
	keep_keys = ['username','request_name','sample_name','species',
				 'clearing_protocol','clearing_progress','antibody1','antibody2',
				 'clearing_batch_number','n_imaging_requests',
				 'n_processing_requests','datetime_submitted']
	final_dict_list = []

	for d in all_contents_dict_list:
		username = d.get('username')
		request_name = d.get('request_name')
		current_sample_name = d.get('sample_name')
		imaging_request_number = d.get('imaging_request_number')
		imager = d.get('imager')
		imaging_progress = d.get('imaging_progress')
		imaging_request_dict = {'username':username,'request_name':request_name,
							    'sample_name':current_sample_name,
							    'imaging_request_number':imaging_request_number,
							   'imager':imager,'imaging_progress':imaging_progress}
		processing_request_number = d.get('processing_request_number')
		processor = d.get('processor')
		processing_progress = d.get('processing_progress')
		processing_request_dict = {'username':username,'request_name':request_name,
							       'sample_name':current_sample_name,
								   'imaging_request_number':imaging_request_number,
								   'processing_request_number':processing_request_number,
									  'processor':processor,'processing_progress':processing_progress}
		existing_sample_names = [x.get('sample_name') for x in final_dict_list]
		if current_sample_name not in existing_sample_names: # Then new sample, new imaging request, new processing request
			new_dict_values = list(map(d.get,keep_keys))
			new_dict = {keep_keys[ii]:new_dict_values[ii] for ii in range(len(keep_keys))}
			new_dict['imaging_requests'] = []
			imaging_request_dict['processing_requests'] = [processing_request_dict]
			new_dict['imaging_requests'].append(imaging_request_dict)
			final_dict_list.append(new_dict)
		else:
			# A repeated sample name could either be
			# a new imaging request or a new processing request at the same imaging request
			existing_index = existing_sample_names.index(current_sample_name)
			existing_dict = final_dict_list[existing_index]
			existing_imaging_request_dicts = existing_dict['imaging_requests']
			existing_imaging_request_numbers = [x.get('imaging_request_number') for x in existing_imaging_request_dicts]
			if imaging_request_number not in existing_imaging_request_numbers: # Then its a new imaging request and processing request
				imaging_request_dict['processing_requests'] = [processing_request_dict]
				existing_dict['imaging_requests'].append(imaging_request_dict)
			else: # Then it's an old imaging request and new processing request
				existing_imaging_request_index = existing_imaging_request_numbers.index(imaging_request_number)
				existing_imaging_request_dict = existing_imaging_request_dicts[existing_imaging_request_index]
				existing_imaging_request_dict['processing_requests'].append(processing_request_dict)

	sort = request.args.get('sort', 'request_name') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	sorted_results = sorted(final_dict_list,
		key=partial(table_sorter,sort_key=sort),reverse=reverse) # partial allows you to pass in a parameter to the function
	
	table = AllSamplesTable(sorted_results,sort_by=sort,
					  sort_reverse=reverse)
	table.table_id = 'all_samples_table'
	return render_template('requests/all_samples.html',samples_table=table,
		combined_contents=final_dict_list,legend=legend)

@requests.route("/request/new",methods=['GET','POST'])
@logged_in
@log_http_requests
def new_request():
	""" Route for a user to enter a new request via a form """
	all_imaging_modes = current_app.config['IMAGING_MODES']

	current_user = session['user']
	logger.info(f"{current_user} accessed new request form")

	form = NewRequestForm(request.form)

	if request.method == 'POST':
		logger.info("POST request")
		if form.validate_on_submit():
			logger.info("Form validated")
			""" figure out which button was pressed """
			submit_keys = [x for x in form._fields.keys() if 'submit' in x and form[x].data == True]
			if len(submit_keys) == 1: # submit key was either sample setup or final submit button
				submit_key = submit_keys[0]
			else: # submit key came from within a sub-form, meaning one of the resolution table setup buttons
				logger.info("resolution table setup button pressed")
				""" find which sample this came from """
				submit_key = 'other'
				for ii in range(len(form.imaging_samples.data)):
					imaging_dict = form.imaging_samples.data[ii]
					if imaging_dict['new_image_resolution_form_submit'] == True:
						image_resolution_forsetup = imaging_dict['image_resolution_forsetup']
						image_resolution_forms = form.imaging_samples[ii].image_resolution_forms
						image_resolution_forms.append_entry()
						resolution_table_index = len(image_resolution_forms.data)-1
						""" now pick out which form we currently just made """
						image_resolution_form = image_resolution_forms[resolution_table_index]
						image_resolution_form.image_resolution.data = image_resolution_forsetup
						
						""" Set the focus point for javascript to scroll to """
						if form.species.data == 'mouse':
							column_name = f'imaging_samples-{ii}-image_resolution_forms-{resolution_table_index}-channel_forms-0-registration'
						else:
							column_name = f'imaging_samples-{ii}-image_resolution_forms-{resolution_table_index}-channel_forms-0-generic_imaging'
							
						# Now make 4 new channel formfields and set defaults and channel names
						for x in range(4):
							# image_resolution_form.channels.append_entry()
							channel_name = current_app.config['IMAGING_CHANNELS'][x]
							image_resolution_form.channel_forms[x].channel_name.data = channel_name
							# Make the default for channel 488 to be 1.3x imaging with registration checked
							if form.species.data != 'mouse':
								logger.info("Species != mouse! Disabling registration/detection options")
								image_resolution_form.channel_forms[x].registration.render_kw = {'disabled':'disabled'}
								image_resolution_form.channel_forms[x].injection_detection.render_kw = {'disabled':'disabled'}
								image_resolution_form.channel_forms[x].probe_detection.render_kw = {'disabled':'disabled'}
								image_resolution_form.channel_forms[x].cell_detection.render_kw = {'disabled':'disabled'}
							elif channel_name == '488' and image_resolution_forsetup == "1.3x":
								image_resolution_form.channel_forms[x].registration.data = 1

			""" Handle all of the different "*submit*" buttons pressed """
			if submit_key == 'sample_submit_button': # The sample setup button
				logger.info("sample submit")
				nsamples = form.number_of_samples.data

				""" Render all of the clearing and imaging fields """
				# make nsamples sets of sample fields
				for ii in range(nsamples):
					form.clearing_samples.append_entry()
					form.clearing_samples[ii].sample_name.data = form.request_name.data + '-' + f'{ii+1}'.zfill(3)
					if form.species.data == 'rat':
						form.clearing_samples[ii].clearing_protocol.data = 'iDISCO abbreviated clearing (rat)'

					form.imaging_samples.append_entry()
				# """ Now disable the fields in the top section """
				# logger.debug(form.species.data)
				# form.species_display.data = form.species.data
				# logger.debug(form.species_display.data)
				# form.species_display.render_kw = {'disabled':'disabled'}
				# form.hide_species(value=form.species.data)
				# form.subject_fullname.render_kw = {'disabled':'disabled'}


				column_name = 'clearing_samples-0-sample_name'



			elif submit_key == 'uniform_clearing_submit_button': # The uniform clearing button
				logger.info("uniform clearing button pressed")
				""" copy over all clearing parameters from sample 1 to samples 2:last """
				sample1_clearing_sample_dict = form.clearing_samples[0].data
				sample1_perfusion_date = sample1_clearing_sample_dict['perfusion_date']
				sample1_expected_handoff_date = sample1_clearing_sample_dict['expected_handoff_date']
				sample1_clearing_protocol = sample1_clearing_sample_dict['clearing_protocol']
				sample1_antibody1 = sample1_clearing_sample_dict['antibody1']
				sample1_antibody2 = sample1_clearing_sample_dict['antibody2']
				for ii in range(form.number_of_samples.data):
					if ii == 0:
						continue
					form.clearing_samples[ii].perfusion_date.data = sample1_perfusion_date
					form.clearing_samples[ii].expected_handoff_date.data = sample1_expected_handoff_date
					form.clearing_samples[ii].clearing_protocol.data = sample1_clearing_protocol
					form.clearing_samples[ii].antibody1.data = sample1_antibody1
					form.clearing_samples[ii].antibody2.data = sample1_antibody2
				column_name = 'uniform_clearing_submit_button'

			elif submit_key == 'uniform_imaging_submit_button': # The uniform imaging button
				logger.info("uniform imaging button pressed")
				""" copy over all imaging/processing parameters from sample 1 to samples 2:last """
				sample1_imaging_sample_dict = form.imaging_samples[0].data
				sample1_image_resolution_form_dicts = sample1_imaging_sample_dict['image_resolution_forms']

				for ii in range(form.number_of_samples.data):
					if ii == 0:
						continue
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
					This is done to avoid inserting only into Experiment
					table but not Sample and ImagingChannel tables if there is an error 
					at any point during any of the inserts"""
				connection = db_lightsheet.Request.connection
				with connection.transaction:
					if form.username.data:
						username = form.username.data
						princeton_email = username + '@princeton.edu'
						""" insert into User() db table 
						with skip_duplicates=True in case username 
						is not already in there. """
						user_insert_dict = dict(username=username,princeton_email=princeton_email)
						db_lightsheet.User().insert1(user_insert_dict,skip_duplicates=True)
					else:
						username = current_user
					princeton_email_current_user = current_user + '@princeton.edu'
					
					current_user_insert_dict = dict(username=current_user,
						princeton_email=princeton_email_current_user)
					db_lightsheet.User().insert1(current_user_insert_dict,skip_duplicates=True)
					request_insert_dict = dict(request_name=form.request_name.data,
						username=username,requested_by=current_user,
						labname=form.labname.data.lower(),
						subject_fullname=form.subject_fullname.data,
						correspondence_email=form.correspondence_email.data.lower(),
						description=form.description.data,species=form.species.data,
						number_of_samples=form.number_of_samples.data,
						testing=form.testing.data)
					now = datetime.now()
					date = now.strftime("%Y-%m-%d")
					time = now.strftime("%H:%M:%S") 
					request_insert_dict['date_submitted'] = date
					request_insert_dict['time_submitted'] = time

					db_lightsheet.Request().insert1(request_insert_dict)
					
					''' Sample section '''
					clearing_samples = form.clearing_samples.data
					imaging_samples = form.imaging_samples.data
					number_of_samples = form.number_of_samples.data

					''' Now loop through all samples and make the insert lists '''
					sample_insert_list = []
					clearing_batch_insert_list = []
					imaging_request_insert_list = []
					imaging_resolution_insert_list = []
					processing_request_insert_list = []
					processing_resolution_insert_list = [] 
					channel_insert_list = []
					for ii in range(number_of_samples):
						clearing_sample_form_dict = form.clearing_samples[ii].data		
						sample_name = clearing_sample_form_dict['sample_name']				
						sample_insert_dict = {}
						""" Set up sample insert dict """
						''' Add primary keys that are not in the form '''
						sample_insert_dict['request_name'] = form.request_name.data

						sample_insert_dict['username'] = username 
						sample_insert_dict['sample_name'] = sample_name
						
						""" update sample insert dict with clearing form data """
						sample_insert_dict['clearing_protocol'] = clearing_sample_form_dict['clearing_protocol']
						sample_insert_dict['antibody1'] = clearing_sample_form_dict['antibody1']
						sample_insert_dict['antibody2'] = clearing_sample_form_dict['antibody2']
						sample_insert_list.append(sample_insert_dict)

						""" Now clearing batch """
						clearing_batch_insert_dict = {}
						clearing_batch_insert_dict['request_name'] = form.request_name.data
						clearing_batch_insert_dict['username'] = username 
						clearing_batch_insert_dict['clearing_protocol'] = clearing_sample_form_dict['clearing_protocol']
						clearing_batch_insert_dict['antibody1'] = clearing_sample_form_dict['antibody1']
						clearing_batch_insert_dict['antibody2'] = clearing_sample_form_dict['antibody2']
						if form.self_clearing.data:
							clearing_batch_insert_dict['clearer'] = username
						clearing_batch_insert_dict['clearing_progress'] = 'incomplete'
						perfusion_date = clearing_sample_form_dict['perfusion_date']
						if perfusion_date:
							clearing_batch_insert_dict['perfusion_date'] = perfusion_date
						expected_handoff_date = clearing_sample_form_dict['expected_handoff_date']
						if expected_handoff_date:
							clearing_batch_insert_dict['expected_handoff_date'] = expected_handoff_date
						clearing_batch_insert_dict['notes_for_clearer'] = clearing_sample_form_dict['notes_for_clearer']
						clearing_batch_insert_list.append(clearing_batch_insert_dict)
						""" Set up ImagingRequest and ProcessingRequest insert dicts """
						imaging_sample_form_dict = form.imaging_samples[ii].data
						""" When user submits this request form it is always 
						the first imaging request and processing request for this sample """

						""" ImagingRequest """
						imaging_request_insert_dict = {}
						imaging_request_number = 1
						imaging_request_insert_dict['request_name'] = form.request_name.data
						imaging_request_insert_dict['username'] = username 
						imaging_request_insert_dict['sample_name'] = sample_name
						imaging_request_insert_dict['imaging_request_number'] = imaging_request_number
						if form.self_imaging.data:
							imaging_request_insert_dict['imager'] = username
						imaging_request_insert_dict['imaging_request_date_submitted'] = date
						imaging_request_insert_dict['imaging_request_time_submitted'] = time
						imaging_request_insert_dict['imaging_progress'] = "incomplete"
						imaging_request_insert_list.append(imaging_request_insert_dict)

						""" ProcessingRequest """
						processing_request_insert_dict = {}
						processing_request_number = 1
						processing_request_insert_dict['request_name'] = form.request_name.data
						processing_request_insert_dict['username'] = username 
						processing_request_insert_dict['sample_name'] = sample_name
						processing_request_insert_dict['imaging_request_number'] = imaging_request_number
						processing_request_insert_dict['processing_request_number'] = processing_request_number
						processing_request_insert_dict['processing_request_date_submitted'] = date
						processing_request_insert_dict['processing_request_time_submitted'] = time
						processing_request_insert_dict['processing_progress'] = "incomplete"
						# """ The user is always the "processor" - i.e. the person
						#  who double-checks the processing form and hits GO """
						# processing_request_insert_dict['processor'] = username
						processing_request_insert_list.append(processing_request_insert_dict)

						""" Now insert each image resolution/channel combo """
						
						for resolution_dict in imaging_sample_form_dict['image_resolution_forms']:
							# logger.debug(resolution_dict)
							""" imaging entry first """
							imaging_resolution_insert_dict = {}
							imaging_resolution_insert_dict['request_name'] = form.request_name.data
							imaging_resolution_insert_dict['username'] = username 
							imaging_resolution_insert_dict['sample_name'] = sample_name
							imaging_resolution_insert_dict['imaging_request_number'] = imaging_request_number
							imaging_resolution_insert_dict['image_resolution'] = resolution_dict['image_resolution']
							imaging_resolution_insert_dict['notes_for_imager'] = resolution_dict['notes_for_imager']
							imaging_resolution_insert_list.append(imaging_resolution_insert_dict)
							""" now processing entry """
							processing_resolution_insert_dict = {}
							processing_resolution_insert_dict['request_name'] = form.request_name.data
							processing_resolution_insert_dict['username'] = username 
							processing_resolution_insert_dict['sample_name'] = sample_name
							processing_resolution_insert_dict['imaging_request_number'] = imaging_request_number
							processing_resolution_insert_dict['processing_request_number'] = processing_request_number
							processing_resolution_insert_dict['image_resolution'] = resolution_dict['image_resolution']
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
									channel_insert_dict = {}
									channel_insert_dict['imaging_request_number'] = imaging_request_number 
									channel_insert_dict['request_name'] = form.request_name.data	
									channel_insert_dict['username'] = username
									channel_insert_dict['sample_name'] = sample_name
									channel_insert_dict['image_resolution'] = resolution_dict['image_resolution']
									for key,val in imaging_channel_dict.items(): 
										if key == 'csrf_token': 
											continue # pragma: no cover - used to exclude this line from testing
										channel_insert_dict[key] = val
									channel_insert_list.append(channel_insert_dict)
							# logger.info(channel_insert_list)
					
					""" Now figure out the number in each clearing batch """
					new_list = []
					good_indices = []
					counts = []
					for index,dict_ in enumerate(clearing_batch_insert_list):
						subdict = {key:dict_[key] for key in dict_.keys() if key == 'clearing_protocol' \
									or key == 'antibody1' or key == 'antibody2'}
						try: # check if new_list contains the dict already
							i = new_list.index(subdict)
						except ValueError:
							counts.append(1)
							new_list.append(subdict)
							good_indices.append(index)
						else:
							counts[i] += 1

					clearing_batch_insert_list = [clearing_batch_insert_list[index] for index in good_indices]
					for ii in range(len(clearing_batch_insert_list)):
						insert_dict = clearing_batch_insert_list[ii]
						insert_dict['number_in_batch'] = counts[ii]
						insert_dict['clearing_batch_number'] = ii+1
					
					""" Now loop through all sample insert dicts and assign clearing batch number """
					for sample_insert_dict in sample_insert_list:
						sample_clearing_protocol,sample_antibody1,sample_antibody2 = \
							list(map(sample_insert_dict.get,['clearing_protocol','antibody1','antibody2']))
						""" Figure out which clearing batch this corresponds to """
						for clearing_batch_insert_dict in clearing_batch_insert_list:
							clearing_batch_clearing_protocol,clearing_batch_antibody1,clearing_batch_antibody2 = \
							list(map(clearing_batch_insert_dict.get,['clearing_protocol','antibody1','antibody2']))
							if (clearing_batch_clearing_protocol == sample_clearing_protocol and \
									clearing_batch_antibody1 == sample_antibody1 and \
									clearing_batch_antibody2 == sample_antibody2):
								clearing_batch_number = clearing_batch_insert_dict.get('clearing_batch_number')
								sample_insert_dict['clearing_batch_number'] = clearing_batch_number

					# logger.info("ClearingBatch() insert ")
					# logger.info(clearing_batch_insert_list)
					db_lightsheet.Request.ClearingBatch().insert(clearing_batch_insert_list,)
					# logger.info("Sample() insert:")
					# logger.debug(sample_insert_list)
					db_lightsheet.Request.Sample().insert(sample_insert_list)
					# logger.info("ImagingRequest() insert:")
					# logger.info(imaging_request_insert_list)
					db_lightsheet.Request.ImagingRequest().insert(imaging_request_insert_list)
					# logger.info("ProcessingRequest() insert:")
					# logger.info(processing_request_insert_list)
					db_lightsheet.Request.ProcessingRequest().insert(processing_request_insert_list)
					# logger.info("ImagingResolutionRequest() insert:")
					# logger.info(imaging_resolution_insert_list)
					db_lightsheet.Request.ImagingResolutionRequest().insert(imaging_resolution_insert_list)
					# logger.info("ProcessingResolutionRequest() insert:")
					# logger.info(processing_resolution_insert_list)
					db_lightsheet.Request.ProcessingResolutionRequest().insert(processing_resolution_insert_list)
					# logger.info('channel insert:')
					# logger.info(channel_insert_list)
					
					db_lightsheet.Request.ImagingChannel().insert(channel_insert_list)
					
					flash("Request submitted successfully. You will receive an email at "
						  f"{form.correspondence_email.data} with instructions " 
						  "for setting up your spock account in order for this "
						  "portal to run your jobs.","success")
					flash("If you elected to clear any of your tubes "
						 "then head to Task Management -> All Clearing Tasks in the Menu Bar"
						 " to start the clearing entry form. "
						 "If not, your tubes will be cleared by the Core Facility and "
						 "you will receive an email once they are cleared. You can check the "
						 "status of your samples at your request page (see table below).", "success")
					msg = Message('Lightserv automated email',
						sender='lightservhelper@gmail.com',
						recipients=['ahoag@princeton.edu']) # keep it to me while in DEV phase
					with open('/home/ahoag/.ssh/id_rsa.pub','r') as keyfile: 
						keyfile_contents = keyfile.readlines() 
					ssh_key_text = keyfile_contents[0].strip('\n')
					spock_link = 'http://braincogs00.pni.princeton.edu' + url_for('main.spock_connection_test')
					msg.body = ('Hello!\n\nThis is an automated email sent from lightserv, '
						'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
						'Your request:\n'
						f'request_name: "{form.request_name.data}"\n'
						'was successfully submitted.\n\nIn order for us to process your data, '
						'you will need to copy the following ssh public key into the following file on spock.pni.princeton.edu: '
						f'/home/{username}/.ssh/authorized_keys\n\n'
						'If this file does not already exist, log in to spock and create it using the command: '
						f'mkdir /home/{username}/.ssh; touch /home/{username}/.ssh/authorized_keys\n\n'
						'If you have never logged in to spock before, please see the documentation:  '
						f'https://npcdocs.princeton.edu/index.php/Spock#Accessing_spock\n'
						'If you are unable to log in to to spock and make the file, '
						'please contact pnihelp@princeton.edu\n\n'
						f'The ssh key you need to copy into the file is: \n{ssh_key_text}\n\n'
						f'When you have copied over the key, test your connection to spock at: {spock_link}\n\n'
						'DISCLAIMER: By copying this key over to your account on spock, you are authorizing the Core Facility to '
						'run spock jobs as you, and as a result your spock karma will be affected as if you ran the job yourself. '
						'Please respond to this message if you have any questions about this or any other issue regarding your request.\n\n'
						'Thanks,\nThe Histology and Brain Registration Core Facility.')
					mail.send(msg)
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
			if 'clearing_samples' in form.errors:
				for obj in form.errors['clearing_samples']:
					if isinstance(obj,dict):

						for key,val in list(obj.items()):
							for error_str in val:
								flash(error_str,'danger')
					elif isinstance(obj,str):
						flash(obj,'danger')
			elif 'imaging_samples' in form.errors:
				for obj in form.errors['imaging_samples']:
					flash(obj,'danger')
			if 'number_of_samples' in form.errors:
				for error_str in form.errors['number_of_samples']:
					flash(error_str,'danger')
	""" Make default checkboxes -- can't be done in forms.py unfortunately: https://github.com/lepture/flask-wtf/issues/362 """
	if request.method=='GET':
		logger.info("GET request")

		if not form.correspondence_email.data:	
			form.correspondence_email.data = current_user + '@princeton.edu' 

		# form.subject_fullname.choices = [('test','test')] 

	if 'column_name' not in locals():
		column_name = ''
	

	return render_template('requests/new_request.html', title='new_request',
		form=form,legend='New Request',column_name=column_name)	

