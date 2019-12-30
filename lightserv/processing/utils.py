from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)
from lightserv.processing.forms import StartProcessingForm, NewProcessingRequestForm
from lightserv.processing.tables import (create_dynamic_channels_table_for_processing,
	dynamic_processing_management_table,ImagingOverviewTable,ExistingProcessingTable)
from lightserv import db_lightsheet
from lightserv import cel,mail
import datajoint as dj
from datetime import datetime
import logging
import tifffile
import glob
import os, errno
import pickle
import paramiko
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/processing_utils.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)


# @cel.task()
def run_spock_pipeline(username,request_name,sample_name,imaging_request_number,processing_request_number):
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
	sample_contents = db_lightsheet.Request.Sample() & f'username="{username}"' \
	& f'request_name="{request_name}"'  & f'sample_name="{sample_name}"'
	
	all_channel_contents = db_lightsheet.Request.ImagingChannel() & f'username="{username}"' \
	& f'request_name="{request_name}"'  & f'sample_name="{sample_name}"' & \
	f'imaging_request_number="{imaging_request_number}"'
	channel_content_dict_list = all_channel_contents.fetch(as_dict=True)
	sample_contents_dict = sample_contents.fetch1() 
	sample_basepath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
		request_name,sample_name,f'imaging_request_{imaging_request_number}')
	raw_basepath = os.path.join(sample_basepath,'rawdata')

	""" Can now go in and find the z=0 plane 
	which contains the metadata for each channel """

	""" Loop through the channels in sorted order of channel_name
	and figure out which z=0 plane is which within a directory
	because there can be more than one if multi-channel imaging 
	was performed """

	all_imaging_modes = current_app.config['IMAGING_MODES']
	connection = db_lightsheet.Request.Sample.connection
	with connection.transaction:
		unique_image_resolutions = sorted(list(set(all_channel_contents.fetch('image_resolution'))))
		for image_resolution in unique_image_resolutions:
			this_image_resolution_content = db_lightsheet.Request.ProcessingResolutionRequest() & \
			 f'request_name="{request_name}"' & f'username="{username}"' & \
			 f'sample_name="{sample_name}"' & f'imaging_request_number="{imaging_request_number}"' & \
			 f'processing_request_number="{processing_request_number}"' & \
			 f'image_resolution="{image_resolution}"'  
			atlas_name = this_image_resolution_content.fetch1('atlas_name')
			atlas_file = atlas_dict[atlas_name]
			atlas_annotation_file = atlas_annotation_dict[atlas_name]

			channel_contents_this_resolution = \
				(all_channel_contents & f'image_resolution="{image_resolution}"')
			channel_contents_list_this_resolution = channel_contents_this_resolution.fetch(as_dict=True)

			""" Now find the channels belonging to the same rawdata_subfolder so I can  
			run the multi-imaging channels together in the code """
			unique_rawdata_subfolders = list(set(channel_contents_this_resolution.fetch('rawdata_subfolder')))
			for rawdata_subfolder in unique_rawdata_subfolders:
				rawdata_fullpath = os.path.join(raw_basepath,rawdata_subfolder)

				""" set up the parameter dictionary """
				param_dict = {}
				param_dict['systemdirectory'] = '/jukebox'
				output_directory = os.path.join(sample_basepath,'output',
					f'processing_request_{processing_request_number}',rawdata_subfolder)
				param_dict['outputdirectory'] = output_directory
				param_dict['blendtype'] = 'sigmoidal' # no exceptions
				param_dict['intensitycorrection'] = True # no exceptions
				param_dict['rawdata'] = True # no exceptions
				param_dict['AtlasFile'] = atlas_file
				param_dict['annotationfile'] = atlas_annotation_file

				""" figure out the resize factor based on resolution """
				if image_resolution == '1.3x':
					resizefactor = 3
					x_scale, y_scale = 5.0,5.0
				elif image_resolution == '4x':
					resizefactor = 5
					x_scale, y_scale = 1.63,1.63
				else:
					sys.exit("There was a problem finding the resizefactor")
				param_dict['resizefactor'] = resizefactor
				param_dict['finalorientation'] = ("2","1","0") # hardcoded for now but will need to be captured from the user 
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
				channel_contents_this_subfolder = channel_contents_this_resolution & \
				 f'rawdata_subfolder="{rawdata_subfolder}"'
				channel_contents_dict_list_this_subfolder = channel_contents_this_subfolder.fetch(as_dict=True)
				for channel_dict in channel_contents_dict_list_this_subfolder:		
					channel_name = channel_dict['channel_name']
					channel_index = channel_dict['imspector_channel_index'] 
					processing_insert_dict = {'username':username,'request_name':request_name,
					'sample_name':sample_name,'imaging_request_number':imaging_request_number,
					'processing_request_number':processing_request_number,
					'image_resolution':image_resolution,'channel_name':channel_name,
					'intensity_correction':True,'datetime_processing_started':now}

					channel_imaging_modes = [key for key in all_imaging_modes if channel_dict[key] == True]
					this_channel_content = all_channel_contents & f'channel_name="{channel_name}"'
					logger.info("This channel content")
					logger.info(this_channel_content)
					""" grab the tiling, number of z planes info from the first entry since it has to be the same for all 
					channels in the same rawdata_subfolder"""
					if channel_index == 0:
						tiling_scheme,tiling_overlap,z_step = this_channel_content.fetch1('tiling_scheme','tiling_overlap','z_step')
						param_dict['tiling_overlap'] = tiling_overlap
						if tiling_scheme != '1x1':
							stitching_method = 'terastitcher'
						else:
							stitching_method = 'blending'
						param_dict['stitchingmethod'] = stitching_method
						
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
						lightsheet_channel_str = 'gench'
					inputdictionary[rawdata_fullpath].append([lightsheet_channel_str,str(channel_index).zfill(2)])

					processing_insert_dict['lightsheet_channel_str'] = lightsheet_channel_str
					now = datetime.now()
					processing_insert_dict['datetime_processing_started'] = now
					logger.info("Inserting into ProcessingChannel()")
					logger.info(processing_insert_dict)
					db_lightsheet.Request.ProcessingChannel().insert1(processing_insert_dict,replace=True)

				param_dict['inputdictionary'] = inputdictionary
				xyz_scale = (x_scale,y_scale,z_step)
				param_dict['xyz_scale'] = xyz_scale
				param_dict['slurmjobfactor'] = 50
				logger.info(param_dict)
				""" Prepare insert to processing db table """
				
				""" Now write the pickle file with the parameter dictionary """	
				try:
				    os.makedirs(output_directory)
				except OSError as exc: 
				    if exc.errno == errno.EEXIST and os.path.isdir(output_directory):
				        pass
				logger.info(f"Made directory: {output_directory}")
				pickle_fullpath = output_directory + '/param_dict.p'
				with open(pickle_fullpath,'wb') as pkl_file:
					pickle.dump(param_dict,pkl_file)
				logger.info(f"wrote pickle file: {pickle_fullpath}")

				""" Now run step 0 in the code via paramiko """
				hostname = 'spock.pni.princeton.edu'

				command = """cd %s;sbatch --export=output_directory='%s' main.sh """ % \
				(current_app.config['PROCESSING_CODE_DIR'],output_directory)
				port = 22
				try:
					client = paramiko.SSHClient()
					client.load_system_host_keys()
					client.set_missing_host_key_policy(paramiko.WarningPolicy)
					
					client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)

					stdin, stdout, stderr = client.exec_command(command)
					print(stdout.read(),stderr.read())

				finally:
					client.close()
	return "success"