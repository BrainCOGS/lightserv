from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup)
# from flask_login import current_user, login_required
# from lightserv import db_lightsheet
# from lightserv.models import Experiment
from lightserv.experiments.forms import ExpForm, UpdateNotesForm, StartProcessingForm
from lightserv.tables import ExpTable
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
	logger.info(f"{session['user']} accessed new experiment form")

	form = ExpForm(request.form)

	form.correspondence_email.data = session['user'] + '@princeton.edu' 
	if request.method == 'POST':
		if form.validate_on_submit():
			submit_keys = [x for x in form._fields.keys() if 'submit' in x and form[x].data]
			logger.debug(submit_keys)
			submit_key = submit_keys[0]
			
			if submit_key == 'custom_clearing_submit':
				logger.debug("Clearing is custom")
				form.custom_clearing.data = True
				nsamples = form.number_of_samples.data
				# First pop off any existing sample fields 
				while len(form.samples) > 0:
					form.samples.pop_entry()
				# make nsamples sets of sample fields
				for ii in range(nsamples):
					form.samples.append_entry()
				return render_template('experiments/new_exp.html', title='new_experiment',
			form=form,legend='New Experiment',column_name="samples-0-clearing_protocol")	

			elif submit_key == 'uniform_clearing_submit':
				logger.debug("Clearing is uniform")
				form.custom_clearing.data = False
				nsamples = form.number_of_samples.data
				# First pop off any existing sample fields
				while len(form.samples) > 0:
					form.samples.pop_entry()
				# Just make one set of sample fields
				form.samples.append_entry()
				return render_template('experiments/new_exp.html', title='new_experiment',
			form=form,legend='New Experiment',column_name="samples-0-clearing_protocol")

			elif submit_key == 'custom_imaging_submit':
				logger.debug("Imaging is custom")
				form.custom_imaging.data = True
				nsamples = form.number_of_samples.data
				# First pop off any existing imaging fields 
				while len(form.imaging) > 0:
					form.imaging.pop_entry()
				# make nsamples sets of imaging fields
				for ii in range(nsamples):
					form.imaging.append_entry()
				return render_template('experiments/new_exp.html', title='new_experiment',
			form=form,legend='New Experiment',column_name="imaging-0-image_resolution")	

			elif submit_key == 'uniform_imaging_submit':
				logger.debug("Imaging is uniform")
				form.custom_imaging.data = False
				nsamples = form.number_of_samples.data
				# First pop off any existing sample fields
				while len(form.imaging) > 0:
					form.imaging.pop_entry()
				# Just make one set of sample fields
				form.imaging.append_entry()
				return render_template('experiments/new_exp.html', title='new_experiment',
			form=form,legend='New Experiment',column_name="imaging-0-image_resolution")	

			elif submit_key == 'submit': # The final submit button

				''' Create a new entry in the Experiment table based on form input.
				'''
				logger.debug("Final submission")
				# username = session['user']
				# ''' The fields that need to go in the database that are not in the form '''
				# exp_dict = dict(labname=form.labname.data.lower(),
				# 	correspondence_email=form.correspondence_email.data.lower(),
				# 	title=form.title.data,description=form.description.data,species=form.species.data,
				# 	perfusion_date=form.perfusion_date.data,expected_handoff_date=form.expected_handoff_date.data,
				# 	clearing_protocol=form.clearing_protocol.data,antibody1=form.antibody1.data,
				# 	antibody2=form.antibody2.data,channel488=form.channel488.data,
				# 	channel555=form.channel555.data,channel647=form.channel647.data,
				# 	channel790=form.channel790.data,image_resolution=form.image_resolution.data,
				# 	username=username)
				# if form.self_clearing.data == True: # otherwise keep as NULL
				# 	clearer = username
				# 	exp_dict['clearer'] = clearer
				# all_usernames = db_lightsheet.User().fetch('username') 
				# if username not in all_usernames:
				# 	princeton_email = username + '@princeton.edu'
				# 	user_dict = {'username':username,'princeton_email':princeton_email}
				# 	db_lightsheet.User().insert1(user_dict)

				# db_lightsheet.Experiment().insert1(exp_dict)
				# exp_id = db_lightsheet.Experiment().fetch("KEY")[-1]['experiment_id'] # gets the most recently added key
				# flash(Markup(f'Your experiment has started!\n \
				# 	Check your new experiment page: <a href="{url_for("experiments.exp",experiment_id=exp_id)}" \
				# 	class="alert-link" target="_blank">here</a> for your data when it becomes available.'),'success')
				# return redirect(url_for('main.home'))
		else:

			if 'samples' in form.errors:
				for error_str in form.errors['samples']:
					flash(error_str,'danger')
			# 	error_str = '<br/>'.join(x for x in form.errors['samples']).html_safe
			# flash[:error] = errors.join("\n") 
			# flash('There were errors: <br/> abc','danger')
			logger.debug("Not validated!")
			logger.debug(form.errors)
			# logger.debug(form.samples.data)
	return render_template('experiments/new_exp.html', title='new_experiment',
		form=form,legend='New Experiment')	

