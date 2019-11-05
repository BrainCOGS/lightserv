from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup)
# from flask_login import current_user, login_required
# from lightserv import db_lightsheet
# from lightserv.models import Experiment
from lightserv.experiments.forms import ExpForm, UpdateNotesForm, StartProcessingForm
from lightserv.tables import ExpTable, SamplesTable
from lightserv import db_lightsheet
from lightserv.main.utils import logged_in
from lightserv import cel

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

experiments = Blueprint('experiments',__name__)

@experiments.route("/exp/new",methods=['GET','POST'])
@logged_in
def new_exp():
	""" Route for a user to enter a new experiment via a form and submit that experiment """
	username = session['user']
	logger.info(f"{username} accessed new experiment form")

	form = ExpForm(request.form)
	
	if request.method == 'POST':
		if form.validate_on_submit():
			submit_keys = [x for x in form._fields.keys() if 'submit' in x and form[x].data]
			logger.debug(submit_keys)
			submit_key = submit_keys[0]
			
			""" Handle multiple clearing/imaging yes/no button pressed """
			if submit_key == 'sample_submit_button': # The sample setup button
				nsamples = form.number_of_samples.data
				if form.uniform_clearing.data == True: # UNIFORM clearing
					logger.info("Clearing is uniform")
					while len(form.clearing_samples.data) > 0:
						form.clearing_samples.pop_entry()
					# Just make one set of sample fields
					form.clearing_samples.append_entry()
				else: # CUSTOM clearing
					logger.info("Clearing is custom")
					while len(form.clearing_samples.data) > 0:
						form.clearing_samples.pop_entry()
					# make nsamples sets of sample fields
					for ii in range(nsamples):
						form.clearing_samples.append_entry()

				if form.uniform_imaging.data == True: # UNIFORM imaging
					logger.info("imaging is uniform")
					while len(form.imaging_samples.data) > 0:
						form.imaging_samples.pop_entry()
					# Just make one set of sample fields
					form.imaging_samples.append_entry()
				else: # CUSTOM imaging
					logger.info("imaging is custom")
					while len(form.imaging_samples.data) > 0:
						form.imaging_samples.pop_entry()
					# make nsamples sets of sample fields
					for ii in range(nsamples):
						form.imaging_samples.append_entry()
				column_name = 'clearing_samples-0-clearing_protocol'

			elif submit_key == 'submit': # The final submit button
				logger.debug("Final submission")
				''' Create a new entry in the Experiment table based on form input.
				'''
				username = session['user']

				""" Start a transaction for doing the inserts.
					This is done to avoid inserting only into Experiment
					table but not Sample table if there is an error """
				connection = db_lightsheet.Experiment.connection
				with connection.transaction:
					exp_insert_dict = dict(experiment_name=form.experiment_name.data,
						username=username,labname=form.labname.data.lower(),
						correspondence_email=form.correspondence_email.data.lower(),
						description=form.description.data,species=form.species.data,
						number_of_samples=form.number_of_samples.data,
						sample_prefix=form.sample_prefix.data)
					now = datetime.now()
					date = now.strftime("%Y-%m-%d")
					time = now.strftime("%H:%M:%S") 
					exp_insert_dict['date_submitted'] = date
					exp_insert_dict['time_submitted'] = time
					db_lightsheet.Experiment().insert1(exp_insert_dict)
					''' Figure out the experiment_id so we can use it for the samples table insert '''

					experiment_id = db_lightsheet.Experiment()
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
						sample_insert_dict = {}
						if uniform_clearing == True:
							clearing_sample_dict = clearing_samples[0]
						else:
							clearing_sample_dict = clearing_samples[ii]

						if uniform_imaging == True:
							imaging_sample_dict = imaging_samples[0]
						else:
							imaging_sample_dict = imaging_samples[ii]

						for key,val in clearing_sample_dict.items(): 
							if val != None and key != 'csrf_token':
								sample_insert_dict[key] = val
						for key,val in imaging_sample_dict.items():
							if val != None and key != 'csrf_token':
								sample_insert_dict[key] = val
						sample_name = form.sample_prefix.data + '-' + '%i' % (ii+1)
						''' Add depedent primary keys '''
						sample_insert_dict['experiment_name'] = form.experiment_name.data
						sample_insert_dict['username'] = username 

						sample_insert_dict['sample_name'] = sample_name
						sample_insert_dict['clearing_progress'] = 'incomplete'

						if form.self_clearing.data:
							sample_insert_dict['clearer'] = username
						if form.self_imaging.data:
							sample_insert_dict['imager'] = username
						
						db_lightsheet.Experiment.Sample.insert1(sample_insert_dict)
						logger.info("new insert")
						logger.info(sample_insert_dict)
						logger.info('')
					return redirect(url_for('main.home'))
			
		else: # post request but not validated

			if 'clearing_samples' in form.errors:
				for error_str in form.errors['clearing_samples']:
					flash(error_str,'danger')
			if 'imaging_samples' in form.errors:
				for error_str in form.errors['imaging_samples']:
					flash(error_str,'danger')
			
			logger.debug("Not validated!")
			logger.debug(form.errors)
			# logger.debug(form.samples.data)
	if not form.correspondence_email.data:	
		form.correspondence_email.data = session['user'] + '@princeton.edu' 
	if 'column_name' not in locals():
		column_name = ''
	return render_template('experiments/new_exp.html', title='new_experiment',
		form=form,legend='New Experiment',column_name=column_name)	

