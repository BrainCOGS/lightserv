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
from datetime import datetime
import logging
import tifffile
import glob
import os

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
			dj.Table._update(sample_contents,'notes_from_processing',form.notes_from_processing.data)
			""" loop through and update the atlas to be used based on what the user supplied """
			for form_resolution_dict in form.image_resolution_forms.data:
				image_resolution = form_resolution_dict['image_resolution']
				atlas_name = form_resolution_dict['atlas_name']
				for form_channel_dict in form_resolution_dict['channel_forms']:
					channel_name = form_channel_dict['channel_name']
					channel_content = channel_contents & f'channel_name="{channel_name}"' &  f'image_resolution="{image_resolution}"'
					# logger.info(channel_content)
					logger.info("updating channel contents from form data")
					dj.Table._update(channel_content,'atlas_name',atlas_name)
			logger.info(f"Starting step0 without celery for testing")
			# run_step0.delay(username=username,experiment_name=experiment_name,sample_name=sample_name)
			run_step0(username=username,experiment_name=experiment_name,sample_name=sample_name)

			dj.Table._update(sample_contents,'processing_progress','running')

			flash('Your data processing has begun. You will receive an email \
				when the first steps are completed.','success')
			asdf
			# return redirect(url_for('experiments.exp',username=username,
			# experiment_name=experiment_name,sample_name=sample_name))

	elif request.method == 'GET': # get request
		channel_contents_lists = []
		while len(form.image_resolution_forms) > 0:
			form.image_resolution_forms.pop_entry()
		""" Figure out the unique number of image resolutions """
		unique_image_resolutions = sorted(list(set(channel_contents.fetch('image_resolution'))))
		for ii in range(len(unique_image_resolutions)):
			this_image_resolution = unique_image_resolutions[ii]
			channel_contents_list_this_resolution = (channel_contents & f'image_resolution="{this_image_resolution}"').fetch(as_dict=True)
			channel_contents_lists.append([])
			form.image_resolution_forms.append_entry()
			this_resolution_form = form.image_resolution_forms[-1]
			this_resolution_form.image_resolution.data = this_image_resolution
			''' Now go and add the channel subforms to the image resolution form '''
			for jj in range(len(channel_contents_list_this_resolution)):
				channel_content = channel_contents_list_this_resolution[jj]
				channel_contents_lists[ii].append(channel_content)
				this_resolution_form.channel_forms.append_entry()
				this_channel_form = this_resolution_form.channel_forms[-1]
				this_channel_form.channel_name.data = channel_content['channel_name']
				this_resolution_form.atlas_name.data = channel_content['atlas_name']

				""" figure out the channel purposes """
				used_imaging_modes = []
				for imaging_mode in current_app.config['IMAGING_MODES']:
					if channel_content[imaging_mode]:
						used_imaging_modes.append(imaging_mode)
				channel_purposes_str = ', '.join(mode for mode in used_imaging_modes)
				this_channel_form.channel_purposes_str.data = channel_purposes_str

	return render_template('processing/start_processing.html',
		channel_contents_lists=channel_contents_lists,
		sample_dict=sample_dict,form=form,sample_table=sample_table)	


