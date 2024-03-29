from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)

from lightserv.requests.forms import (NewRequestForm, UpdateNotesForm,
 ConfirmDeleteForm)
from lightserv.requests.tables import (AllRequestTable,
	RequestOverviewTable, create_dynamic_samples_table,
	AllSamplesTable)
from lightserv import cel,db_lightsheet, smtp_connect
from lightserv.main.utils import (logged_in, table_sorter,logged_in_as_processor,
	check_clearing_completed,check_imaging_completed,log_http_requests,
	request_exists,mymkdir, logged_in_as_request_owner,clearing_not_yet_started,
	check_user_in_g_lightsheet_data)
from lightserv.main.tasks import send_email

import datajoint as dj

from functools import partial
import os,glob

import secrets

import numpy as np

import pymysql
import logging
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/requests_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

requests = Blueprint('requests',__name__)

@requests.route("/requests/all_requests",methods=['GET','POST'])
@log_http_requests
@logged_in
def all_requests(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed all_requests page")
	request_contents = db_lightsheet.Request()
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch()
	imaging_request_contents = db_lightsheet.Request.ImagingRequest()
	processing_request_contents = db_lightsheet.Request.ProcessingRequest()
	if current_user in current_app.config['CLEARING_ADMINS']:
		legend = 'All core facility requests'
	else:
		legend = 'Your core facility requests'
		restrict_OR_list = [{"username":current_user},{"auditor":current_user}]
		request_contents = request_contents & restrict_OR_list
		imaging_request_contents = (request_contents*imaging_request_contents & restrict_OR_list).proj(
			'imager',
			'imaging_progress')
		processing_request_contents = (request_contents*processing_request_contents & restrict_OR_list).proj(
			'processor',
			'processing_progress')
	# logger.debug(request_contents)
	''' Now figure out what fraction of the samples in each request are cleared/imaged/processed '''    
	replicated_args = dict(is_archival='is_archival',number_of_samples='number_of_samples',description='description',
		species='species',datetime_submitted='datetime_submitted')

	request_joined_contents = dj.U('username','request_name').aggr(
		request_contents.join(clearing_batch_contents,left=True),
		is_archival='MIN(is_archival)',
		number_of_samples='MIN(number_of_samples)',
		number_in_batch='MIN(number_in_batch)',
		description='MIN(description)',
		species='MIN(species)',
		datetime_submitted='TIMESTAMP(MIN(date_submitted),MIN(time_submitted))',
		n_cleared='CONVERT(SUM(IF(clearing_progress="complete",number_in_batch,0)),char)').proj(
		**replicated_args,
			fraction_cleared='CONCAT(n_cleared,"/",CONVERT(number_of_samples,char))')

	imaging_aggr_contents = dj.U('username','request_name').aggr(
		imaging_request_contents,
		n_imaged='CONVERT(SUM(imaging_progress="complete"),char)',
		total_imaging_requests='CONVERT(COUNT(*),char)',
		)
	imaging_joined_contents = (request_joined_contents.join(imaging_aggr_contents,left=True)).proj(**replicated_args,
		fraction_cleared='fraction_cleared',
		fraction_imaged='IF(n_imaged is NULL,"0/0",CONCAT(n_imaged,"/",total_imaging_requests))' 
		)
	processing_aggr_contents = dj.U('username','request_name').aggr(
		processing_request_contents,
		n_processed='CONVERT(SUM(processing_progress="complete"),char)',
		total_processing_requests='CONVERT(COUNT(processing_progress),char)',
		)
	processing_joined_contents = (imaging_joined_contents.join(processing_aggr_contents,left=True)).proj(
		**replicated_args,
		fraction_cleared='fraction_cleared',
		fraction_imaged='fraction_imaged',
		fraction_processed='IF(n_processed is NULL,"0/0",CONCAT(n_processed,"/",total_processing_requests))' 
		)  
	
	sort = request.args.get('sort', 'datetime_submitted') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'desc') == 'desc')
	sorted_results = sorted(processing_joined_contents.fetch(as_dict=True),
		key=partial(table_sorter,sort_key=sort),reverse=reverse) # partial allows you to pass in a parameter to the function

	table = AllRequestTable(sorted_results,sort_by=sort,
					  sort_reverse=reverse)
	table.table_id = 'horizontal'

	form = ConfirmDeleteForm()
	if request.method == 'POST':
		if form.validate_on_submit():
			return redirect(url_for('requests.delete_request',
				username=current_user,request_name=form.request_name.data))
		else:
			for key in form.errors:
				error = form.errors[key]
				flash(error,'danger')
	logger.debug((processing_joined_contents & {'username':'cz15'}).fetch('request_name','datetime_submitted'))
	return render_template('requests/all_requests.html',
		request_contents=processing_joined_contents,request_table=table,
		legend=legend,form=form)