@experiments.route("/exp/<username>/<experiment_name>/delete", methods=['POST'])
@logged_in
def delete_exp(experiment_id):
	""" A route which will delete an experiment from the database """
	exp_contents = db_lightsheet.Experiment() & f'experiment_id="{experiment_id}"'

	if exp_contents.fetch1('username') != session['user']:
		abort(403)
	try:
		exp_contents.delete_quick() # does not query user for confirmation like delete() does - that is handled in the form.
	except pymysql.err.IntegrityError:
		flash('You cannot delete an experiment without deleting its dependencies (e.g. clearing entries). \
			Delete all dependencies first.','danger')
		return redirect(url_for('main.home'))

	flash('Your experiment has been deleted!', 'success')
	return redirect(url_for('main.home'))

@experiments.route("/exp/<username>/<experiment_name>",)
@logged_in
def exp(username,experiment_name):
	""" A route for displaying a single experiment. Also acts as a gateway to start data processing. """
	exp_contents = db_lightsheet.Experiment() & \
	 f'experiment_name="{experiment_name}"' & f'username="{username}"'
	exp_table = ExpTable(exp_contents)
	exp_table.table_id = 'horizontal' # to override vertical layout
	samples_contents = db_lightsheet.Experiment.Sample() & f'experiment_name="{experiment_name}"' & f'username="{username}"' 
	samples_table = SamplesTable(samples_contents)
	samples_table.table_id = 'vertical'
	try:
		if exp_contents.fetch1('username') != session['user'] and session['user'] != 'ahoag':
			flash('You do not have permission to see dataset: {}'.format(experiment_id),'danger')
			return redirect(url_for('main.home'))
	except:
		flash(f'Page does not exist for Dataset: "{experiment_id}"','danger')
		return redirect(url_for('main.home'))
	return render_template('experiments/exp.html',exp_contents=exp_contents,exp_table=exp_table,samples_table=samples_table)

@experiments.route("/exp/<int:experiment_id>/notes", methods=['GET','POST'])
@logged_in
def update_notes(experiment_id):
	""" A route for updating notes in a single experiment """
	if 'user' not in session:
		return redirect('users.login')
	form = UpdateNotesForm()
	exp_contents = db_lightsheet.Experiment() & f'experiment_id="{experiment_id}"'
	exp_table = ExpTable(exp_contents)

	if form.validate_on_submit():
		''' Enter the entered notes into this experiment's notes column'''
		''' To update entry, need to first delete the entry and then add it 
		again with the additional data '''

		update_insert_dict = exp_contents.fetch1()
		update_insert_dict['notes']=form.notes.data
		exp_contents.delete_quick()

		db_lightsheet.Experiment().insert1(update_insert_dict)
		flash(f"Your notes have been updated",'success')
		return redirect(url_for('experiments.exp',experiment_id=experiment_id))
	elif request.method == 'GET':
		current_notes = exp_contents.fetch1('notes')
		form.notes.data = current_notes
	return render_template('experiments/update_notes.html',form=form,exp_table=exp_table)

