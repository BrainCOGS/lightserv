from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)
# from flask_login import current_user, login_required
# from lightserv import db_lightsheet
# from lightserv.models import Experiment
from lightserv.requests.forms import NewRequestForm, UpdateNotesForm
from lightserv.requests.tables import (ExpTable, create_dynamic_samples_table)
from lightserv import db_lightsheet
from lightserv.main.utils import (logged_in, table_sorter,logged_in_as_processor,
	check_clearing_completed,check_imaging_completed)
from lightserv import cel,mail
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

@requests.route("/request/new",methods=['GET','POST'])
@logged_in
def new_request():
	""" Route for a user to enter a new request via a form """
	all_imaging_modes = current_app.config['IMAGING_MODES']

	current_user = session['user']
	logger.info(f"{current_user} accessed new request form")
	username = current_user

	form = NewRequestForm(request.form)
	logger.info(form.data)
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
						
						column_name = f'imaging_samples-{ii}-image_resolution_forms-{resolution_table_index}-channels-0-registration'
						# Now make 4 new channel formfields and set defaults and channel names
						for x in range(4):
							# image_resolution_form.channels.append_entry()
							channel_name = current_app.config['IMAGING_CHANNELS'][x]
							image_resolution_form.channels[x].channel_name.data = channel_name
							# Make the default for channel 488 to be 1.3x imaging with registration checked
							if channel_name == '488' and image_resolution_forsetup == "1.3x":
								image_resolution_form.channels[x].registration.data = 1
				
			""" Handle "setup samples" button pressed """
			if submit_key == 'sample_submit_button': # The sample setup button
				logger.info("sample submit")
				nsamples = form.number_of_samples.data
				logger.info(form.uniform_clearing.data)
				logger.info(type(form.uniform_clearing.data))
				if form.uniform_clearing.data == True: # UNIFORM clearing
					logger.info("Clearing is uniform")
					while len(form.clearing_samples.data) > 0:
						form.clearing_samples.pop_entry()
					# Just make one set of sample fields
					form.clearing_samples.append_entry()
					form.clearing_samples[0].sample_name.data = form.sample_prefix.data + '-001'

				else: # CUSTOM clearing
					logger.info("Clearing is custom")
					while len(form.clearing_samples.data) > 0:
						form.clearing_samples.pop_entry()
					# make nsamples sets of sample fields
					for ii in range(nsamples):
						form.clearing_samples.append_entry()
						form.clearing_samples[ii].sample_name.data = form.sample_prefix.data + '-' + f'{ii+1}'.zfill(3)

				if form.uniform_imaging.data == True: # UNIFORM imaging
					logger.info("imaging is uniform")
					while len(form.imaging_samples.data) > 0:
						form.imaging_samples.pop_entry()
					# Just make one set of sample fields
					form.imaging_samples.append_entry()
					form.imaging_samples[0].sample_name.data = form.sample_prefix.data + '-001'
				else: # CUSTOM imaging
					logger.info("imaging is custom")
					while len(form.imaging_samples.data) > 0:
						form.imaging_samples.pop_entry()
					# make nsamples sets of sample fields
					for ii in range(nsamples):
						form.imaging_samples.append_entry()
						form.imaging_samples[ii].sample_name.data = form.sample_prefix.data + '-' + f'{ii+1}'.zfill(3)
				
				column_name = 'clearing_samples-0-clearing_protocol'

			elif submit_key == 'submit': # The final submit button
				logger.debug("Final submission")
				''' Create a new entry in the Experiment table based on form input.
				'''

				""" Start a transaction for doing the inserts.
					This is done to avoid inserting only into Experiment
					table but not Sample and ImagingChannel tables if there is an error 
					at any point during any of the inserts"""
				connection = db_lightsheet.Request.connection
				with connection.transaction:
					princeton_email = username + '@princeton.edu'
					user_insert_dict = dict(username=username,princeton_email=princeton_email)
					db_lightsheet.User().insert1(user_insert_dict,skip_duplicates=True)
					request_insert_dict = dict(request_name=form.request_name.data,
						username=username,labname=form.labname.data.lower(),
						correspondence_email=form.correspondence_email.data.lower(),
						description=form.description.data,species=form.species.data,
						number_of_samples=form.number_of_samples.data,
						sample_prefix=form.sample_prefix.data,uniform_clearing=form.uniform_clearing.data)
					now = datetime.now()
					date = now.strftime("%Y-%m-%d")
					time = now.strftime("%H:%M:%S") 
					request_insert_dict['date_submitted'] = date
					request_insert_dict['time_submitted'] = time
					db_lightsheet.Request().insert1(request_insert_dict)
				
					''' Now loop through samples and get clearing and imaging parameters for each sample '''
					clearing_samples = form.clearing_samples.data
					imaging_samples = form.imaging_samples.data
					number_of_samples = form.number_of_samples.data
					''' First need to figure out if clearing and imaging 
					were custom or uniform for each sample '''
					if len(clearing_samples) == number_of_samples:
						uniform_clearing = False
					else:
						uniform_clearing = True

					if len(imaging_samples) == number_of_samples:
						uniform_imaging = False
					else:
						uniform_imaging = True

					for ii in range(number_of_samples):
						sample_name = form.sample_prefix.data + '-' + f'{ii+1}'.zfill(3)
						logger.info(sample_name)
						sample_insert_dict = {}
						""" Set up sample insert dict """
						''' Add primary keys that are not in the form '''
						sample_insert_dict['request_name'] = form.request_name.data
						sample_insert_dict['username'] = username 
						sample_insert_dict['sample_name'] = sample_name
						sample_insert_dict['clearing_progress'] = 'incomplete'

						if form.self_clearing.data:
							sample_insert_dict['clearer'] = username
						if uniform_clearing == True:
							clearing_sample_dict = clearing_samples[0]
						else:
							clearing_sample_dict = clearing_samples[ii]

						if uniform_imaging == True:
							imaging_sample_dict = imaging_samples[0]
						else:
							imaging_sample_dict = imaging_samples[ii]

						""" update insert dict with clearing form data """
						for key,val in clearing_sample_dict.items(): 
							if val != None and val !='None' and key not in ['csrf_token','sample_name']:
								sample_insert_dict[key] = val


						""" Set up ImagingRequest insert dict """

						""" When user submits this request form it is always 
						the first imaging request for this sample """
						imaging_request_number = 1
						imaging_request_insert_dict = {}
						imaging_request_insert_dict['request_name'] = form.request_name.data
						imaging_request_insert_dict['username'] = username 
						imaging_request_insert_dict['sample_name'] = sample_name
						imaging_request_insert_dict['imaging_request_number'] = imaging_request_number
						if form.self_imaging.data:
							imaging_request_insert_dict['imager'] = username
						imaging_request_insert_dict['imaging_request_date_submitted'] = date
						imaging_request_insert_dict['imaging_request_time_submitted'] = time
						imaging_request_insert_dict['imaging_progress'] = "incomplete"

						""" Now insert each image resolution/channel combo """
						resolution_insert_list = []
						channel_insert_list = []

						for resolution_dict in imaging_sample_dict['image_resolution_forms']:
							logger.info(resolution_dict)
							resolution_insert_dict = {}
							resolution_insert_dict['request_name'] = form.request_name.data
							resolution_insert_dict['username'] = username 
							resolution_insert_dict['sample_name'] = sample_name
							resolution_insert_dict['imaging_request_number'] = imaging_request_number
							resolution_insert_dict['image_resolution'] = resolution_dict['image_resolution']
							resolution_insert_dict['notes_for_imager'] = resolution_dict['notes_for_imager']
							resolution_insert_dict['notes_for_processor'] = resolution_dict['notes_for_processor']
							resolution_insert_dict['notes_for_processor'] = resolution_dict['notes_for_processor']
							resolution_insert_dict['atlas_name'] = resolution_dict['atlas_name']
							resolution_insert_list.append(resolution_insert_dict)

							for imaging_channel_dict in resolution_dict['channels']:
								
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
									for key,val in imaging_channel_dict.items(): 
										if key == 'csrf_token':
											continue
										channel_insert_dict[key] = val

									channel_insert_list.append(channel_insert_dict)
							logger.info(channel_insert_list)
								
						
						logger.info("Sample() insert:")
						logger.info(sample_insert_dict)
						db_lightsheet.Sample().insert1(sample_insert_dict)
						logger.info("ImagingRequest() insert:")
						logger.info(imaging_request_insert_dict)
						db_lightsheet.Sample.ImagingRequest().insert1(imaging_request_insert_dict)
						logger.info("ImageResolutionRequest() insert:")
						logger.info(resolution_insert_list)
						db_lightsheet.Sample.ImageResolutionRequest().insert(resolution_insert_list)
						logger.info('channel insert:')
						logger.info(channel_insert_list)
						db_lightsheet.Sample.ImagingChannel().insert(channel_insert_list)
						
					flash("Request submitted successfully.", "success")
					return redirect(url_for('main.home'))
			
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
					if isinstance(obj,dict):
						for key,val in list(obj.items()):
							for error_str in val:
								flash(error_str,'danger')
					elif isinstance(obj,str):
						flash(obj,'danger')
			if 'number_of_samples' in form.errors:
				for error_str in form.errors['number_of_samples']:
					flash(error_str,'danger')
	""" Make default checkboxes -- can't be done in forms.py unfortunately: https://github.com/lepture/flask-wtf/issues/362 """
	if request.method=='GET':
		logger.info("Get request")
		form.uniform_clearing.data = True
		form.uniform_imaging.data = True
		if not form.correspondence_email.data:	
			form.correspondence_email.data = username + '@princeton.edu' 
	if 'column_name' not in locals():
		column_name = ''
	

	return render_template('requests/new_request.html', title='new_request',
		form=form,legend='New Request',column_name=column_name)	

