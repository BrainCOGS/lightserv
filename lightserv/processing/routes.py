from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)
from lightserv.processing.forms import StartProcessingForm
from lightserv.tables import create_dynamic_channels_table_for_processing
from lightserv import db_lightsheet
from lightserv.main.utils import (logged_in, table_sorter,logged_in_as_processor,
	check_clearing_completed,check_imaging_completed)
from lightserv import cel,mail
import datajoint as dj

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/processing_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

# neuroglancer.set_static_content_source(url='https://neuromancer-seung-import.appspot.com')

processing = Blueprint('processing',__name__)

@processing.route("/processing/<username>/<experiment_name>/<sample_name>/start_processing",
	methods=['GET','POST'])
@logged_in
@check_clearing_completed
@check_imaging_completed
@logged_in_as_processor
def start_processing(username,experiment_name,sample_name):
	""" Route for the person assigned as data processor for a sample 
	to start the data processing. """
	logger.info(f"{session['user']} accessed start_processing route")
	
	sample_contents = (db_lightsheet.Sample() & f'experiment_name="{experiment_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"')
	sample_dict = sample_contents.fetch1()
	channel_contents = (db_lightsheet.Sample.ImagingChannel() & f'experiment_name="{experiment_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"') # all of the channels for this sample
	channel_content_dict_list = channel_contents.fetch(as_dict=True)

	joined_contents = sample_contents * channel_contents
	sample_table_id = 'horizontal_procsesing_table'
	sample_table = create_dynamic_channels_table_for_processing(joined_contents,table_id=sample_table_id)
	sample_table.table_id = sample_table_id

	form = StartProcessingForm()
	
	processing_progress = sample_contents.fetch1('processing_progress')

	if processing_progress == 'complete':
		logger.info("processing already complete but accessing the processing entry page anyway")
		flash("processing is already complete for this sample. "
				"This page is read only and hitting submit will do nothing",'warning')

	if request.method == 'POST': # post request
		logger.info('post request')
		if form.validate_on_submit():
			logger.debug("form validated")
			''' Now update the db table with the data collected in the form'''
			logger.info("updating sample contents from form data")
			dj.Table._update(sample_contents,'atlas_name',form.atlas_name.data)
			dj.Table._update(sample_contents,'finalorientation',form.finalorientation.data)
			dj.Table._update(sample_contents,'notes_from_processing',form.notes_from_processing.data)

			# logger.info(f"Starting step0 with Celery ")
			logger.info(f"Starting step0 without celery for testing")
			# run_step0.delay(username=username,experiment_name=experiment_name,sample_name=sample_name)
			run_step0(username=username,experiment_name=experiment_name,sample_name=sample_name)

			dj.Table._update(sample_contents,'processing_progress','running')

			flash('Your data processing has begun. You will receive an email \
				when the first steps are completed.','success')
			return redirect(url_for('experiments.exp',username=username,
			experiment_name=experiment_name,sample_name=sample_name))

	elif request.method == 'GET': # get request
		form.atlas_name.data = sample_dict['atlas_name']
		''' Add the imaging purposes to channel_content_dict_list '''
		registration_used = False
		for dict_list in channel_content_dict_list:
			used_imaging_modes = []
			for imaging_mode in current_app.config['IMAGING_MODES']:
				if dict_list[imaging_mode]:
					used_imaging_modes.append(imaging_mode)
					if imaging_mode == 'registration':
						registration_used = True
			dict_list['used_imaging_modes'] = used_imaging_modes
	return render_template('processing/start_processing.html',
		channel_content_dict_list=channel_content_dict_list,registration_used=registration_used,
		sample_dict=sample_dict,form=form,sample_table=sample_table)	