@experiments.route("/exp/<username>/<experiment_name>/start_processing",methods=['GET','POST'])
@logged_in
def start_processing(username,experiment_name):
	""" Route for a user to enter a new experiment via a form and submit that experiment """
	logger.info(f"{session['user']} accessed start_processing route")
	exp_contents = (db_lightsheet.Experiment() &\
	 f'username="{username}"' & f'experiment_name="{experiment_name}"')
	logger.info(exp_contents)

	# print(exp_contents)
	# assert len(exp_contents) == 1
	# channels = [488,555,647,790]
	channel_query_strs = ['channel%i' % channel for channel in channels]

	channels = ['registration','injection_detection','probe_detection','cell_detection']
	channel_response_dict = exp_contents.fetch(*channel_query_strs,as_dict=True)[0]
	used_imaging_channels = [channel for channel in channel_response_dict.keys() if channel_response_dict[channel]]
	if len(used_imaging_channels) == 0:
		flash("This experiment has no images so no data processing can be done",'danger')
		return redirect(url_for('experiments.exp',experiment_id=experiment_id))

	exp_table = ExpTable(exp_contents)
	form = StartProcessingForm()
	if request.method == 'POST':
		logger.debug("POST request")
		if form.validate_on_submit():
			logger.debug("Validated")
			''' Make the parameter dictionary from form input.'''
			form_fields = [x for x in form._fields.keys() if 'submit' not in x and 'csrf_token' not in x]
			processing_params_dict = {field:form[field].data for field in form_fields}
			logger.debug(processing_params_dict)
			logger.debug("Successfully captured form input into processing parameter dictionary")
			logger.info(f"Sending processes to Celery")
			run_step0.delay(experiment_id=experiment_id,processing_params_dict=processing_params_dict)
			flash('Your data processing has begun. You will receive an email \
				when the first steps are completed.','success')
			return redirect(url_for('main.home'))
		else:
			logger.debug("Not validated!")
			logger.debug(form.errors)
			flash("There were errors in the form. Check form for details.",'danger')
	return render_template('experiments/start_processing.html',
		form=form,exp_table=exp_table,used_imaging_channels=used_imaging_channels)	

@cel.task()
def run_step0(experiment_id,processing_params_dict):
	""" An asynchronous celery task (runs in a background process) which runs step 0 
	in the light sheet pipeline. 
	"""
	import tifffile
	from xml.etree import ElementTree as ET 
	exp_contents = db_lightsheet.Experiment & f'experiment_id={experiment_id}'
	username = exp_contents.fetch1('username')
	''' Now add to parameter dictionary the other needed info to run the code '''
	username = exp_contents.fetch('username')
	raw_path = f'/jukebox/LightSheetData/lightserv_test/{username}/exp_{experiment_id}'  
	''' Make the "inputdictionary", i.e. the mapping between directory and function '''
	processing_params_dict['inputdictionary'] = {}
	input_dictionary = {}

	# Create a counter for multi-channel imaging. If multi-channel imaging was used
	# this counter will be incremented each time a raw data directory is repeated
	# so that each channel gets assigned the right number, e.g. [['regch','00'],['cellch','01']] 
	multichannel_counter_dict = {} 
	for channel in rawdata_dir_dict.keys():
		rawdata_dir = rawdata_dir_dict[channel]

		# First figure out the counter 
		if rawdata_dir in multichannel_counter_dict.keys():
			multichannel_counter_dict[rawdata_dir] += 1
		else:
			multichannel_counter_dict[rawdata_dir] = 0
		multichannel_counter = multichannel_counter_dict[rawdata_dir]
		# Now figure out the channel type
		channel_mode = exp_contents.fetch1(channel)
		if channel_mode == 'registration':
			mode_abbr = 'regch'
		elif channel_mode == 'cell_detection':
			mode_abbr = 'cellch'
		elif channel_mode == 'injection_detection':
			mode_abbr = 'injch'
		elif channel_mode == 'probe_detection':
			mode_abbr = 'injch'
		else:
			abort(403)

		input_list = [mode_abbr,f'{multichannel_counter:02}']
		if multichannel_counter > 0:		
			input_dictionary[rawdata_dir].append(input_list)
		else:
			input_dictionary[rawdata_dir] = [input_list]
	# Output directory for processed files
	output_directory = f'/jukebox/LightSheetData/{username}/experiment_{experiment_id}'
	
	# Figure out xyz scale from metadata of 0th z plane of last rawdata directory (is the same for all directories)
	# Grab the metadata tags from the 0th z plane
	z0_plane = glob.glob(rawdata_dir + '/*RawDataStack*Z0000*.tif')[0]

	with tifffile.TiffFile(z0_plane) as tif:
		tags = tif.pages[0].tags
	xml_description=tags['ImageDescription'].value
	root = ET.fromstring(xml_description)
	# The pixel size is in the PhysicalSizeX, PhysicalSizeY, PhysicalSizeZ attributes, which are in the "Pixels" tag
	image_tag = root[2]
	pixel_tag = image_tag[2]
	pixel_dict = pixel_tag.attrib
	dx,dy,dz = pixel_dict['PhysicalSizeX'],pixel_dict['PhysicalSizeY'],pixel_dict['PhysicalSizeZ']
	xyz_scale = (dx,dy,dz)
	
	param_dict['systemdirectory'] = '/jukebox/'
	param_dict['inputdictionary'] = input_dictionary
	param_dict['output_directory'] = output_directory
	param_dict['xyz_scale'] = xyz_scale
	logger.info("### PARAM DICT ###")
	logger.info(param_dict)
	logger.info('#######')
	# for channel in rawdata_dict.keys():
	# 	rawdata_directory = rawdata_dict
	# param_dict['inputdictionary'] = {rawdata_directory:[]}
	return "success"