# @cel.task()
def run_step0(username,experiment_name,sample_name):
	""" An asynchronous celery task (runs in a background process) which runs step 0 
	in the light sheet pipeline -- i.e. makes the parameter dictionary pickle file
	and grabs a bunch of metadata from the raw files to store in the database.  
	"""
	atlas_dict = current_app.config['ATLAS_NAME_FILE_DICTIONARY']
	atlas_annotation_dict = current_app.config['ATLAS_ANNOTATION_FILE_DICTIONARY']
	now = datetime.now()
	logger.info("In step 0")
	import tifffile
	from xml.etree import ElementTree as ET 
	
	''' Fetch the processing params from the table to run the code '''
	sample_contents = db_lightsheet.Sample() & f'username="{username}"' \
	& f'experiment_name="{experiment_name}"'  & f'sample_name="{sample_name}"'
	
	all_channel_contents = db_lightsheet.Sample.ImagingChannel() & f'username="{username}"' \
	& f'experiment_name="{experiment_name}"'  & f'sample_name="{sample_name}"'
	channel_content_dict_list = all_channel_contents.fetch(as_dict=True)
	sample_contents_dict = sample_contents.fetch1() 

	raw_basepath = os.path.join(current_app.config['RAWDATA_ROOTPATH'],username,
		experiment_name,sample_name)

	""" Can now go in and find the z=0 plane 
	which contains the metadata for each channel """

	""" Loop through the channels in sorted order of channel_name
	and figure out which z=0 plane is which within a directory
	because there can be more than one if multi-channel imaging 
	was performed """

	all_imaging_modes = current_app.config['IMAGING_MODES']
	connection = db_lightsheet.Sample.connection
	with connection.transaction:
		unique_image_resolutions = sorted(list(set(all_channel_contents.fetch('image_resolution'))))
		for image_resolution in unique_image_resolutions:
			channel_contents_this_resolution = \
				(all_channel_contents & f'image_resolution="{image_resolution}"')
			channel_contents_list_this_resolution = channel_contents_this_resolution.fetch(as_dict=True)

			""" Now find the channels belonging to the same rawdata_subfolder so I can  
			run the multi-imaging channels together in the code """
			unique_rawdata_subfolders = list(set(channel_contents_this_resolution.fetch('rawdata_subfolder')))
			for rawdata_subfolder in unique_rawdata_subfolders:
				rawdata_fullpath = raw_basepath + '/' + rawdata_subfolder

				""" set up the parameter dictionary """
				param_dict = {}
				param_dict['systemdirectory'] = '/jukebox'
				output_directory = os.path.join(raw_basepath,'output')
				param_dict['outputdirectory'] = output_directory
				param_dict['blendtype'] = 'sigmoidal' # no exceptions
				param_dict['intensitycorrection'] = True # no exceptions
				param_dict['rawdata'] = True # no exceptions
				""" figure out the resize factor based on resolution """
				if image_resolution == '1.1x' or image_resolution == '1.3x':
					resizefactor = 3
				elif image_resolution == '2x':
					resizefactor = 4
				elif image_resolution == '4x':
					resizefactor = 5

				""" grab the metadata """
				# logger.info(f"finding metadata for channel {channel_name}")
					
				""" First find the z=0 plane for this channel """

				# ''' Always look in the Filter0000 z=0 file for the full metadata 
				# since it holds the info for the Filter0001, Filter00002, etc... files as well and 
				# the metadata in the z=0 planes for the Filter0001, ... files does not have the 
				# necessary information '''
				# z0_plane_path = glob.glob(rawdata_fullpath + \
				# 	f'/*RawDataStack*C00*Filter0000.ome.tif')[0] # C00 just means left lightsheet which should always be there
				# logger.info(f"Found Z=0 Filter0000 file: {z0_plane_path}")
				# """ Extract metadata """
				# with tifffile.TiffFile(z0_plane_path) as tif:
				# 	tags = tif.pages[0].tags
				# xml_description=tags['ImageDescription'].value

				# root = ET.fromstring(xml_description)

				# ''' NA '''
				# custom_attributes = root[-1]
				# prop_array = custom_attributes[0]
				# for child in prop_array:
				# 	if 'UltraII_Na_Value' in child.tag:
				# 		NA = float(child.attrib['Value'])
				# 		processing_insert_dict['numerical_aperture'] = NA

				# ''' pixel type '''
				# image_tag = root[2]
				# pixel_tag = image_tag[2]
				# pixel_dict = pixel_tag.attrib
				# pixel_type = pixel_dict['PixelType']
				# dj.Table._update(this_channel_content,'pixel_type',pixel_type)
				# # processing_insert_dict['pixel_type'] = pixel_type

				# ''' xyz_scale '''
				# x_scale = int(float(pixel_dict['PhysicalSizeX']))
				# y_scale = int(float(pixel_dict['PhysicalSizeY']))
				# z_scale = int(float(pixel_dict['PhysicalSizeZ']))
				# param_dict['xyz_scale'] = (x_scale,y_scale,z_scale)

				# ''' imspector version '''
				# try:
				# 	custom_attributes_image = image_tag[-1]
				# 	version_tag = [child for child in custom_attributes_image if 'ImspectorVersion' in child.tag][0]
				# 	imspector_version = version_tag.attrib['ImspectorVersion']
				# 	processing_insert_dict['imspector_version'] = imspector_version,	
				# except:
				# 	pass # do nothing. Those values will stay NULL
				# ''' Store all of the metadata as an xml string for later access if needed '''
				# processing_insert_dict['metadata_xml_string'] = xml_description			

				""" Loop through the channels themselves to make the input dictionary """
				inputdictionary = {}
				inputdictionary[rawdata_fullpath] = []
				channel_contents_this_subfolder = channel_contents_this_resolution & f'rawdata_subfolder="{rawdata_subfolder}"'
				logger.info(channel_contents_this_subfolder)
				channel_contents_dict_list_this_subfolder = channel_contents_this_subfolder.fetch(as_dict=True)
				for channel_dict in channel_contents_dict_list_this_subfolder:		
					
					channel_name = channel_dict['channel_name']
					channel_index = channel_dict['imspector_channel_index'] 

					channel_imaging_modes = [key for key in all_imaging_modes if channel_dict[key] == True]
					this_channel_content = all_channel_contents & f'channel_name="{channel_name}'
					""" grab the tiling, atlas info from the first entry since it has to be the same for all 
					channels in the same rawdata_subfolder"""
					if channel_index == 0:
						tiling_scheme,tiling_overlap, atlas_name = \
						 this_channel_content.fetch1('tiling_scheme,','tiling_overlap','atlas_name')
						param_dict['tiling_overlap'] = tiling_overlap
						if tiling_scheme != '1x1':
							stitching_method = 'terastitcher'
						else:
							stitching_method = 'blending'
						param_dict['stitchingmethod'] = stitching_method
						atlas_file = atlas_dict[atlas_name]
						atlas_annotation_file = atlas_annotation_dict[atlas_name]
						param_dict['atlasfile'] = atlas_file
						param_dict['annotationfile'] = atlas_annotation_file
					
					
					""" Fill inputdictionary """

					if 'registration' in channel_imaging_modes:
						lightsheet_channel_str = 'regch'
					elif 'injection_detection' in channel_imaging_modes:
						lightsheet_channel_str = 'injch'
					elif 'probe_detection' in channel_imaging_modes:
						lightsheet_channel_str = 'injch'
					elif 'cell_detection' in channel_imaging_modes:
						lightsheet_channel_str = 'cellch'
					else:
						lightsheet_channel_str = 'anych'
					inputdictionary[rawdata_fullpath].append([lightsheet_channel_str,str(channel_index).zfill(2)])

					processing_insert_dict['lightsheet_channel_str'] = lightsheet_channel_str
				param_dict[inputdictionary] = inputdictionary

				""" Prepare insert to processing db table """
				processing_insert_dict = {'username':username,'experiment_name':experiment_name,
					'sample_name':sample_name,'channel_name':channel_name,'intensity_correction':True,
					'datetime_processing_started':now}
					# logger.info("inputdictionary: {}".format(inputdictionary))
					# db_lightsheet.Sample.ProcessingChannel().insert1(processing_insert_dict)
					# logger.info("Inserted processing params into db table")
					# dj.Table._update()
				
	""" Fill out the parameter dictionar(ies) for this sample.
	There could be more than one because channels could have been imaged 
	separately. However, channels could also have been imaged together, so 
	we cannot simply loop through channels and make a parameter dictionary for each """

	""" To do this, need to figure out what the request for this channel was
	(e.g. registration). Could be more than one purpose """
	
	
	
	
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