@requests.route("/request_overview/<username>/<request_name>",)
@logged_in
@log_http_requests
@request_exists
def request_overview(username,request_name):
	""" A route for displaying information about a single request 
	and its associated samples. """
	logger.debug(f"{username} accessed request_overview")
	request_contents = db_lightsheet.Request() & f'request_name="{request_name}"' & \
			f'username="{username}"'
	request_contents = request_contents.proj('description','species','number_of_samples',
		'is_archival',datetime_submitted='TIMESTAMP(date_submitted,time_submitted)')
	sample_contents = db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & f'username="{username}"' 
	
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & \
		f'request_name="{request_name}"' & f'username="{username}"' 
	clearing_batch_sample_contents = db_lightsheet.Request.ClearingBatchSample() & \
		f'request_name="{request_name}"' & f'username="{username}"' 
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & \
		f'request_name="{request_name}"' & f'username="{username}"' 
	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
		f'request_name="{request_name}"' & f'username="{username}"' 

	replicated_args = dict(number_of_samples='number_of_samples',description='description',
		species='species',clearing_progress='clearing_progress',
		clearer='clearer',
		imaging_progress='imaging_progress',imager='imager',
		is_archival='is_archival',
		link_to_clearing_spreadsheet='link_to_clearing_spreadsheet')
	sample_joined_contents = request_contents * clearing_batch_sample_contents * clearing_batch_contents.proj(
	'clearing_progress','clearer','link_to_clearing_spreadsheet')
	imaging_aggr_contents = dj.U('username','request_name','sample_name').aggr(
		imaging_request_contents,
		imaging_progress='MIN(imaging_progress)',
		imager='MIN(imager)',
		imaging_request_number='MIN(imaging_request_number)',
		total_imaging_requests='COUNT(*)',
		n_imaged='CONVERT(SUM(imaging_progress="complete"),char)',).proj(**replicated_args,
			   total_imaging_requests='IF(n_imaged is NULL, "0",total_imaging_requests)',
			   imaging_request_number='IF(imaging_request_number is NULL, "N/A",imaging_request_number)')

	imaging_joined_contents = sample_joined_contents.join(imaging_aggr_contents,left=True)

	processing_aggr_contents = dj.U('username','request_name').aggr(   
		processing_request_contents,
		processing_request_number='MIN(processing_request_number)',
		processor='MIN(processor)',
		processing_progress='MIN(processing_progress)',
		n_processed='CONVERT(SUM(processing_progress="complete"),char)',
		total_processing_requests='CONVERT(COUNT(processing_progress),char)')


	processing_joined_contents = (imaging_joined_contents.join(processing_aggr_contents,left=True)).proj(
		**replicated_args,
		imaging_request_number='imaging_request_number',
		total_imaging_requests='total_imaging_requests',
		processing_request_number='IF(processing_request_number is NULL, "N/A",processing_request_number)',
		processor='IF(processor is NULL,"N/A",processor)',
		processing_progress='IF(processing_progress is NULL,"N/A",processing_progress)',
		total_processing_requests='IF(n_processed is NULL,0,total_processing_requests)', 
	)
	
	all_contents_dict_list = processing_joined_contents.fetch(as_dict=True)
	logger.debug(all_contents_dict_list)
	keep_keys = ['username','request_name','sample_name','species',
				 'clearing_protocol','antibody1','antibody2','clearing_progress',
				 'clearer','clearing_batch_number','datetime_submitted','is_archival',
				 'link_to_clearing_spreadsheet']
	
	""" Go through all samples in this request and for each of its 
	imaging and processing requests assemble a dictionary to feed to
	the table maker """

	final_dict_list = []
	for d in all_contents_dict_list:
		username = d.get('username')
		request_name = d.get('request_name')
		current_sample_name = d.get('sample_name')
		
		imaging_request_number = d.get('imaging_request_number')
		is_archival = d.get('is_archival')
		imager = d.get('imager')
		imaging_progress = d.get('imaging_progress')
		imaging_request_dict = {'username':username,'request_name':request_name,
								'sample_name':current_sample_name,
								'imaging_request_number':imaging_request_number,
							   'imager':imager,'imaging_progress':imaging_progress,
							   'is_archival':is_archival}
		processing_request_number = d.get('processing_request_number')
		processor = d.get('processor')
		processing_progress = d.get('processing_progress')
		processing_request_dict = {'username':username,'request_name':request_name,
								   'sample_name':current_sample_name,
								   'imaging_request_number':imaging_request_number,
								   'processing_request_number':processing_request_number,
								   'processor':processor,'processing_progress':processing_progress,
								   'is_archival':is_archival}
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
	# logger.
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
	request_contents = request_contents.proj('description','species','number_of_samples',
		'is_archival','auditor',
		datetime_submitted='TIMESTAMP(date_submitted,time_submitted)')
	sample_contents = db_lightsheet.Request.Sample()
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch()
	imaging_request_contents = db_lightsheet.Request.ImagingRequest()
	processing_request_contents = db_lightsheet.Request.ProcessingRequest()
	if current_user not in current_app.config['CLEARING_ADMINS']:
		legend = 'Your core facility samples (from all of your requests)'
		restrict_OR_list = [{"username":current_user},{"auditor":current_user}]
		request_contents = request_contents & restrict_OR_list
		sample_contents = (request_contents*sample_contents & restrict_OR_list).proj()
		clearing_batch_contents = (request_contents*clearing_batch_contents & restrict_OR_list).proj(
			'clearer','clearing_progress','link_to_clearing_spreadsheet')
		imaging_request_contents = (request_contents*imaging_request_contents & restrict_OR_list).proj(
			'imager','imaging_progress')
		processing_request_contents = (request_contents*processing_request_contents & restrict_OR_list).proj(
			'processor','processing_progress')
	else:
		legend = 'All core facility samples (from all requests)'
	
	replicated_args = dict(number_of_samples='number_of_samples',description='description',
		species='species',datetime_submitted='datetime_submitted',
		clearer='clearer',
		clearing_progress='clearing_progress',
		imager='imager',imaging_progress='imaging_progress',
		is_archival='is_archival',
		link_to_clearing_spreadsheet='link_to_clearing_spreadsheet')
	
	sample_joined_contents = request_contents * sample_contents * clearing_batch_contents
	
	imaging_joined_contents = sample_joined_contents.join(imaging_request_contents,left=True) 
	df1 = pd.DataFrame(imaging_joined_contents.fetch(as_dict=True))
	df2 = pd.DataFrame(processing_request_contents.fetch(as_dict=True))

	# processing_joined_contents = imaging_joined_contents * processing_request_contents 
	processing_joined_contents = pd.merge(df1,df2,
		how='left',on=["username","request_name","sample_name","imaging_request_number"])
	
	# all_contents_dict_list = processing_joined_contents.fetch(as_dict=True)
	all_contents_dict_list = processing_joined_contents.to_dict('records')
	keep_keys = ['username','request_name','sample_name','species',
				 'clearing_protocol','clearer','clearing_progress',
				 'antibody1','antibody2',
				 'clearing_batch_number','n_imaging_requests',
				 'n_processing_requests','datetime_submitted','is_archival',
				 'link_to_clearing_spreadsheet']
	# Assemble the list of dictionaries to pass to the flask table creator
	# Each dict will contain a list of imaging requests which will in turn
	# contain a list of processing requests
	final_dict_list = []
	for d in all_contents_dict_list:
		username = d.get('username')
		request_name = d.get('request_name')
		is_archival = d.get('is_archival')
		current_sample_name = d.get('sample_name')
		imaging_request_number = d.get('imaging_request_number')
		imager = d.get('imager')
		imaging_progress = d.get('imaging_progress')
		imaging_request_dict = {'username':username,'request_name':request_name,
								'sample_name':current_sample_name,
								'imaging_request_number':imaging_request_number,
								'imager':imager,'imaging_progress':imaging_progress,
								'is_archival':is_archival}
		processing_request_number = d.get('processing_request_number')
		if not np.isnan(processing_request_number):
			processing_request_number = int(processing_request_number)
		processor = d.get('processor')
		processing_progress = d.get('processing_progress')
		processing_request_dict = {'username':username,'request_name':request_name,
								   'sample_name':current_sample_name,
								   'imaging_request_number':imaging_request_number,
								   'processing_request_number':processing_request_number,
									  'processor':processor,'processing_progress':processing_progress,
									  'is_archival':is_archival}

		existing_sample_names = [x.get('sample_name') for x in final_dict_list \
								 if x['username']==username and x['request_name']==request_name]
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
			# First pull out imaging request dict list  for this request
			existing_dict = [d for d in final_dict_list if d.get('username') == username and \
							d.get('request_name') == request_name and \
							d.get('sample_name') == current_sample_name][0]
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
					image_resolution_forms = form.imaging_samples[ii].image_resolution_forms
					imaging_dict = form.imaging_samples.data[ii]
					used_image_resolutions = [subform.image_resolution.data for subform in image_resolution_forms]
					logger.debug("Used image resolutions for this sample:")
					logger.debug(used_image_resolutions)
					if imaging_dict['new_image_resolution_form_submit'] == True:
						image_resolution_forsetup = imaging_dict['image_resolution_forsetup']
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
							# image_resolution_form.channels.append_entry()
							channel_name = all_imaging_channels[x]
							image_resolution_form.channel_forms[x].channel_name.data = channel_name
							
							if form.species.data == 'mouse' and channel_name == '488' and image_resolution_forsetup == "1.3x":
								image_resolution_form.channel_forms[x].registration.data = 1
							# if form.species.data == 'mouse' and channel_name == '555' and image_resolution_forsetup == "1.3x":
							#     image_resolution_form.channel_forms[x].injection_detection.data = 1
								
						logger.info(f"Column name is: {column_name}")
						resolution_choices = form.imaging_samples[ii].image_resolution_forsetup.choices
						logger.debug(resolution_choices)
						new_choices = [x for x in resolution_choices if x[0] not in used_image_resolutions]
						logger.debug(new_choices)
						form.imaging_samples[ii].image_resolution_forsetup.choices = new_choices
						break
				"""Now remove the image resolution the user just chose 
				from the list of choices for the next image resolution table """
				
			""" Handle all of the different "*submit*" buttons pressed """
			if submit_key == 'sample_submit_button': # The sample setup button
				logger.info("sample submit")
				nsamples = form.number_of_samples.data

				""" Make nsamples sets of sample fields and render them """
				for ii in range(nsamples):
					form.clearing_samples.append_entry()
					form.clearing_samples[ii].sample_name.data = form.request_name.data + '-' + f'{ii+1}'.zfill(3)
					current_choices = form.clearing_samples[ii].clearing_protocol.choices
					if form.species.data == 'mouse':
						new_choices = [x for x in current_choices if 'rat' not in x[0].lower()]
					if form.species.data == 'rat':
						new_choices = [x for x in current_choices if 'rat' in x[0].lower()]                        
						form.clearing_samples[ii].clearing_protocol.data = 'iDISCO abbreviated clearing (rat)'
					form.clearing_samples[ii].clearing_protocol.choices = new_choices
					form.imaging_samples.append_entry()

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
					This is done to avoid inserting only into Request()
					table but not any of the dependent tables if there is an error 
					at any point during any of the code block """
				connection = db_lightsheet.Request.connection
				with connection.transaction:
					""" If someone else's username is entered, then
					override the username dictionary entry to use this """
					if form.other_username.data:
						username = form.other_username.data
						logger.info(f"Other username entered. Setting username={username}")
						princeton_email = username + '@princeton.edu'
						""" insert into User() db table 
						with skip_duplicates=True in case username 
						is not already in there. """
						user_insert_dict = dict(username=username,princeton_email=princeton_email)
						db_lightsheet.User().insert1(user_insert_dict,skip_duplicates=True)
					else:
						username = current_user
						logger.info(f"Form filled out by current user with username={username}.")

					""" Check if someone wants an auditor on their request """

					if form.auditor_username.data:
						auditor_username = form.auditor_username.data
						logger.info(f"Auditor entered: {auditor_username}")
						auditor_princeton_email = auditor_username + '@princeton.edu'
						""" insert into User() db table 
						with skip_duplicates=True in case username 
						is not already in there. """
						auditor_user_insert_dict = dict(username=auditor_username,
							princeton_email=auditor_princeton_email)
						db_lightsheet.User().insert1(auditor_user_insert_dict,skip_duplicates=True)
					else:
						auditor_username = None
					princeton_email_current_user = current_user + '@princeton.edu' # for autofill
					
					current_user_insert_dict = dict(username=current_user,
						princeton_email=princeton_email_current_user)
					db_lightsheet.User().insert1(current_user_insert_dict,skip_duplicates=True)
					
					request_insert_dict = dict(request_name=form.request_name.data,
						username=username,requested_by=current_user,
						auditor=auditor_username,
						labname=form.labname.data.lower(),
						correspondence_email=form.correspondence_email.data.lower(),
						description=form.description.data,species=form.species.data,
						number_of_samples=form.number_of_samples.data,
						raw_data_retention_preference=form.raw_data_retention_preference.data,
						testing=form.testing.data)
					now = datetime.now()
					date = now.strftime("%Y-%m-%d")
					time = now.strftime("%H:%M:%S") 
					request_insert_dict['date_submitted'] = date
					request_insert_dict['time_submitted'] = time
					logger.debug("Inserting into Request()")
					logger.debug(request_insert_dict)
					db_lightsheet.Request().insert1(request_insert_dict)

					''' Sample section '''
					clearing_samples = form.clearing_samples.data
					imaging_samples = form.imaging_samples.data
					number_of_samples = form.number_of_samples.data

					''' Now loop through all samples and make the insert lists '''
					sample_insert_list = []
					clearing_batch_insert_list = []
					imaging_batch_insert_list = []
					imaging_request_insert_list = []
					imaging_resolution_insert_list = []
					processing_request_insert_list = []
					processing_resolution_insert_list = [] 
					channel_insert_list = []
					sample_imaging_dict = {} # keep track of what imaging needs to be done for each sample -- used for making imaging batches later 
					for ii in range(number_of_samples):
						clearing_sample_form_dict = form.clearing_samples[ii].data      
						sample_name = clearing_sample_form_dict['sample_name']              
						subject_fullname = clearing_sample_form_dict['subject_fullname']              
						sample_insert_dict = {}
						""" Set up sample insert dict """
						sample_insert_dict['request_name'] = form.request_name.data
						''' Add primary keys that are not in the form '''
						sample_insert_dict['username'] = username 
						sample_insert_dict['sample_name'] = sample_name
						sample_insert_dict['subject_fullname'] = subject_fullname
						sample_insert_dict['clearing_protocol'] = clearing_sample_form_dict['clearing_protocol']
						sample_insert_dict['antibody1'] = clearing_sample_form_dict['antibody1'].strip()
						sample_insert_dict['antibody2'] = clearing_sample_form_dict['antibody2'].strip()
						sample_insert_list.append(sample_insert_dict)

						""" Now clearing batch """
						clearing_batch_insert_dict = {}
						clearing_batch_insert_dict['request_name'] = form.request_name.data
						clearing_batch_insert_dict['username'] = username 
						clearing_batch_insert_dict['clearing_protocol'] = clearing_sample_form_dict['clearing_protocol']
						clearing_batch_insert_dict['antibody1'] = clearing_sample_form_dict['antibody1'].strip()
						clearing_batch_insert_dict['antibody2'] = clearing_sample_form_dict['antibody2'].strip()
						
						if form.self_clearing.data == True:
							logger.debug("Self clearing selected!")
							clearing_batch_insert_dict['clearer'] = username
						else:
							logger.debug("Self clearing not selected")
						clearing_batch_insert_dict['clearing_progress'] = 'incomplete'
						perfusion_date = clearing_sample_form_dict['perfusion_date']
						if perfusion_date:
							clearing_batch_insert_dict['perfusion_date'] = perfusion_date
						expected_handoff_date = clearing_sample_form_dict['expected_handoff_date']
						if expected_handoff_date:
							clearing_batch_insert_dict['expected_handoff_date'] = expected_handoff_date
						clearing_batch_insert_dict['notes_for_clearer'] = clearing_sample_form_dict['notes_for_clearer']
						clearing_batch_insert_list.append(clearing_batch_insert_dict)

						""" Now imaging batch """
						imaging_batch_insert_dict = {}
						imaging_batch_insert_dict['username'] = username 
						imaging_batch_insert_dict['request_name'] = form.request_name.data
						imaging_batch_insert_dict['imaging_request_number'] = 1 # always 1 since this is a new request
						imaging_batch_insert_dict['imaging_request_date_submitted'] = date
						imaging_batch_insert_dict['imaging_request_time_submitted'] = time

						# imaging_batch_insert_dict['imaging_request_number'] = 1
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
						""" Make the directory on /jukebox corresponding to this imaging request """
						raw_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
							username,form.request_name.data,sample_name,f'imaging_request_{imaging_request_number}',
							'rawdata')
						output_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
							username,form.request_name.data,sample_name,f'imaging_request_{imaging_request_number}',
							'output')
						viz_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
							username,form.request_name.data,sample_name,f'imaging_request_{imaging_request_number}',
							'viz')
						mymkdir(raw_path_to_make)
						mymkdir(output_path_to_make)
						mymkdir(viz_path_to_make)

						logger.debug("Made raw, output and viz directories")

						""" ProcessingRequest - make it regardless of microscope or resolution used """
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
							imaging_resolution_insert_dict['request_name'] = form.request_name.data
							imaging_resolution_insert_dict['username'] = username 
							imaging_resolution_insert_dict['sample_name'] = sample_name
							imaging_resolution_insert_dict['imaging_request_number'] = imaging_request_number
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
								processing_resolution_insert_dict['request_name'] = form.request_name.data
								processing_resolution_insert_dict['username'] = username 
								processing_resolution_insert_dict['sample_name'] = sample_name
								processing_resolution_insert_dict['imaging_request_number'] = imaging_request_number
								processing_resolution_insert_dict['processing_request_number'] = processing_request_number
								processing_resolution_insert_dict['image_resolution'] = image_resolution
								processing_resolution_insert_dict['notes_for_processor'] = resolution_dict['notes_for_processor']
								processing_resolution_insert_dict['atlas_name'] = resolution_dict['atlas_name']
								processing_resolution_insert_dict['final_orientation'] = resolution_dict['final_orientation']
								processing_resolution_insert_list.append(processing_resolution_insert_dict)
								# """ Make processing path on /jukebox """
								# processing_path_to_make = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
								# username,form.request_name.data,sample_name,f'imaging_request_{imaging_request_number}',
								# 'output',f'processing_request_{processing_request_number}',f'resolution_{image_resolution}')
								# mymkdir(processing_path_to_make)

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
									channel_insert_dict['imaging_request_number'] = imaging_request_number 
									channel_insert_dict['request_name'] = form.request_name.data    
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
					
					""" Figure out the ClearingBatch() and ClearingBatchSample() inserts.
					A clearing batch is determined by unique combination of 
					clearing_protocol, antibody1, antibody2 for a given request.
					
					Update the clearing_batch_insert_list to only have as many
					entries as clearing batches, removing the redundant entries.

					Make sure notes_for_clearer
					fields are concatenated for all samples in a batch """
					
					new_list = [] # dummy list of subdicts only containing the 3 important keys
					good_indices = [] # indices of original clearing_batch_insert_list that we will use in the end
					counts = [] # number in each batch, index shared with new_list
					notes_for_clearer_each_batch = [] # concatenated 
					for index,dict_ in enumerate(clearing_batch_insert_list):
						subdict = {key:dict_[key] for key in dict_.keys() if key == 'clearing_protocol' \
									or key == 'antibody1' or key == 'antibody2'}
						notes_for_clearer_this_sample = dict_['notes_for_clearer']
						sample_name = sample_insert_list[index]['sample_name']
						if notes_for_clearer_this_sample != '':
							notes_for_clearer_string = f'{notes_for_clearer_this_sample} (for sample: {sample_name})\n'
						else:
							notes_for_clearer_string = ''
						# check if new_list contains the subdict already
						try: 
							# if it does then find the index of new_list corresponding to this batch
							i = new_list.index(subdict)
						except ValueError: 
							# if it doesn't, then this is a new unique combo of keys
							counts.append(1)
							new_list.append(subdict)
							good_indices.append(index)
							notes_for_clearer_each_batch.append(notes_for_clearer_string)
						else: # only gets executed if try block doesn't generate an error
							counts[i] += 1 
							notes_for_clearer_each_batch[i]+=notes_for_clearer_string

					""" Remake clearing_batch_insert_list to only have unique entries
					and make the ClearingBatchSample() insert list.  """
					clearing_batch_insert_list = [clearing_batch_insert_list[index] for index in good_indices]
					for ii in range(len(clearing_batch_insert_list)):
						insert_dict = clearing_batch_insert_list[ii]
						insert_dict['number_in_batch'] = counts[ii]
						insert_dict['clearing_batch_number'] = ii+1
						insert_dict['notes_for_clearer'] = notes_for_clearer_each_batch[ii]
					
					""" Now loop through all sample insert dicts and assign clearing batch number """
					clearing_batch_sample_insert_list = []
					for sample_insert_dict in sample_insert_list:
						clearing_batch_sample_insert_dict = sample_insert_dict.copy()
						del clearing_batch_sample_insert_dict['subject_fullname']
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
								clearing_batch_sample_insert_dict['clearing_batch_number'] = clearing_batch_number
						clearing_batch_sample_insert_list.append(clearing_batch_sample_insert_dict)
					
					""" Figure out the ImagingBatch() entries
					and ImagingBatchSample() entries.
					An imaging batch is determined by a set of samples
					IN THE SAME CLEARING BATCH
					that need to be imaged at the same resolutions and same 
					imaging channels at those resolutions for a given request. """
				   
					# Loop over existing imaging batch dictionaries  
					new_list = [] # dummy list of imaging dicts ('resolution1':[channel_name1,channel_name2,...],....)
					good_indices = [] # indices of original imaging_batch_insert_list that we will use in the end
					counts = [] # number in each batch, index shared with new_list
					notes_for_clearer_each_batch = [] # concatenated 
					for index,dict_ in enumerate(imaging_batch_insert_list):
						imaging_dict = dict_['imaging_dict']
						sample_name = sample_insert_list[index]['sample_name']
						# Figure out clearing batch number from our ClearingBatchSample() insert dicts
						clearing_batch_number = [d['clearing_batch_number'] for d in clearing_batch_sample_insert_list if d['sample_name'] == sample_name][0]
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
					n_clearing_batches = max([d['clearing_batch_number'] for d in clearing_batch_insert_list])
					for clearing_batch_number in range(1,n_clearing_batches+1):
						# Figure out which samples are in this clearing batch
						samples_this_clearing_batch = [d['sample_name'] for d in clearing_batch_sample_insert_list if d['clearing_batch_number'] == clearing_batch_number]
						# Loop over the unique imaging dicts IN THIS CLEARING BATCH
						# and assign an imaging batch number and figure out how many samples are in each imaging batch
						imaging_dicts_this_clearing_batch = [d for d in new_list if d['clearing_batch_number'] == clearing_batch_number]
						imaging_batch_number = 1
						for imaging_dict in imaging_dicts_this_clearing_batch:
							imaging_batch_insert_dict = {
								'username':username,
								'request_name':form.request_name.data,
								'clearing_batch_number':clearing_batch_number,
								'imaging_request_number':imaging_request_number,
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
								this_sample_imaging_dict = sample_imaging_dict[sample_name]
								if this_sample_imaging_dict == imaging_dict:
									imaging_batch_sample_insert_dict = {
									'username':username,
									'request_name':form.request_name.data,
									'clearing_batch_number':clearing_batch_number,
									'imaging_request_number':imaging_request_number,
									'imaging_batch_number':imaging_batch_number,
									'sample_name':sample_name
									}
									imaging_batch_sample_insert_list.append(imaging_batch_sample_insert_dict)
									n_samples_this_clearing_and_imaging_batch += 1
							imaging_batch_insert_dict['number_in_imaging_batch'] = n_samples_this_clearing_and_imaging_batch
							imaging_batch_number += 1
							imaging_batch_insert_list.append(imaging_batch_insert_dict)

				   
					""" finally, remove clearing and imaging info from Sample() insert dicts.
					Those were just used for constructing the ClearingBatchSample() and
					ImagingBatchSample() insert dicts """
					sample_columns = ['username','request_name','sample_name','subject_fullname']
					sample_insert_list = [{key:dic[key] for key in dic if key in sample_columns} for dic in sample_insert_list ]
					# logger.info("ClearingBatch() insert ")
					# logger.info(clearing_batch_insert_list)
					logger.info("Sample() insert:")
					logger.debug(sample_insert_list)
					db_lightsheet.Request.Sample().insert(sample_insert_list)
					logger.info("ClearingBatch() insert ")
					logger.info(clearing_batch_insert_list)
					db_lightsheet.Request.ClearingBatch().insert(clearing_batch_insert_list,)
					""" For each clearing batch decide if we need to make 
					an insert into the antibody history table.
					This just depends whether antibodies were used """
					for clearing_entry_dict in clearing_batch_insert_list:
						antibody1,antibody2 = clearing_entry_dict['antibody1'],clearing_entry_dict['antibody2']
						if antibody1 or antibody2:
							antibody_history_insert_dict = {}
							antibody_history_insert_dict['username'] = username
							antibody_history_insert_dict['request_name'] = form.request_name.data
							antibody_history_insert_dict['date'] = date
							antibody_history_insert_dict['primary_antibody'] = clearing_entry_dict['antibody1']
							antibody_history_insert_dict['secondary_antibody'] = clearing_entry_dict['antibody2']
							antibody_history_insert_dict['brief_descriptor'] = form.description.data[:128]
							antibody_history_insert_dict['animal_model'] = form.species.data
							antibody_history_insert_dict['primary_concentration'] = ''
							antibody_history_insert_dict['secondary_concentration'] = ''
							antibody_history_insert_dict['primary_order_info'] = ''
							antibody_history_insert_dict['secondary_order_info'] = ''
							antibody_history_insert_dict['notes'] = ''
							logger.info("AntibodyHistory() insert")
							logger.info(antibody_history_insert_dict)
							db_lightsheet.AntibodyHistory().insert1(antibody_history_insert_dict,skip_duplicates=True)

					logger.info("ClearingBatchSample() insert ")
					for d in clearing_batch_sample_insert_list:
						logger.info(d)
					db_lightsheet.Request.ClearingBatchSample().insert(clearing_batch_sample_insert_list,)
					logger.info("ImagingBatch() insert ")
					for d in imaging_batch_insert_list:
						logger.info(d)
					db_lightsheet.Request.ImagingBatch().insert(imaging_batch_insert_list,)
					
					logger.info("ImagingBatchSample() insert ")
					for d in imaging_batch_sample_insert_list:
						logger.info(d)
					db_lightsheet.Request.ImagingBatchSample().insert(imaging_batch_sample_insert_list,)
					
					
					logger.debug("Sample imaging dict:")
					logger.debug(sample_imaging_dict)
					
					logger.info("ImagingRequest() insert:")
					logger.info(imaging_request_insert_list)
					db_lightsheet.Request.ImagingRequest().insert(imaging_request_insert_list)
					logger.info("ProcessingRequest() insert:")
					logger.info(processing_request_insert_list)
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
					


					flash("Request submitted successfully. You will receive an email at "
						  f"{form.correspondence_email.data} with further instructions " 
						  "for handing off your sample, if necessary.","success")
					flash("If you elected to clear or image any of your samples yourself "
						 "then head to Task Management -> All Clearing Tasks in the top Menu Bar "
						 "to start the clearing entry form when ready. "
						 "If not, your tubes will be cleared and imaged by the Core Facility and "
						 "you will receive an email once they are cleared. You can check the "
						 "status of your samples at your request page (see table below).", "success")
					# Email
					subject = 'Lightserv automated email: Request received'
					# with open('/home/lightservuser/.ssh/id_rsa.pub','r') as keyfile: 
					#     keyfile_contents = keyfile.readlines() 
					# ssh_key_text = keyfile_contents[0].strip('\n')
					hosturl = os.environ['HOSTURL']
					# spock_test_link = f'https://{hosturl}' + url_for('main.spock_connection_test')
					pre_handoff_link = f'https://{hosturl}' + url_for('main.pre_handoff')
					message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
						'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
						'Your request:\n'
						f'request_name: "{form.request_name.data}"\n'
						'was successfully submitted.\n\n'
						f'Please see the pre-handoff instructions here: {pre_handoff_link}\n\n'
						'Thanks,\nThe Histology and Brain Registration Core Facility.')
				correspondence_email = form.correspondence_email.data
				recipients = [correspondence_email]
				if not os.environ['FLASK_MODE'] == 'TEST': # pragma: no cover - used to exclude this line from calculating test coverage
					send_email.delay(subject=subject,body=message_body,recipients=recipients) 
					""" If request received and person did not assign themselves as the clearer, then 
					send Laura an email """
					if form.self_clearing.data == False:
						subject = 'Lightserv automated email: New Clearing Request'

						hosturl = os.environ['HOSTURL']
						clearing_manager_link = f'https://{hosturl}' + url_for('clearing.clearing_manager')
						message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
							'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
							'A new request:\n'
							f'username: "{username}"\n'
							f'request_name: "{form.request_name.data}"\n'
							'was received and will need to be cleared.\n\n'
							f'Information about each clearing batch from this request can be viewed at the clearing management page: {clearing_manager_link}\n\n'
							'Thanks,\nThe Histology and Brain Registration Core Facility.')
						recipients = [x + '@princeton.edu' for x in current_app.config['CLEARING_ADMINS']]
						send_email.delay(subject=subject,body=message_body,recipients=recipients) 
					""" If username is not already part of the g_lightsheet_data group,
					send an email to pnihelp requesting that they are added """
					user_in_lightsheet_data_group = check_user_in_g_lightsheet_data(username) # returns None if there is an error connecting to spock
					if user_in_lightsheet_data_group == False:
						logger.debug(f"Username: {username} is not in g_lightsheet_data")
						logger.debug("sending email to pnihelp")
						subject = 'New lightsheet user bucket permissions'
						message_body = ('Hi,\n\nThis is an automated email sent from lightserv, '
							'the web application supporting the the light sheet microscopy facility for the U19 BRAIN CoGS project. '
							'A new user with:\n'
							f'netid: {username}\n'
							'needs to be added to the g_lightsheet_data group on bucket so that they can '
							f'see their data in /jukebox/LightSheetData\n\n'
							'Thanks,\nThe Histology and Brain Registration Core Facility.')
						recipients = ['pnihelp@princeton.edu']
						imaging_admins = current_app.config['IMAGING_ADMINS']
						for imaging_admin_username in imaging_admins:
							recipients.append(imaging_admin_username + '@princeton.edu')
						send_email.delay(subject=subject,body=message_body,recipients=recipients) 
					else:
						logger.debug(f"Username: {username} is already in g_lightsheet_data.")
						logger.debug("No need to send email to pnihelp")
				return redirect(url_for('requests.all_requests'))
			
		else: # post request but not validated. Need to handle some errors

			if 'submit' in form.errors:
				for error_str in form.errors['submit']:
					flash(error_str,'danger')
			
			logger.debug("Not validated! See error dict below:")
			# logger.debug(form.imaging_samples[0].image_resolution_forms[0].atlas_name.data)
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

	if request.method=='GET':
		logger.info("GET request")

		if not form.correspondence_email.data:  
			form.correspondence_email.data = current_user + '@princeton.edu'
		""" Convenience auto-fills for DEV mode """
		if os.environ['FLASK_MODE'] == 'DEV': 
			if not form.labname.data:
				form.labname.data = 'braincogs'
			if not form.request_name.data:
				form.request_name.data = 'test'
			if not form.description.data:
				form.description.data = 'test'
		# form.subject_fullname.choices = [('test','test')] 

	if 'column_name' not in locals():
		column_name = ''
	
	clearing_admins = current_app.config['CLEARING_ADMINS']
	return render_template('requests/new_request.html', title='new_request',
		form=form,legend='New Request',column_name=column_name,
		clearing_admins=clearing_admins) 

@requests.route("/delete_request/<username>/<request_name>",)
@logged_in
@logged_in_as_request_owner
@clearing_not_yet_started
@log_http_requests
@request_exists
def delete_request(username,request_name):
	""" A route for deleting a request """
	logger.debug(f"{username} accessed delete_request")
	request_contents = db_lightsheet.Request() & f'request_name="{request_name}"' & \
			f'username="{username}"'
	""" Figure out if clearer was not yet assigned for any of the clearing 
	batches associated with this request. In that case, 
	Laura needs to know that these clearing batches will disappear from the clearing GUI """
	email_laura = False
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'request_name="{request_name}"' & \
			f'username="{username}"'
	for clearing_dict in clearing_batch_contents:
		clearer = clearing_dict['clearer']
		if not clearer:
			email_laura = True
			break
	
	""" temporarily turn safemode off so that there is no yes/no prompt upon delete() """
	dj.config['safemode'] = False
	request_contents.delete()
	""" Reset to whatever mode it was before the switch """
	dj.config['safemode'] = current_app.config['DJ_SAFEMODE']
	if not os.environ['FLASK_MODE'] == 'TEST': # pragma: no cover - used to exclude this line from calculating test coverage
		if email_laura:
			subject = 'Lightserv automated email: Clearing Request Deleted'
			hosturl = os.environ['HOSTURL']
			clearing_manager_link = f'https://{hosturl}' + url_for('clearing.clearing_manager')
			message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
				'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
				'A request:\n'
				f'username: "{username}"\n'
				f'request_name: "{request_name}"\n'
				'was deleted and no longer needs to be cleared. '
				'The clearing request(s) associated with this request '
				f'were removed from the clearing management page: {clearing_manager_link}\n\n'
				'Thanks,\nThe Histology and Brain Registration Core Facility.')
			recipients = [x + '@princeton.edu' for x in current_app.config['CLEARING_ADMINS']]
			send_email.delay(subject=subject,body=message_body,recipients=recipients) 
	flash('Your request has been deleted','success')
	return redirect(url_for('requests.all_requests'))