# @cel.task()
def run_step0(username,experiment_name,sample_name):
	""" An asynchronous celery task (runs in a background process) which runs step 0 
	in the light sheet pipeline -- i.e. makes the parameter dictionary pickle file
	and grabs a bunch of metadata from the raw files to store in the database.  
	"""
	logger.info("In step 0")
	import tifffile
	from xml.etree import ElementTree as ET 
	processing_params_dict = {}
	''' Fetch the processing params from the table to run the code '''
	sample_contents = db_lightsheet.Sample() & f'username="{username}"' \
	& f'experiment_name="{experiment_name}"'  & f'sample_name="{sample_name}"'

	channel_contents = db_lightsheet.Sample.ImagingChannel() & f'username="{username}"' \
	& f'experiment_name="{experiment_name}"'  & f'sample_name="{sample_name}"'
	channel_content_dict_list = channel_contents.fetch(as_dict=True)
	sample_contents_dict = sample_contents.fetch1() 

	raw_basepath = f'/jukebox/LightSheetData/lightserv_testing/{username}/{experiment_name}/{sample_name}'  
	''' Make the "inputdictionary", i.e. the mapping between directory and function '''
	processing_params_dict['inputdictionary'] = {}
	input_dictionary = {}

	""" In the location on bucket there could be multiple folders, 
	with each folder having one or more raw datasets in it.

	Need to figure out which channels were imaged in which folders """

	for channel_dict in channel_content_dict_list:
		channel_name = channel_dict['channel_name']
		print(channel_name)
		# for key in sample_contents_dict.keys():
		# 	if f'channel{channel}' in key:
		# 		if sample_contents_dict[key]:
		# 			pass

	# Create a counter for multi-channel imaging. If multi-channel imaging was used
	# this counter will be incremented each time a raw data directory is repeated
	# so that each channel gets assigned the right number, e.g. [['regch','00'],['cellch','01']] 
	# multichannel_counter_dict = {} 
	# for channel in rawdata_dir_dict.keys():
	# 	rawdata_dir = rawdata_dir_dict[channel]
	# 	# First figure out the counter 
	# 	if rawdata_dir in multichannel_counter_dict.keys():
	# 		multichannel_counter_dict[rawdata_dir] += 1
	# 	else:
	# 		multichannel_counter_dict[rawdata_dir] = 0
	# 	multichannel_counter = multichannel_counter_dict[rawdata_dir]
	# 	# Now figure out the channel type
	# 	channel_mode = exp_contents.fetch1(channel)
	# 	if channel_mode == 'registration':
	# 		mode_abbr = 'regch'
	# 	elif channel_mode == 'cell_detection':
	# 		mode_abbr = 'cellch'
	# 	elif channel_mode == 'injection_detection':
	# 		mode_abbr = 'injch'
	# 	elif channel_mode == 'probe_detection':
	# 		mode_abbr = 'injch'
	# 	else:
	# 		abort(403)

	# 	input_list = [mode_abbr,f'{multichannel_counter:02}']
	# 	if multichannel_counter > 0:		
	# 		input_dictionary[rawdata_dir].append(input_list)
	# 	else:
	# 		input_dictionary[rawdata_dir] = [input_list]
	# # Output directory for processed files
	# output_directory = f'/jukebox/LightSheetData/{username}/experiment_{experiment_name}/processed'
	
	# # Figure out xyz scale from metadata of 0th z plane of last rawdata directory (is the same for all directories)
	# # Grab the metadata tags from the 0th z plane
	# z0_plane = glob.glob(rawdata_dir + '/*RawDataStack*Z0000*.tif')[0]

	# with tifffile.TiffFile(z0_plane) as tif:
	# 	tags = tif.pages[0].tags
	# xml_description=tags['ImageDescription'].value
	# root = ET.fromstring(xml_description)
	# # The pixel size is in the PhysicalSizeX, PhysicalSizeY, PhysicalSizeZ attributes, which are in the "Pixels" tag
	# image_tag = root[2]
	# pixel_tag = image_tag[2]
	# pixel_dict = pixel_tag.attrib
	# dx,dy,dz = pixel_dict['PhysicalSizeX'],pixel_dict['PhysicalSizeY'],pixel_dict['PhysicalSizeZ']
	# xyz_scale = (dx,dy,dz)
	
	# param_dict['systemdirectory'] = '/jukebox/'
	# param_dict['inputdictionary'] = input_dictionary
	# param_dict['output_directory'] = output_directory
	# param_dict['xyz_scale'] = xyz_scale
	# logger.info("### PARAM DICT ###")
	# logger.info(param_dict)
	# logger.info('#######')
	# for channel in rawdata_dict.keys():
	# 	rawdata_directory = rawdata_dict
	# param_dict['inputdictionary'] = {rawdata_directory:[]}
	return "success"