@requests.route("/request/<username>/<request_name>",)
@logged_in
def request_overview(username,request_name):
	""" A route for displaying a single request. Also acts as a gateway to start data processing. """
	
	request_contents = db_lightsheet.Request() & f'request_name="{request_name}"' & \
	 		f'username="{username}"'
	samples_contents = db_lightsheet.Sample() & f'request_name="{request_name}"' & f'username="{username}"' 
	''' Get rid of the rows where none of the channels are used '''
	channel_contents = db_lightsheet.Sample.ImagingChannel() & f'request_name="{request_name}"' & f'username="{username}"' 
	# The first time page is loaded, sort, reverse, table_id are all not set so they become their default
	sort = request.args.get('sort', 'request_name') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	table_id = request.args.get('table_id', '')

	combined_contents = (dj.U('request_name','sample_name').aggr(
    channel_contents) * samples_contents)
	request_table_id = 'horizontal_request_table'
	samples_table_id = 'vertical_samples_table'

	if table_id == request_table_id: # the click to sort a column was in the experiment table
		sorted_results = sorted(request_contents.fetch(as_dict=True),
			key=partial(table_sorter,sort_key=sort),reverse=reverse) # partial allows you to pass in a parameter to the function

		request_table = ExpTable(sorted_results,sort_by=sort,
						  sort_reverse=reverse)
		samples_table = create_dynamic_samples_table(combined_contents,table_id=samples_table_id)
	elif table_id == samples_table_id: # the click was in the samples table
		samples_table = create_dynamic_samples_table(combined_contents,
			sort_by=sort,sort_reverse=reverse,table_id=samples_table_id)
		request_table = ExpTable(request_contents)
	else:
		samples_table = create_dynamic_samples_table(combined_contents,
			table_id=samples_table_id)
		request_table = ExpTable(request_contents)

	samples_table.table_id = samples_table_id
	request_table.table_id = request_table_id
	return render_template('requests/request.html',request_contents=request_contents,
		request_table=request_table,samples_table=samples_table)