@experiments.route("/exp/<int:experiment_id>/delete", methods=['POST'])
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

@experiments.route("/exp/<int:experiment_id>",)
@logged_in
def exp(experiment_id):
	""" A route for displaying a single experiment. Also acts as a gateway to start data processing. """
	exp_contents = db_lightsheet.Experiment() & f'experiment_id="{experiment_id}"'
	exp_table = ExpTable(exp_contents)

	try:
		if exp_contents.fetch1('username') != session['user'] and session['user'] != 'ahoag':
			flash('You do not have permission to see dataset: {}'.format(experiment_id),'danger')
			return redirect(url_for('main.home'))
	except:
		flash(f'Page does not exist for Dataset: "{experiment_id}"','danger')
		return redirect(url_for('main.home'))
	return render_template('experiments/exp.html',exp_contents=exp_contents,exp_table=exp_table)

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

@experiments.route("/exp/<int:experiment_id>/rawdata_link",)
@logged_in
def exp_rawdata(experiment_id):
	""" An incomplete route for making a neuroglancer link to view the raw data from an experiment """
	try: 
		vol = cloudvolume.CloudVolume('file:///home/ahoag/ngdemo/demo_bucket/demo_dataset/190715_an31_devcno_03082019_1d3x_488_017na_1hfds_z10um_100msec_16-55-48/')
		# vol = cloudvolume.CloudVolume('file:///home/ahoag/ngdemo/demo_bucket/demo_dataset/demo_layer_singletif/')
		image_data = np.transpose(vol[:][...,0],(2,1,0)) # can take a few seconds
		viewer = neuroglancer.Viewer()
		# This volume handle can be used to notify the viewer that the data has changed.
		volume = neuroglancer.LocalVolume(
				 data=image_data, # need it in z,y,x order, strangely
				 voxel_size=[40000,40000,40000],
				 voxel_offset = [0, 0, 1], # x,y,z in nm not voxels
				 volume_type='image'
				 )
		with viewer.txn() as s:
			s.layers['image'] = neuroglancer.ImageLayer(source=volume,
			shader = '''
void main() {
float v = toNormalized(getDataValue(0)) * 20.0;
emitRGBA(vec4(v, 0.0, 0.0, v));
		}
		''')
	
	except:
		flash('Something went wrong making viewer','danger')
		return redirect(url_for('experiments.exp',experiment_id=experiment_id))
	return render_template('experiments/datalink.html',viewer=viewer)

@experiments.route("/exp/start_processing/<experiment_id>",methods=['GET','POST'])
@logged_in
def start_processing(experiment_id):
	""" Route for a user to enter a new experiment via a form and submit that experiment """
	logger.info(f"{session['user']} accessed start_processing route")
	exp_contents = db_lightsheet.Experiment() & f'experiment_id={experiment_id}'
	assert len(exp_contents) == 1
	channels = [488,555,647,790]
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