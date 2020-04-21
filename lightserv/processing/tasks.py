from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app,jsonify)
from lightserv.main.utils import mymkdir
from lightserv.processing.utils import determine_status_code
from lightserv import cel, db_lightsheet, db_spockadmin
from lightserv.taskmanager.tasks import send_email

import datajoint as dj
from datetime import datetime
import logging
import tifffile
import glob
import os,stat
import pickle
import paramiko
from PIL import Image
import math
from pathlib import Path


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/processing_tasks.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

""" Jobs run as single tasks (not scheduled) """

@cel.task()
def run_lightsheet_pipeline(username,request_name,
	sample_name,imaging_request_number,processing_request_number):
	""" An asynchronous celery task (runs in a background process) which
	runs a script on spock to run the entire light sheet pipeline 
	for each ProcessingResolution() entry in this ProcessingRequest()
	"""

	atlas_dict = current_app.config['ATLAS_NAME_FILE_DICTIONARY']
	atlas_annotation_dict = current_app.config['ATLAS_ANNOTATION_FILE_DICTIONARY']
	now = datetime.now()
	
	import tifffile
	from xml.etree import ElementTree as ET 
	
	''' Fetch the processing params from the table to run the code '''
	sample_contents = db_lightsheet.Request.Sample() & f'username="{username}"' \
	& f'request_name="{request_name}"'  & f'sample_name="{sample_name}"'
	all_channel_contents = db_lightsheet.Request.ImagingChannel() & f'username="{username}"' \
	& f'request_name="{request_name}"'  & f'sample_name="{sample_name}"' & \
	f'imaging_request_number="{imaging_request_number}"'
	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & f'username="{username}"' \
	& f'request_name="{request_name}"'  & f'sample_name="{sample_name}"' & \
	f'imaging_request_number="{imaging_request_number}"' & \
	f'processing_request_number="{processing_request_number}"' 
	channel_content_dict_list = all_channel_contents.fetch(as_dict=True)
	sample_contents_dict = sample_contents.fetch1() 
	sample_basepath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
		request_name,sample_name,f'imaging_request_{imaging_request_number}')
	raw_basepath = os.path.join(sample_basepath,'rawdata')

	""" Loop through the image resolutions requested since 
	we run the pipeline separately for each image resolution requested.
	"""

	all_imaging_modes = current_app.config['IMAGING_MODES']
	connection = db_lightsheet.Request.Sample.connection
	with connection.transaction:
		unique_image_resolutions = sorted(list(set(all_channel_contents.fetch('image_resolution'))))
		for image_resolution in unique_image_resolutions:
			logger.debug("Setting up param dicts for Image resolution: {}".format(image_resolution))
			"""figure out how many different spock jobs we will need to launch.
			This is equivalent to how many parameter dictionaries we have 
			to construct. If all imaging used the same tiling and same 
			z_step then we only need one job """
			this_image_resolution_content = db_lightsheet.Request.ProcessingResolutionRequest() & \
			 f'request_name="{request_name}"' & f'username="{username}"' & \
			 f'sample_name="{sample_name}"' & f'imaging_request_number="{imaging_request_number}"' & \
			 f'processing_request_number="{processing_request_number}"' & \
			 f'image_resolution="{image_resolution}"'  
			atlas_name,final_orientation = this_image_resolution_content.fetch1('atlas_name','final_orientation')
			atlas_file = atlas_dict[atlas_name]
			atlas_annotation_file = atlas_annotation_dict[atlas_name]
			""" set up the base parameter dictionary that is common to this image resolution
			no matter what the imaging parameters were 
			"""
			param_dict = {}
			param_dict['systemdirectory'] = '/jukebox'
			param_dict['blendtype'] = 'sigmoidal' # no exceptions
			param_dict['intensitycorrection'] = True # no exceptions
			param_dict['rawdata'] = True # no exceptions
			param_dict['AtlasFile'] = atlas_file
			param_dict['annotationfile'] = atlas_annotation_file

			output_directory = os.path.join(sample_basepath,'output',
				f'processing_request_{processing_request_number}',
				f'resolution_{image_resolution}')
			param_dict['outputdirectory'] = output_directory

			""" figure out the resize factor based on resolution """
			if image_resolution == '1.3x':
				resizefactor = 3
				x_scale, y_scale = 5.0,5.0
			elif image_resolution == '1.1x':
				resizefactor = 3
				x_scale, y_scale = 5.909091,5.909091
			elif image_resolution == '4x':
				resizefactor = 5
				x_scale, y_scale = 1.63,1.63
			else:
				sys.exit("There was a problem finding the resizefactor")
			param_dict['resizefactor'] = resizefactor
			slurmjobfactor=50
			param_dict['slurmjobfactor'] = slurmjobfactor
			
			""" Now the inputdictionary """
			inputdictionary = {}

			""" Need to find the channels belonging to the same rawdata_subfolder so I can  
			fill out the inputdictionary properly """
			channel_contents_this_resolution = \
				(all_channel_contents & f'image_resolution="{image_resolution}"')
			channel_contents_list_this_resolution = channel_contents_this_resolution.fetch(as_dict=True)

			unique_rawdata_subfolders = list(set(channel_contents_this_resolution.fetch('rawdata_subfolder')))
			logger.debug(f"Have the following rawdata folders: {unique_rawdata_subfolders}")
			max_number_of_z_planes = 0
			for ii in range(len(unique_rawdata_subfolders)):
				rawdata_subfolder = unique_rawdata_subfolders[ii]
				# this_rawdata_dict['rawdata_subfolder']=rawdata_subfolder
				rawdata_fullpath = os.path.join(raw_basepath,rawdata_subfolder)
				inputdictionary[rawdata_fullpath] = []
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

				""" Loop through the channels themselves to make the input dictionary
				and grab the rest of the parameter dictionary keys """
				
				channel_contents_this_subfolder = channel_contents_this_resolution & \
				 f'rawdata_subfolder="{rawdata_subfolder}"'
				channel_contents_dict_list_this_subfolder = channel_contents_this_subfolder.fetch(as_dict=True)
				for channel_dict in channel_contents_dict_list_this_subfolder:		
					channel_name = channel_dict['channel_name']
					channel_index = channel_dict['imspector_channel_index'] 
					processing_channel_insert_dict = {'username':username,'request_name':request_name,
					'sample_name':sample_name,'imaging_request_number':imaging_request_number,
					'processing_request_number':processing_request_number,
					'image_resolution':image_resolution,'channel_name':channel_name,
					'intensity_correction':True,'datetime_processing_started':now}

					channel_imaging_modes = [key for key in all_imaging_modes if channel_dict[key] == True]
					this_channel_content = all_channel_contents & f'channel_name="{channel_name}"'
		
					""" grab the tiling, number of z planes info from the first entry
					since the parameter dictionary only needs one value for 
					xyz_scale, tiling_overlap, etc...
					and it must be the same for each channel in each rawdata folder
					for the code to run (currently) """
					if ii == 0 and channel_index == 0: 
						number_of_z_planes,tiling_scheme,tiling_overlap,z_step,image_orientation = \
							this_channel_content.fetch1(
								'number_of_z_planes','tiling_scheme',
								'tiling_overlap','z_step','image_orientation')
						if number_of_z_planes > max_number_of_z_planes:
							max_number_of_z_planes = number_of_z_planes
						param_dict['tiling_overlap'] = tiling_overlap
						if tiling_scheme != '1x1':
							stitching_method = 'terastitcher'
						else:
							stitching_method = 'blending'
						param_dict['stitchingmethod'] = stitching_method
						xyz_scale = (x_scale,y_scale,z_step)
						param_dict['xyz_scale'] = xyz_scale
						""" Now figure out the final orientation tuple given the 
							orientation that this was imaged at and the requested
							final_orientation string.
							The orientation will have already been forced to be 
							sagittal if one requested a registration channel. """
						if image_orientation == 'horizontal':
							if final_orientation == 'sagittal':
								final_orientation_tuple = ("2","1","0")
							elif final_orientation == 'horizontal':
								final_orientation_tuple = ("0","1","2")
							elif final_orientation == 'coronal':
								final_orientation_tuple = ("2","0","1")
						elif image_orientation == 'sagittal':
							if final_orientation == 'sagittal':
								final_orientation_tuple = ("0","1","2")
							elif final_orientation == 'horizontal':
								final_orientation_tuple = ("2","1","0")
							elif final_orientation == 'coronal':
								final_orientation_tuple = ("0","2","1")
						elif image_orientation == 'coronal':
							if final_orientation == 'sagittal':
								final_orientation_tuple = ("0","2","1")
							elif final_orientation == 'horizontal':
								final_orientation_tuple = ("2","0","1")
							elif final_orientation == 'coronal':
								final_orientation_tuple = ("0","1","2")
						param_dict['finalorientation'] = final_orientation_tuple 

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
					
					processing_channel_insert_dict['lightsheet_channel_str'] = lightsheet_channel_str
					now = datetime.now()
					processing_channel_insert_dict['datetime_processing_started'] = now
					logger.info("Inserting into ProcessingChannel()")
					logger.info(processing_channel_insert_dict)
					db_lightsheet.Request.ProcessingChannel().insert1(processing_channel_insert_dict,replace=True)

			param_dict['inputdictionary'] = inputdictionary
			logger.debug("inputdictionary:")
			logger.debug(inputdictionary)
			logger.debug("")
			logger.debug("Param dictionary")
			logger.debug(param_dict)
			""" Prepare insert to processing db table """
			
			""" Now write the pickle file with the parameter dictionary """	
			pickle_fullpath = output_directory + '/param_dict.p'
			with open(pickle_fullpath,'wb') as pkl_file:
				pickle.dump(param_dict,pkl_file)
			# Open up permissions on the file so the pipeline can write to it
			st = os.stat(pickle_fullpath)
			logger.info(f"wrote pickle file: {pickle_fullpath}")
			logger.debug("Permissions on pickle file are originally:")
			logger.debug(st.st_mode)
			os.chmod(pickle_fullpath,st.st_mode | stat.S_IWOTH)
			st_now = os.stat(pickle_fullpath)
			logger.debug("Permissions on pickle file are now:")
			logger.debug(st_now.st_mode)

			""" Now run the spock pipeline via paramiko """
			hostname = 'spock.pni.princeton.edu'
			if stitching_method == 'blending':
				logger.debug("Running light sheet pipeline with no stitching (single tile)")
				pipeline_shell_script = 'lightsheet_pipeline_no_stitching.sh'
			elif stitching_method == 'terastitcher':
				logger.debug("Running light sheet pipeline with stitching (terastitcher)")
				pipeline_shell_script = 'lightsheet_pipeline_stitching.sh'
			""" figure out how many array jobs we will need for step 1"""
			n_array_jobs_step1 = math.ceil(max_number_of_z_planes/float(slurmjobfactor)) # how many array jobs we need for step 1
			processing_code_dir = current_app.config['PROCESSING_CODE_DIR']
			# command = """cd %s;%s/%s %s %s""" % \
			# 	(processing_code_dir,
			# 		processing_code_dir,
			# 		pipeline_shell_script,
			# 		output_directory,
			# 		n_array_jobs_step1
			# 	)

			command = f"""cd {processing_code_dir}/testing; {processing_code_dir}/testing/test_pipeline.sh"""
			port = 22

			client = paramiko.SSHClient()
			client.load_system_host_keys()
			client.set_missing_host_key_policy(paramiko.WarningPolicy)
			try:
				client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)
			except paramiko.ssh_exception.AuthenticationException:
				logger.info(f"Failed to connect to spock to start job. ")
				dj.Table._update(this_image_resolution_content,'spock_job_progress','NOT_SUBMITTED')	
				flash("Error submitting your job to spock. "
					  "Most likely the ssh key was not copied correctly to your account on spock. "
					  "The key can be found in an email that was sent to you from "
					  "lightservhelper@gmail.com when you submitted your request. "
					  "Please check that the permissions of your ~/.ssh folder on spock are set to 700 "
					  "and the permissions of the .ssh/authorized_keys file is 640:","danger")
				return redirect(url_for('main.FAQ',_anchor='ssh_key'))
			logger.debug("Command:")
			logger.debug(command)
			stdin, stdout, stderr = client.exec_command(command)
			response = str(stdout.read().decode("utf-8").strip('\n')) # strips off the final newline
			logger.debug("Response:")
			logger.debug(response)
			error_response = str(stderr.read().decode("utf-8"))
			logger.debug("Error Response:")
			logger.debug(error_response)

			jobid_step0, jobid_step1, jobid_step2, jobid_step3 = response.split('\n')

			""" Update the job status table in spockadmin schema"""
			status = 'SUBMITTED'
			entry_dict = {'jobid_step3':jobid_step3,'jobid_step2':jobid_step2,'jobid_step1':jobid_step1,
			'jobid_step0':jobid_step0,'username':username,'stitching_method':stitching_method,
			'status_step0':status,'status_step1':status,
			'status_step2':status,'status_step3':status}
			db_spockadmin.ProcessingPipelineSpockJob.insert1(entry_dict)    
			logger.info(f"ProcessingResolutionRequest() request was successfully submitted to spock, jobid: {jobid_step3}")
			""" Update the request tables in lightsheet schema """  
			dj.Table._update(this_image_resolution_content,'spock_jobid',jobid_step3)
			logger.debug("Updated spock jobid in ProcessingResolutionRequest() table")
			dj.Table._update(this_image_resolution_content,'spock_job_progress','SUBMITTED')
			logger.debug("Updated spock job progress in ProcessingResolutionRequest() table")

			dj.Table._update(processing_request_contents,'processing_progress','running')
			logger.debug("Updated processing_progress in ProcessingRequest() table")

			# finally:
			client.close()
	return "SUBMITTED spock job"

@cel.task()
def make_precomputed_tiled_data_poststitching(**kwargs):
	""" Celery task for making precomputed dataset
	(i.e. one that can be read by cloudvolume) from 
	tiled image data after it has been stitched.  

	Spawns a series of spock jobs for handling
	the actual computation
	"""

	""" Read in keys """
	username=kwargs['username']
	request_name=kwargs['request_name']
	sample_name=kwargs['sample_name']
	imaging_request_number=kwargs['imaging_request_number']
	processing_request_number=kwargs['processing_request_number']
	channel_name=kwargs['channel_name']
	channel_index=kwargs['channel_index']
	image_resolution=kwargs['image_resolution']
	lightsheet=kwargs['lightsheet']
	rawdata_subfolder=kwargs['rawdata_subfolder']
	viz_dir = kwargs['viz_dir'] 
	processing_pipeline_jobid_step3 = kwargs['processing_pipeline_jobid_step3']

	rawdata_path = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
								 f"{request_name}/{sample_name}/"
								 f"imaging_request_{imaging_request_number}/rawdata/"
								 f"{rawdata_subfolder}")
	kwargs['rawdata_path'] = rawdata_path
	""" construct the terastitcher output path """
	# brainname = rawdata_path[rawdata_path.rfind('/')+8:-9]
	channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
	logger.debug("CHANNEL INDEX PADDED")
	logger.debug(channel_index_padded)
	logger.debug("Search string:")
	logger.debug(rawdata_path + f'/*_ch{channel_index_padded}_{lightsheet}_lightsheet_ts_out')
	logger.debug(glob.glob(rawdata_path + '/*ts_out'))
	terastitcher_output_parent_dirs = glob.glob(rawdata_path + f'/*_ch{channel_index_padded}_{lightsheet}_lightsheet_ts_out')
	assert len(terastitcher_output_parent_dirs) == 1
	terastitcher_output_parent_dir = terastitcher_output_parent_dirs[0]
	logger.debug("TERASTITCHER OUTPUT DIRECTORY:")
	logger.debug(terastitcher_output_parent_dir)
	""" Find the deepest directory in the terastitcher output folder hierarchy.
	That directory contains the tiled tif files at each z plane """
	all_terastitcher_subpaths = [x[0] for x in os.walk(terastitcher_output_parent_dir)]
	terastitcher_output_dir = max(all_terastitcher_subpaths,key = lambda path: path.count('/'))
	""" Find the number of tif files, which will be the number of z planes
	This is not necessarily the same as the number of z planes in the 
	raw directories because terastitcher can increase/decrease this
	when tiling """
	z_plane_files = glob.glob(terastitcher_output_dir + '/*tif')
	number_of_z_planes = len(z_plane_files)
	kwargs['z_dim'] = number_of_z_planes
	""" Figure out number of pixels in x and y """
	first_plane = z_plane_files[0]
	first_im = Image.open(first_plane)
	x_dim,y_dim = first_im.size
	first_im.close()
	kwargs['x_dim'] = x_dim
	kwargs['y_dim'] = y_dim
	logger.debug("Terastitcher folder has this many z planes:")
	logger.debug(number_of_z_planes)
	kwargs['terastitcher_output_dir'] = terastitcher_output_dir
	logger.debug("Terastitcher output directory:")
	logger.debug(terastitcher_output_dir)
	kwargs['layer_name'] = f'channel{channel_name}_stitched_{lightsheet}_lightsheet'
	logger.debug("Visualization directory:")
	logger.debug(viz_dir)
	slurmjobfactor = 20 # the number of processes to run per core
	n_array_jobs_step1 = math.ceil(number_of_z_planes/float(slurmjobfactor)) # how many array jobs we need for step 1
	n_array_jobs_step2 = 5 # how many array jobs we need for step 2
	kwargs['slurmjobfactor'] = slurmjobfactor
	kwargs['n_array_jobs_step1'] = n_array_jobs_step1
	kwargs['n_array_jobs_step2'] = n_array_jobs_step2
	
	pickle_fullpath = viz_dir + '/precomputed_params.p'
	with open(pickle_fullpath,'wb') as pkl_file:
		pickle.dump(kwargs,pkl_file)
	logger.debug(f'Saved precomputed pickle file: {pickle_fullpath} ')

	# """ Now set up the connection to spock """
	
	command = ("cd /jukebox/wang/ahoag/precomputed/stitched_pipeline; "
			   "/jukebox/wang/ahoag/precomputed/stitched_pipeline/precomputed_pipeline_stitched.sh {} {} {}").format(
		n_array_jobs_step1,n_array_jobs_step2,viz_dir)
	# command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_pipeline.sh "
	hostname = 'spock.pni.princeton.edu'
	port=22
	spock_username = 'lightserv-test' # Use the service account for this step - if it gets overloaded we can switch to user accounts
	client = paramiko.SSHClient()
	client.load_system_host_keys()
	client.set_missing_host_key_policy(paramiko.WarningPolicy)

	client.connect(hostname, port=port, username=spock_username, allow_agent=False,look_for_keys=True)
	stdin, stdout, stderr = client.exec_command(command)
	# jobid_final_step = str(stdout.read().decode("utf-8").strip('\n'))
	response = str(stdout.read().decode("utf-8").strip('\n')) # strips off the final newline
	logger.debug("response from spock:")
	logger.debug(response)
	jobid_step0, jobid_step1, jobid_step2 = response.split('\n')

	status_step0 = 'SUBMITTED'
	status_step1 = 'SUBMITTED'
	status_step2 = 'SUBMITTED'
	entry_dict   = {
				'lightsheet':lightsheet,
				'jobid_step0':jobid_step0,
				'jobid_step1':jobid_step1,
				'jobid_step2':jobid_step2,
				'username':username,'status_step0':status_step0,
				'status_step1':status_step1,'status_step2':status_step2,
				'processing_pipeline_jobid_step3':processing_pipeline_jobid_step3
				}
	logger.debug("Inserting into TiledPrecomputedSpockJob():")
	logger.debug(entry_dict)
	db_spockadmin.TiledPrecomputedSpockJob.insert1(entry_dict)    
	logger.info(f"Precomputed (Tiled data) job inserted into TiledPrecomputedSpockJob() table: {entry_dict}")
	logger.info(f"Precomputed (Tiled data) job successfully submitted to spock, jobid_step2: {jobid_step2}")
	# logger.debug(type(jobid_step2))
	restrict_dict = dict(
		username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number,
		image_resolution=image_resolution,channel_name=channel_name)
	this_processing_channel_content = db_lightsheet.Request.ProcessingChannel() & restrict_dict 
	try:
		if lightsheet == 'left':
			dj.Table._update(this_processing_channel_content,'left_lightsheet_tiled_precomputed_spock_jobid',str(jobid_step2))
			dj.Table._update(this_processing_channel_content,'left_lightsheet_tiled_precomputed_spock_job_progress','SUBMITTED')
		else:
			dj.Table._update(this_processing_channel_content,'right_lightsheet_tiled_precomputed_spock_jobid',str(jobid_step2))
			dj.Table._update(this_processing_channel_content,'right_lightsheet_tiled_precomputed_spock_job_progress','SUBMITTED')
	except:
		logger.info("Unable to update ProcessingChannel() table")
	return "Finished task submitting precomputed pipeline for stitched data"

@cel.task()
def make_precomputed_blended_data(**kwargs):
	""" Celery task for making precomputed dataset
	(i.e. one that can be read by cloudvolume) from 
	blended image data for a single channel.  

	Spawns a series of spock jobs for handling
	the actual computation
	"""

	""" Read in keys """
	username=kwargs['username']
	request_name=kwargs['request_name']
	sample_name=kwargs['sample_name']
	imaging_request_number=kwargs['imaging_request_number']
	processing_request_number=kwargs['processing_request_number']
	channel_name=kwargs['channel_name']
	channel_index=kwargs['channel_index']
	image_resolution=kwargs['image_resolution']
	z_step=kwargs['z_step']
	viz_dir = kwargs['viz_dir'] 
	logger.debug("Visualization directory:")
	logger.debug(viz_dir)
	processing_pipeline_jobid_step3 = kwargs['processing_pipeline_jobid_step3']
	blended_data_path = kwargs['blended_data_path']
	
	""" Find the number of tif files, which will be the number of z planes
	This is not necessarily the same as the number of z planes in the 
	raw directories because terastitcher can increase/decrease this
	when tiling """
	logger.debug("Blended data path is:")
	logger.debug(blended_data_path)
	z_plane_files = glob.glob(blended_data_path + '/*tif')
	number_of_z_planes = len(z_plane_files)
	kwargs['z_dim'] = number_of_z_planes
	""" Figure out number of pixels in x and y """
	first_plane = z_plane_files[0]
	first_im = Image.open(first_plane)
	x_dim,y_dim = first_im.size
	kwargs['x_dim'] = x_dim
	kwargs['y_dim'] = y_dim
	first_im.close()
	
	kwargs['layer_name'] = f'channel{channel_name}_blended'
	
	slurmjobfactor = 20 # the number of processes to run per core
	n_array_jobs_step1 = math.ceil(number_of_z_planes/float(slurmjobfactor)) # how many array jobs we need for step 1
	n_array_jobs_step2 = 5 # how many array jobs we need for step 2
	kwargs['slurmjobfactor'] = slurmjobfactor
	kwargs['n_array_jobs_step1'] = n_array_jobs_step1
	kwargs['n_array_jobs_step2'] = n_array_jobs_step2
	
	pickle_fullpath = viz_dir + '/precomputed_params.p'
	with open(pickle_fullpath,'wb') as pkl_file:
		pickle.dump(kwargs,pkl_file)

	logger.debug(f'Saved precomputed pickle file: {pickle_fullpath} ')
	
	command = ("cd /jukebox/wang/ahoag/precomputed/blended_pipeline; "
			   "/jukebox/wang/ahoag/precomputed/blended_pipeline/precomputed_pipeline_blended.sh {} {} {}").format(
		n_array_jobs_step1,n_array_jobs_step2,viz_dir)
	# command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_pipeline.sh "
	hostname = 'spock.pni.princeton.edu'
	port=22
	spock_username = 'lightserv-test' # Use the service account for this step - if it gets overloaded we can switch to user accounts
	client = paramiko.SSHClient()
	client.load_system_host_keys()
	client.set_missing_host_key_policy(paramiko.WarningPolicy)

	client.connect(hostname, port=port, username=spock_username, allow_agent=False,look_for_keys=True)
	stdin, stdout, stderr = client.exec_command(command)
	# jobid_final_step = str(stdout.read().decode("utf-8").strip('\n'))
	response = str(stdout.read().decode("utf-8").strip('\n')) # strips off the final newline
	logger.debug("response from spock:")
	logger.debug(response)
	jobid_step0, jobid_step1, jobid_step2 = response.split('\n')

	status_step0 = 'SUBMITTED'
	status_step1 = 'SUBMITTED'
	status_step2 = 'SUBMITTED'
	entry_dict   = {
				'jobid_step0':jobid_step0,
				'jobid_step1':jobid_step1,
				'jobid_step2':jobid_step2,
				'username':username,'status_step0':status_step0,
				'status_step1':status_step1,'status_step2':status_step2,
				'processing_pipeline_jobid_step3':processing_pipeline_jobid_step3
				}
	logger.debug("Inserting into BlendedPrecomputedSpockJob():")
	logger.debug(entry_dict)
	db_spockadmin.BlendedPrecomputedSpockJob.insert1(entry_dict)    
	logger.info(f"Precomputed (Blended data) job inserted into BlendedPrecomputedSpockJob() table: {entry_dict}")
	logger.info(f"Precomputed (Blended data) job successfully submitted to spock, jobid_step2: {jobid_step2}")
	# logger.debug(type(jobid_step2))
	restrict_dict = dict(
		username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number,
		image_resolution=image_resolution,channel_name=channel_name)
	this_processing_channel_content = db_lightsheet.Request.ProcessingChannel() & restrict_dict 
	try:
		dj.Table._update(this_processing_channel_content,'blended_precomputed_spock_jobid',str(jobid_step2))
		dj.Table._update(this_processing_channel_content,'blended_precomputed_spock_job_progress','SUBMITTED')
	except:
		logger.info("Unable to update ProcessingChannel() table")
	return "Finished task submitting precomputed pipeline for blended data"

""" Jobs that will be scheduled regularly """

@cel.task()
def processing_job_status_checker():
	""" 
	A celery task that will be run in a schedule

	Checks all outstanding processing job statuses on spock
	and updates their status in the ProcesingPipelineSpockJob() in db_spockadmin
	and ProcessingResolutionRequest() in db_lightsheet, 
	then finally figures out which ProcessingRequest() 
	entities are now complete based on the potentially multiple
	ProcessingResolutionRequest() entries they reference.

	A ProcessingRequest() can consist of several jobs because
	jobs are at the ProcessingResolutionRequest() level. 
	If any of the ProcessingResolutionRequest() jobs failed,
	set the processing_progress in the ProcessingRequest() 
	table to 'failed'. If all jobs completed, then set 
	processing_progress to 'complete'
	"""
	processing_request_contents = db_lightsheet.Request.ProcessingRequest()
   
	""" First get all rows with latest timestamps """
	job_contents = db_spockadmin.ProcessingPipelineSpockJob()
	unique_contents = dj.U('jobid_step3','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	""" Get a list of all jobs we need to check up on, i.e.
	those that could conceivably change. Also list the problematic_codes
	which will be used later for error reporting to the user.
	"""

	# static_codes = ('COMPLETED','FAILED','BOOT_FAIL','CANCELLED','DEADLINE','OUT_OF_MEMORY','REVOKED')
	ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
	incomplete_contents = unique_contents & f'status_step3 in {ongoing_codes}'
	jobids = list(incomplete_contents.fetch('jobid_step3'))
	if jobids == []:
		return "No jobs to check"
	jobids_str = ','.join(str(jobid) for jobid in jobids)
	logger.debug(f"Outstanding job ids are: {jobids}")
	port = 22
	username = 'lightserv-test'
	hostname = 'spock.pni.princeton.edu'

	client = paramiko.SSHClient()
	client.load_system_host_keys()
	client.set_missing_host_key_policy(paramiko.WarningPolicy)
	try:
		client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)
	except:
		logger.debug("Something went wrong connecting to spock.")
		client.close()
		return "Error connecting to spock"
	logger.debug("connected to spock")
	try:
		command = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(jobids_str)
		stdin, stdout, stderr = client.exec_command(command)

		stdout_str = stdout.read().decode("utf-8")
		logger.debug("The response from spock is:")
		logger.debug(stdout_str)
		response_lines = stdout_str.strip('\n').split('\n')
		jobids_received = [x.split('|')[0].split('_')[0] for x in response_lines] # They will be listed as array jobs, e.g. 18521829_[0-5], 18521829_1 depending on their status
		status_codes_received = [x.split('|')[1] for x in response_lines]
		logger.debug("Job ids received")
		logger.debug(jobids_received)
		logger.debug("Status codes received")
		logger.debug(status_codes_received)
		job_status_indices_dict = {jobid:[i for i, x in enumerate(jobids_received) if x == jobid] for jobid in set(jobids_received)} 
		job_insert_list = []
	except:
		logger.debug("Something went wrong fetching job statuses from spock.")
		client.close()
		return "Error fetching job statuses from spock"

	""" Loop through outstanding jobs and determine their statuses """
	for jobid,indices_list in job_status_indices_dict.items():
		logger.debug(f"Working on jobid={jobid}")
		job_insert_dict = {'jobid_step3':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
		status_step3 = determine_status_code(status_codes)
		logger.debug(f"Status code for this job is: {status_step3}")
		job_insert_dict['status_step3'] = status_step3
		""" Find the username, other jobids associated with this jobid """
		username_thisjob,jobid_step0,jobid_step1,jobid_step2 = (unique_contents & f'jobid_step3={jobid}').fetch1(
			'username','jobid_step0','jobid_step1','jobid_step2')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		job_insert_dict['jobid_step1']=jobid_step1
		job_insert_dict['jobid_step2']=jobid_step2
		jobid_step_dict = {'step0':jobid_step0,'step1':jobid_step1,'step2':jobid_step2}

		""" Get the imaging channel entry associated with this jobid
		and update the progress """
		this_processing_resolution_content = db_lightsheet.Request.ProcessingResolutionRequest() & \
		f'spock_jobid={jobid}'
		logger.debug("this processing resolution content:")
		logger.debug(this_processing_resolution_content)
		replace_dict = this_processing_resolution_content.fetch1()
		replace_dict['spock_job_progress'] = status_step3
		dj.Table._update(this_processing_resolution_content,'spock_job_progress',status_step3)
		# db_lightsheet.Request.ProcessingResolutionRequest().insert1(replace_dict,replace=True)
		logger.debug("Updated spock_job_progress in ProcessingResolutionRequest() table ")
		
		""" Now figure out the status codes for the earlier dependency jobs """
		this_run_earlier_jobids_str = ','.join([jobid_step0,jobid_step1,jobid_step2])
		try:
			command_earlier_steps = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(this_run_earlier_jobids_str)
			stdin_earlier_steps, stdout_earlier_steps, stderr_earlier_steps = client.exec_command(command_earlier_steps)
		except:
			logger.debug("Something went wrong fetching steps 0-2 job statuses from spock.")
			client.close()
			return "Error fetching steps 0-2 job statuses from spock"
		stdout_str_earlier_steps = stdout_earlier_steps.read().decode("utf-8")
		try:
			response_lines_earlier_steps = stdout_str_earlier_steps.strip('\n').split('\n')
			jobids_received_earlier_steps = [x.split('|')[0].split('_')[0] for x in response_lines_earlier_steps] # They will be listed as array jobs, e.g. 18521829_[0-5], 18521829_1 depending on their status
			status_codes_received_earlier_steps = [x.split('|')[1] for x in response_lines_earlier_steps]
		except:
			logger.debug("Something went wrong parsing output of sacct query for steps 0-2 on spock")
			client.close()
			return "Error parsing sacct query of jobids for steps 0-2 on spock"

		job_status_indices_dict_earlier_steps = {jobid:[i for i, x in enumerate(jobids_received_earlier_steps) \
			if x == jobid] for jobid in set(jobids_received_earlier_steps)} 
		""" Loop through the earlier steps and figure out their statuses """
		for step_counter in range(3):
		# for jobid_earlier_step,indices_list_earlier_step in job_status_indices_dict_earlier_steps.items():
			step = f'step{step_counter}'
			jobid_earlier_step = jobid_step_dict[step]
			indices_list_earlier_step = job_status_indices_dict_earlier_steps[jobid_earlier_step]
			status_codes_earlier_step = [status_codes_received_earlier_steps[ii] for ii in indices_list_earlier_step]
			status = determine_status_code(status_codes_earlier_step)
			status_step_str = f'status_step{step_counter}'
			job_insert_dict[status_step_str] = status
			step_counter +=1 

		""" If this pipeline run is now 100 percent complete,
		figure out if all of the other pipeline runs 
		that exist for this same processing request
		are also complete.
		If so, then update the processing progress 
		and email the user"""
		(username,request_name,sample_name,imaging_request_number,
		processing_request_number,image_resolution) = this_processing_resolution_content.fetch1(
			"username","request_name","sample_name",
			"imaging_request_number","processing_request_number",
			"image_resolution")
		if status_step3 == 'COMPLETED':
			""" Find all processing channels from this same processing request """
			restrict_dict_imaging = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number)
			imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict_imaging
			restrict_dict_processing = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number)
			processing_resolution_contents = db_lightsheet.Request.ProcessingResolutionRequest() & \
				restrict_dict_processing
			# logger.debug(processing_channel_contents)
			""" Loop through and pool all of the job statuses """
			processing_request_job_statuses = []
			for processing_resolution_dict in processing_resolution_contents:
				job_status = processing_resolution_dict['spock_job_progress']
				processing_request_job_statuses.append(job_status)
			logger.debug("job statuses for this processing request:")
			# print(username,)
			# logger.debug(processing_request_job_statuses)
			# logger.debug(username,request_name,sample_name,imaging_request_number,processing_request_number)
			data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']

			output_directory = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "output",
							 f"processing_request_{processing_request_number}",
							 f"resolution_{image_resolution}")
			if all(x=='COMPLETED' for x in processing_request_job_statuses):
				logger.debug("The processing pipeline for all processing resolution requests"
							 " in this processing request are complete!")
				subject = 'Lightserv automated email: Processing done for your sample'
				body = ('The processing for your sample:\n\n'
						f'request_name: {request_name}\n'
						f'sample_name: {sample_name}\n\n'
						'is now complete. \n\n'
						f'The processed products are available here: {output_directory}')
				send_email(subject=subject,body=body)
				dj.Table._update(processing_request_contents,'processing_progress','complete')

			else:
				logger.debug("Not all processing resolution requests in this "
							 "processing request are completely converted to "
							 "precomputed format")

		job_insert_list.append(job_insert_dict)

	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_spockadmin.ProcessingPipelineSpockJob.insert(job_insert_list)
	logger.debug("Entry in ProcessingPipelineSpockJob() admin table with latest status")

	client.close()


		
	""" Now for each outstanding processing request, go through list of 
		jobids that are linked to that request and update the processing_progress
		accordingly """
	# processing_request_contents = db_lightsheet.Request.ProcessingRequest()
	# running_processing_requests_modified_contents = (processing_request_contents & \
	#     'processing_progress="running"').aggr(processing_resolution_contents,
	#                number_of_jobs="count(*)",
	#                number_of_pending_jobs='SUM(spock_job_progress="PENDING")',
	#                number_of_completed_jobs='SUM(spock_job_progress="COMPLETED")',
	#                number_of_problematic_jobs=f'SUM(spock_job_progress in {problematic_codes})',
	#                spock_jobid ='spock_jobid') 
	# """ For processing requests where all jobids have status=COMPLETE,
	# then the processing_progress='complete' for the whole processing request """
	# completed_processing_requests_modified_contents = (running_processing_requests_modified_contents & \
	#     'number_of_completed_jobs = number_of_jobs')

	# completed_processing_primary_keys_dict_list = completed_processing_requests_modified_contents.fetch(
	#     'username',
	#     'request_name',
	#     'sample_name',
	#     'imaging_request_number',
	#     'processing_request_number',
	#     as_dict=True)

	# for d in completed_processing_primary_keys_dict_list:
	#     logger.debug("Updating processing request table")
	#     username = d.get('username')
	#     request_name = d.get('request_name')
	#     sample_name = d.get('sample_name')
	#     imaging_request_number = d.get('imaging_request_number')
	#     processing_request_number = d.get('processing_request_number')
	#     dj.Table._update(processing_request_contents & \
	#         f'username="{username}"' & f'request_name="{request_name}"' & \
	#         f'sample_name="{sample_name}"' & f'imaging_request_number={imaging_request_number}' & \
	#         f'processing_request_number={processing_request_number}',
	#         'processing_progress','complete')
		
	#     """ Send email to user saying their entire processing request is complete """
	#     sample_basepath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
	#         request_name,sample_name,f'imaging_request_{imaging_request_number}')

	#     output_directory = os.path.join(sample_basepath,'output',
	#             f'processing_request_{processing_request_number}')
	#     msg = EmailMessage()
	#     msg['Subject'] = 'Lightserv automated email: image processing complete'
	#     msg['From'] = 'lightservhelper@gmail.com'
	#     msg['To'] = 'ahoag@princeton.edu' # to me while in DEV phase

					
	#     message_body = ('Hello!\n\nThis is an automated email sent from lightserv, '
	#         'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
	#         'The processing for your request:\n\n'
	#         f'request_name: "{request_name}"\n'
	#         f'sample_name: "{sample_name}"\n'
	#         f'imaging_request_number: {imaging_request_number}\n'
	#         f'processing_request_number: {processing_request_number}\n\n'
	#         'was completed successfully.'
	#         'You can find your processed data here:'
	#         f'\n{output_directory}'
	#         '\n\nThanks,\nThe Histology and Brain Registration Core Facility.')
	#     msg.set_content(message_body)
	#     smtp_server = smtp_connect()
	#     smtp_server.send_message(msg)
	#     logger.debug("Sent email that processing was completed")
	
	# """ For processing requests where even just one jobid has a problematic status,
	# then update the processing_progress='failed' for the whole processing request.
	# Can provide more details in an email """
	# problematic_processing_requests_modified_contents = (running_processing_requests_modified_contents & \
	#     'number_of_problematic_jobs > 0')
	# problematic_processing_primary_keys_dict_list = problematic_processing_requests_modified_contents.fetch(
	#     'username',
	#     'request_name',
	#     'sample_name',
	#     'imaging_request_number',
	#     'processing_request_number',
	#     as_dict=True)

	# for d in problematic_processing_primary_keys_dict_list:
	#     logger.debug("Updating processing request table")
	#     username = d.get('username')
	#     request_name = d.get('request_name')
	#     sample_name = d.get('sample_name')
	#     imaging_request_number = d.get('imaging_request_number')
	#     processing_request_number = d.get('processing_request_number')
	#     dj.Table._update(processing_request_contents & \
	#         f'username="{username}"' & f'request_name="{request_name}"' & \
	#         f'sample_name="{sample_name}"' & f'imaging_request_number={imaging_request_number}' & \
	#         f'processing_request_number={processing_request_number}',
	#         'processing_progress','failed')
	#     sample_basepath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
	#         request_name,sample_name,f'imaging_request_{imaging_request_number}')

	#     output_directory = os.path.join(sample_basepath,'output',
	#             f'processing_request_{processing_request_number}')
		
	#     msg_user = Message('Lightserv automated email: FAILED processing request',
	#                     sender='lightservhelper@gmail.com',
	#                     recipients=['ahoag@princeton.edu']) # send it to me while in DEV phase
					
	#     msg_user.body = ('Hello!\n\nThis is an automated email sent from lightserv, '
	#         'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
	#         'The processing for your request:\n\n'
	#         f'request_name: "{request_name}"\n'
	#         f'sample_name: "{sample_name}"\n'
	#         f'imaging_request_number: {imaging_request_number}\n'
	#         f'processing_request_number: {processing_request_number}\n\n'
	#         'has failed. '
	#         '\n\nThank you for your patience while we look into why this happened. We will get back to you shortly. '
	#         '\n\nIf you have any questions or comments about this please reply to this message.'
	#         '\n\nThanks,\nThe Histology and Brain Registration Core Facility.')
	#     mail.send(msg_user)

	#     """ Now send a message to the admins to alert them that a processing request has failed """
	#     resolution_contents_this_request = db_lightsheet.Request.ProcessingResolutionRequest() & \
	#         f'username="{username}"' & \
	#         f'request_name="{request_name}"' & f'sample_name="{sample_name}"' & \
	#         f'imaging_request_number={imaging_request_number}' & \
	#         f'processing_request_number={processing_request_number}'
	#     job_dict_list = resolution_contents_this_request.fetch(
	#         'image_resolution','spock_jobid','spock_job_progress',as_dict=True)
	#     job_str_lines = '\n'.join(['{0} {1} {2}'.format(
	#         job_dict['image_resolution'],job_dict['spock_jobid'],
	#         job_dict['spock_job_progress']) for job_dict in job_dict_list])
	#     msg_admin = Message('Lightserv automated email: FAILED processing request',
	#                     sender='lightservhelper@gmail.com',
	#                     recipients=['lightservhelper@gmail.com']) # send it to 
					
	#     msg_admin.body = ('Hello!\n\nThis is an automated email sent from lightserv, '
	#         'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
	#         'The processing for request:\n\n'
	#         f'request_name: "{request_name}"\n'
	#         f'sample_name: "{sample_name}"\n'
	#         f'imaging_request_number: {imaging_request_number}\n'
	#         f'processing_request_number: {processing_request_number}\n\n'
	#         'has failed.\n\n'
	#         'In particular, the statuses of all jobs in this processing request are:\n'
	#         '#image_resolution  jobid     status\n'
	#         '{}\n'.format(job_str_lines))

	#     mail.send(msg_admin)

	# for each running process, find all jobids in the processing resolution request tables
	return "Checked processing job statuses"

@cel.task()
def check_for_spock_jobs_ready_for_making_precomputed_tiled_data():
	""" 
	A celery task that will be run in a schedule

	Checks for spock jobs for the light sheet pipeline 
	that use stitching_method='terastitcher' (i.e. tiled)
	for which step 1 (the stitching) is complete AND
	whose precomputed pipeline for visualizing the stitched
	data products is not yet started.

	For each spock job that satisfies those criteria,
	start the precomputed pipeline for tiled data 
	corresponding to that imaging resolution request
	"""
   
	""" First get all rows from the light sheet 
	pipeline where stitching_method='terastitcher'
	and step1='COMPLETED', finding the entries 
	with the latest timestamps """
	job_contents = db_spockadmin.ProcessingPipelineSpockJob() & \
		'stitching_method="terastitcher"' & 'status_step1="COMPLETED"'
	unique_contents = dj.U('jobid_step3','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents

	processing_pipeline_jobids_step3 = unique_contents.fetch('jobid_step3')	
	logger.debug('These are the step 3 jobids of the processing pipeline '
		         'with stitching_method="terastitcher" and a COMPLETED step 1:')
	logger.debug(processing_pipeline_jobids_step3)
	logger.debug("")
	
	""" For each of these jobs, figure out the ones for which the
	tiled precomputed pipeline has not already been started """
	
	for processing_pipeline_jobid_step3 in processing_pipeline_jobids_step3:
		logger.debug(f"Checking out jobid: {processing_pipeline_jobid_step3} ")
		
		""" Check whether the tiled precomputed pipeline has been started for this 
		processing resolution request """

		tiled_precomputed_spock_job_contents = db_spockadmin.TiledPrecomputedSpockJob() & \
			f'processing_pipeline_jobid_step3="{processing_pipeline_jobid_step3}"'
		if len(tiled_precomputed_spock_job_contents) > 0:
			logger.info("Precomputed pipeline already started for this job")
			continue

		""" Kick off a tiled precomputed spock job 
		First need to get the kwarg dictionary for 
		this processing resolution request.
		To get that need to cross-reference the
		ProcessingResolutionRequest()
		table"""
		
		this_processing_resolution_request = db_lightsheet.Request.ProcessingResolutionRequest() & \
			f'spock_jobid={processing_pipeline_jobid_step3}'
		""" Now find all of the ProcessingChannel() entries 
		corresponding to this processing resolution request """
		
		joined_processing_channel_contents = this_processing_resolution_request * \
			db_lightsheet.Request.ProcessingChannel() * \
			db_lightsheet.Request.ImagingChannel()
		
		for this_processing_channel_contents in joined_processing_channel_contents:
			username=this_processing_channel_contents['username']
			request_name = this_processing_channel_contents['request_name']
			sample_name = this_processing_channel_contents['sample_name']
			imaging_request_number = this_processing_channel_contents['imaging_request_number']
			processing_request_number = this_processing_channel_contents['processing_request_number']
			image_resolution = this_processing_channel_contents['image_resolution']
			channel_name = this_processing_channel_contents['channel_name']
			channel_index = this_processing_channel_contents['imspector_channel_index']
			rawdata_subfolder = this_processing_channel_contents['rawdata_subfolder']
			left_lightsheet_used = this_processing_channel_contents['left_lightsheet_used']
			right_lightsheet_used = this_processing_channel_contents['right_lightsheet_used']
			z_step = this_processing_channel_contents['z_step'] # not altered during stitching

			precomputed_kwargs = dict(
				username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number,
				image_resolution=image_resolution,channel_name=channel_name,
				channel_index=channel_index,
				rawdata_subfolder=rawdata_subfolder,
				left_lightsheet_used=left_lightsheet_used,
				right_lightsheet_used=right_lightsheet_used,
				processing_pipeline_jobid_step3=processing_pipeline_jobid_step3,
				z_step=z_step)
			stitched_viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
							 f"{request_name}/{sample_name}/"
							 f"imaging_request_{imaging_request_number}/viz/"
							 f"processing_request_{processing_request_number}/"
							 f"stitched_raw")
			mymkdir(stitched_viz_dir)
			logger.debug(f"Created directory {stitched_viz_dir}")
			channel_viz_dir = os.path.join(stitched_viz_dir,f'channel_{channel_name}')
			mymkdir(channel_viz_dir)
			logger.debug(f"Created directory {channel_viz_dir}")
			if left_lightsheet_used:
				this_viz_dir = os.path.join(channel_viz_dir,'left_lightsheet')
				mymkdir(this_viz_dir)
				logger.debug(f"Created directory {this_viz_dir}")
				precomputed_kwargs['lightsheet'] = 'left'
				precomputed_kwargs['viz_dir'] = this_viz_dir
				make_precomputed_tiled_data_poststitching.delay(**precomputed_kwargs)
				logger.info("Sent precomputed task for tiling left lightsheet")
			if right_lightsheet_used:
				this_viz_dir = os.path.join(channel_viz_dir,'right_lightsheet')
				mymkdir(this_viz_dir)
				logger.debug(f"Created directory {this_viz_dir}")
				precomputed_kwargs['lightsheet'] = 'right'
				precomputed_kwargs['viz_dir'] = this_viz_dir
				make_precomputed_tiled_data_poststitching.delay(**precomputed_kwargs)
				logger.info("Sent precomputed task for tiling right lightsheet")

	return "Checked for light sheet pipeline jobs whose data have been tiled"

@cel.task()
def tiled_precomputed_job_status_checker():
	""" 
	A celery task that will be run in a schedule

	Checks all outstanding job statuses on spock
	for the precomputed tiled (stitched) pipeline
	and updates their status in the TiledPrecomputedSpockJob()
	in db_spockadmin
	and ProcessingChannel() in db_lightsheet 

	"""
   
	""" First get all rows with latest timestamps """
	job_contents = db_spockadmin.TiledPrecomputedSpockJob()
	unique_contents = dj.U('jobid_step2','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	""" Get a list of all jobs we need to check up on, i.e.
	those that could conceivably change. """

	ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
	incomplete_contents = unique_contents & f'status_step2 in {ongoing_codes}'
	jobids = list(incomplete_contents.fetch('jobid_step2'))
	if jobids == []:
		return "No jobs to check"
	jobids_str = ','.join(str(jobid) for jobid in jobids)
	logger.debug(f"Outstanding job ids are: {jobids}")
	port = 22
	username = 'lightserv-test'
	hostname = 'spock.pni.princeton.edu'

	client = paramiko.SSHClient()
	client.load_system_host_keys()
	client.set_missing_host_key_policy(paramiko.WarningPolicy)
	try:
		client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)
	except:
		logger.debug("Something went wrong connecting to spock.")
		client.close()
		return "Error connecting to spock"
	logger.debug("connected to spock")
	try:
		command = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(jobids_str)
		stdin, stdout, stderr = client.exec_command(command)

		stdout_str = stdout.read().decode("utf-8")
		logger.debug("The response from spock is:")
		logger.debug(stdout_str)
		response_lines = stdout_str.strip('\n').split('\n')
		jobids_received = [x.split('|')[0].split('_')[0] for x in response_lines] # They will be listed as array jobs, e.g. 18521829_[0-5], 18521829_1 depending on their status
		status_codes_received = [x.split('|')[1] for x in response_lines]
		logger.debug("Job ids received")
		logger.debug(jobids_received)
		logger.debug("Status codes received")
		logger.debug(status_codes_received)
		job_status_indices_dict = {jobid:[i for i, x in enumerate(jobids_received) if x == jobid] for jobid in set(jobids_received)} 
		job_insert_list = []
	except:
		logger.debug("Something went wrong fetching job statuses from spock.")
		client.close()
		return "Error fetching job statuses from spock"

	""" Loop through the jobids and determine 
	their status from the list of statuses for each of their array jobs"""
	for jobid,indices_list in job_status_indices_dict.items():
		logger.debug(f"Working on jobid={jobid}")
		job_insert_dict = {'jobid_step2':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
		status_step2 = determine_status_code(status_codes)
		logger.debug(f"Status code for this job is: {status_step2}")
		job_insert_dict['status_step2'] = status_step2
		""" Find the username, other jobids associated with this jobid """
		username_thisjob,lightsheet_thisjob,processing_pipeline_jobid_step3_thisjob,jobid_step0,jobid_step1 = (
			unique_contents & f'jobid_step2={jobid}').fetch1(
			'username','lightsheet','processing_pipeline_jobid_step3','jobid_step0','jobid_step1')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['lightsheet']=lightsheet_thisjob
		job_insert_dict['processing_pipeline_jobid_step3']=processing_pipeline_jobid_step3_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		job_insert_dict['jobid_step1']=jobid_step1
		jobid_step_dict = {'step0':jobid_step0,'step1':jobid_step1}
		
		""" Similarly, figure out the status codes for the earlier dependency jobs """
		this_run_earlier_jobids_str = ','.join([jobid_step0,jobid_step1])
		try:
			command_earlier_steps = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(this_run_earlier_jobids_str)
			stdin_earlier_steps, stdout_earlier_steps, stderr_earlier_steps = client.exec_command(command_earlier_steps)
		except:
			logger.debug("Something went wrong fetching steps 0-1 job statuses from spock.")
			client.close()
			return "Error fetching steps 0-1 job statuses from spock"
		stdout_str_earlier_steps = stdout_earlier_steps.read().decode("utf-8")
		try:
			response_lines_earlier_steps = stdout_str_earlier_steps.strip('\n').split('\n')
			jobids_received_earlier_steps = [x.split('|')[0].split('_')[0] for x in response_lines_earlier_steps] # They will be listed as array jobs, e.g. 18521829_[0-5], 18521829_1 depending on their status
			status_codes_received_earlier_steps = [x.split('|')[1] for x in response_lines_earlier_steps]
		except:
			logger.debug("Something went wrong parsing output of sacct query for steps 0-2 on spock")
			client.close()
			return "Error parsing sacct query of jobids for steps 0-2 on spock"

		job_status_indices_dict_earlier_steps = {jobid:[i for i, x in enumerate(jobids_received_earlier_steps) \
			if x == jobid] for jobid in set(jobids_received_earlier_steps)} 
		
		""" Loop through the jobids from the earlier steps
		and figure out their statuses from their array job statuses"""
		for step_counter in range(2):
			step = f'step{step_counter}'
			jobid_earlier_step = jobid_step_dict[step]
			indices_list_earlier_step = job_status_indices_dict_earlier_steps[jobid_earlier_step]
			status_codes_earlier_step = [status_codes_received_earlier_steps[ii] for ii in indices_list_earlier_step]
			status = determine_status_code(status_codes_earlier_step)
			status_step_str = f'status_step{step_counter}'
			job_insert_dict[status_step_str] = status
			step_counter +=1 

		job_insert_list.append(job_insert_dict)

		""" Get the processing channel entry associated with this jobid
		and update the progress """
		if lightsheet_thisjob == 'left':
			restrict_dict = dict(left_lightsheet_tiled_precomputed_spock_jobid=jobid)
			replace_key = 'left_lightsheet_tiled_precomputed_spock_job_progress'
		elif lightsheet_thisjob == 'right':
			restrict_dict = dict(right_lightsheet_tiled_precomputed_spock_jobid=jobid)
			replace_key = 'right_lightsheet_tiled_precomputed_spock_job_progress'
		this_processing_channel_content = db_lightsheet.Request.ProcessingChannel() & restrict_dict
		logger.debug("this processing channel content:")
		logger.debug(this_processing_channel_content)
		dj.Table._update(this_processing_channel_content,replace_key,status_step2)
		logger.debug("Updated spock_job_progress in ProcessingChannel() table ")

		""" If this pipeline run is now 100 percent complete,
		figure out if all of the other tiled precomputed
		pipelines that exist in this same processing request
		and see if they are also complete.
		If so, then email the user that their tiled images
		are ready to be visualized"""

		if status_step2 == 'COMPLETED':
			""" Find all processing channels from this same processing request """
			username,request_name,sample_name,imaging_request_number,processing_request_number = this_processing_channel_content.fetch1(
				'username','request_name','sample_name','imaging_request_number','processing_request_number')
			restrict_dict_imaging = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number)
			imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict_imaging
			restrict_dict_processing = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number)
			processing_channel_contents = db_lightsheet.Request.ProcessingChannel() & restrict_dict_processing
			# logger.debug(processing_channel_contents)
			""" Loop through and pool all of the job statuses """
			processing_request_job_statuses = []
			for processing_channel_dict in processing_channel_contents:
				""" get the imaging channel contents for this channel
				so that I can figure out which light sheets were used """
				channel_name = processing_channel_dict['channel_name']
				this_imaging_channel_contents = imaging_channel_contents & f'channel_name="{channel_name}"'
				left_lightsheet_used = this_imaging_channel_contents.fetch1('left_lightsheet_used')
				right_lightsheet_used = this_imaging_channel_contents.fetch1('right_lightsheet_used')
				if left_lightsheet_used:
					job_status = processing_channel_dict['left_lightsheet_tiled_precomputed_spock_job_progress']
					processing_request_job_statuses.append(job_status)
				if right_lightsheet_used:
					job_status = processing_channel_dict['right_lightsheet_tiled_precomputed_spock_job_progress']
					processing_request_job_statuses.append(job_status)
			logger.debug("job statuses for this processing request:")
			# print(username,)
			logger.debug(username)
			logger.debug(request_name)
			logger.debug(sample_name)
			logger.debug(imaging_request_number)
			logger.debug(processing_request_number)
			# logger.debug(processing_request_job_statuses)
			# logger.debug(username,request_name,sample_name,imaging_request_number,processing_request_number)
			neuroglancer_form_relative_url = os.path.join(
				'/neuroglancer',
				'stitched_data_setup',
				username,
				request_name,
				sample_name,
				str(imaging_request_number),
				str(processing_request_number))
			neuroglancer_form_full_url = 'https://' + os.environ['HOSTURL'] + neuroglancer_form_relative_url
			if all(x=='COMPLETED' for x in processing_request_job_statuses):
				logger.debug("all processing channels in this processing request"
							 " completely converted to precomputed format!")
				subject = 'Lightserv automated email: Stitched data ready to be visualized'
				body = ('Your stitched data for sample:\n\n'
						f'request_name: {request_name}\n'
						f'sample_name: {sample_name}\n\n'
						'are now ready to be visualized. '
						f'To visualize your data, visit this link: {neuroglancer_form_full_url}')
				send_email(subject=subject,body=body)
			else:
				logger.debug("Not all processing channels in this request"
							 " are completely converted to precomputed format")
	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_spockadmin.TiledPrecomputedSpockJob.insert(job_insert_list)
	logger.debug("Entry in TiledPrecomputedSpockJob() spockadmin table with latest status")

	client.close()

	return "Checked tiled precomptued job statuses"

@cel.task()
def check_for_spock_jobs_ready_for_making_precomputed_blended_data():
	""" 
	A celery task that will be run in a schedule

	Checks for spock jobs for the light sheet pipeline 
	for which step 1 (specifically the blending) is complete AND
	whose precomputed pipeline for visualizing the blended
	data products is not yet started.

	For each spock job that satisfies those criteria,
	start the precomputed pipeline for blended data 
	corresponding to that imaging resolution request
	"""
   
	""" First get all rows from the light sheet 
	pipeline where status_step1='COMPLETED', finding the entries 
	with the latest timestamps """
	job_contents = db_spockadmin.ProcessingPipelineSpockJob() & \
		'status_step1="COMPLETED"'
	unique_contents = dj.U('jobid_step3','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents

	processing_pipeline_jobids_step3 = unique_contents.fetch('jobid_step3')	
	logger.debug('These are the step 3 jobids of the processing pipeline '
		         'with a COMPLETED step 1:')
	logger.debug(processing_pipeline_jobids_step3)
	logger.debug("")
	
	""" For each of these jobs, figure out the ones for which the
	blended precomputed pipeline has not already been started """
	
	for processing_pipeline_jobid_step3 in processing_pipeline_jobids_step3:
		logger.debug(f"Checking out jobid: {processing_pipeline_jobid_step3} ")
		
		""" Check whether the blended precomputed pipeline has been started for this 
		processing resolution request """
		
		blended_precomputed_spock_job_contents = db_spockadmin.BlendedPrecomputedSpockJob() & \
			f'processing_pipeline_jobid_step3="{processing_pipeline_jobid_step3}"'
		if len(blended_precomputed_spock_job_contents) > 0:
			logger.info("Precomputed pipeline already started for this job")
			continue

		""" Kick off a blended precomputed spock job 
		First need to get the kwarg dictionary for 
		this processing resolution request.
		To get that need to cross-reference the
		ProcessingResolutionRequest()
		table"""
		
		this_processing_resolution_request = db_lightsheet.Request.ProcessingResolutionRequest() & \
			f'spock_jobid={processing_pipeline_jobid_step3}'
		
		""" Now find all of the ProcessingChannel() entries 
		corresponding to this processing resolution request """
		
		joined_processing_channel_contents = this_processing_resolution_request * \
			db_lightsheet.Request.ProcessingChannel() * \
			db_lightsheet.Request.ImagingChannel()
		
		for this_processing_channel_contents in joined_processing_channel_contents:
			username=this_processing_channel_contents['username']
			request_name = this_processing_channel_contents['request_name']
			sample_name = this_processing_channel_contents['sample_name']
			imaging_request_number = this_processing_channel_contents['imaging_request_number']
			processing_request_number = this_processing_channel_contents['processing_request_number']
			image_resolution = this_processing_channel_contents['image_resolution']
			channel_name = this_processing_channel_contents['channel_name']
			channel_index = this_processing_channel_contents['imspector_channel_index']
			rawdata_subfolder = this_processing_channel_contents['rawdata_subfolder']
			data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
			channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
			blended_data_path = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "output",
							 f"processing_request_{processing_request_number}",
							 f"resolution_{image_resolution}",
							 "full_sizedatafld",
							 f"{rawdata_subfolder}_ch{channel_index_padded}")

			# rawdata_subfolder = this_processing_channel_contents['rawdata_subfolder']
			z_step = this_processing_channel_contents['z_step'] # not altered during blending
			""" number of z planes could be altered in the case of tiling due to terastitcher 
			so we will calculate it on the fly when doing the precomputed steps """
			precomputed_kwargs = dict(
				username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number,
				image_resolution=image_resolution,channel_name=channel_name,
				channel_index=channel_index,
				processing_pipeline_jobid_step3=processing_pipeline_jobid_step3,
				z_step=z_step,blended_data_path=blended_data_path)
			blended_viz_dir = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "viz",
							 f"processing_request_{processing_request_number}",
							 "blended")
			mymkdir(blended_viz_dir)
			logger.debug(f"Created directory {blended_viz_dir}")
			channel_viz_dir = os.path.join(blended_viz_dir,f'channel_{channel_name}')
			mymkdir(channel_viz_dir)
			logger.debug(f"Created directory {channel_viz_dir}")
			precomputed_kwargs['viz_dir'] = channel_viz_dir
			make_precomputed_blended_data.delay(**precomputed_kwargs)
			logger.info("Sent precomputed task for tiling blended data")

	return "Checked for light sheet pipeline jobs whose data have been blended"

@cel.task()
def blended_precomputed_job_status_checker():
	""" 
	A celery task that will be run in a schedule

	Checks all outstanding job statuses on spock
	for the precomputed tiled (stitched) pipeline
	and updates their status in the TiledPrecomputedSpockJob()
	in db_spockadmin
	and ProcessingChannel() in db_lightsheet 

	"""
   
	""" First get all rows with latest timestamps """
	job_contents = db_spockadmin.BlendedPrecomputedSpockJob()
	unique_contents = dj.U('jobid_step2','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	""" Get a list of all jobs we need to check up on, i.e.
	those that could conceivably change. """

	ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
	incomplete_contents = unique_contents & f'status_step2 in {ongoing_codes}'
	jobids = list(incomplete_contents.fetch('jobid_step2'))
	if jobids == []:
		return "No jobs to check"
	jobids_str = ','.join(str(jobid) for jobid in jobids)
	logger.debug(f"Outstanding job ids are: {jobids}")
	port = 22
	username = 'lightserv-test'
	hostname = 'spock.pni.princeton.edu'

	client = paramiko.SSHClient()
	client.load_system_host_keys()
	client.set_missing_host_key_policy(paramiko.WarningPolicy)
	try:
		client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)
	except:
		logger.debug("Something went wrong connecting to spock.")
		client.close()
		return "Error connecting to spock"
	logger.debug("connected to spock")
	try:
		command = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(jobids_str)
		stdin, stdout, stderr = client.exec_command(command)

		stdout_str = stdout.read().decode("utf-8")
		logger.debug("The response from spock is:")
		logger.debug(stdout_str)
		response_lines = stdout_str.strip('\n').split('\n')
		jobids_received = [x.split('|')[0].split('_')[0] for x in response_lines] # They will be listed as array jobs, e.g. 18521829_[0-5], 18521829_1 depending on their status
		status_codes_received = [x.split('|')[1] for x in response_lines]
		logger.debug("Job ids received")
		logger.debug(jobids_received)
		logger.debug("Status codes received")
		logger.debug(status_codes_received)
		job_status_indices_dict = {jobid:[i for i, x in enumerate(jobids_received) if x == jobid] for jobid in set(jobids_received)} 
		job_insert_list = []
	except:
		logger.debug("Something went wrong fetching job statuses from spock.")
		client.close()
		return "Error fetching job statuses from spock"

	""" Loop through the jobids and determine 
	their status from the list of statuses for each of their array jobs"""
	for jobid,indices_list in job_status_indices_dict.items():
		logger.debug(f"Working on jobid={jobid}")
		job_insert_dict = {'jobid_step2':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
		status_step2 = determine_status_code(status_codes)
		logger.debug(f"Status code for this job is: {status_step2}")
		job_insert_dict['status_step2'] = status_step2
		""" Find the username, other jobids associated with this jobid """
		username_thisjob,processing_pipeline_jobid_step3_thisjob,jobid_step0,jobid_step1 = (
			unique_contents & f'jobid_step2={jobid}').fetch1(
			'username','processing_pipeline_jobid_step3','jobid_step0','jobid_step1')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['processing_pipeline_jobid_step3']=processing_pipeline_jobid_step3_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		job_insert_dict['jobid_step1']=jobid_step1
		
		jobid_step_dict = {'step0':jobid_step0,'step1':jobid_step1}
		""" Similarly, figure out the status codes for the earlier dependency jobs """
		this_run_earlier_jobids_str = ','.join([jobid_step0,jobid_step1])
		try:
			command_earlier_steps = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(this_run_earlier_jobids_str)
			stdin_earlier_steps, stdout_earlier_steps, stderr_earlier_steps = client.exec_command(command_earlier_steps)
		except:
			logger.debug("Something went wrong fetching steps 0-1 job statuses from spock.")
			client.close()
			return "Error fetching steps 0-1 job statuses from spock"
		stdout_str_earlier_steps = stdout_earlier_steps.read().decode("utf-8")
		try:
			response_lines_earlier_steps = stdout_str_earlier_steps.strip('\n').split('\n')
			jobids_received_earlier_steps = [x.split('|')[0].split('_')[0] for x in response_lines_earlier_steps] # They will be listed as array jobs, e.g. 18521829_[0-5], 18521829_1 depending on their status
			status_codes_received_earlier_steps = [x.split('|')[1] for x in response_lines_earlier_steps]
		except:
			logger.debug("Something went wrong parsing output of sacct query for steps 0-2 on spock")
			client.close()
			return "Error parsing sacct query of jobids for steps 0-2 on spock"

		job_status_indices_dict_earlier_steps = {jobid:[i for i, x in enumerate(jobids_received_earlier_steps) \
			if x == jobid] for jobid in set(jobids_received_earlier_steps)} 
		
		""" Loop through the jobids from the earlier steps
		and figure out their statuses from their array job statuses"""
		for step_counter in range(2):
			step = f'step{step_counter}'
			jobid_earlier_step = jobid_step_dict[step]
			indices_list_earlier_step = job_status_indices_dict_earlier_steps[jobid_earlier_step]
			status_codes_earlier_step = [status_codes_received_earlier_steps[ii] for ii in indices_list_earlier_step]
			status = determine_status_code(status_codes_earlier_step)
			status_step_str = f'status_step{step_counter}'
			job_insert_dict[status_step_str] = status
			step_counter +=1 

		job_insert_list.append(job_insert_dict)

		""" Get the processing channel entry associated with this jobid
		and update the progress """
		restrict_dict = dict(blended_precomputed_spock_jobid=jobid)
		replace_key = 'blended_precomputed_spock_job_progress'
		this_processing_channel_content = db_lightsheet.Request.ProcessingChannel() & restrict_dict
		logger.debug("this processing channel content:")
		logger.debug(this_processing_channel_content)
		dj.Table._update(this_processing_channel_content,replace_key,status_step2)
		logger.debug(f"Updated {replace_key} in ProcessingChannel() table ")

		""" If this pipeline run is now 100 percent complete,
		figure out if all of the other blended precomputed
		pipelines that exist in this same processing request
		and see if they are also complete.
		If so, then email the user that their blended images
		are ready to be visualized"""

		if status_step2 == 'COMPLETED':
			""" Find all processing channels from this same processing request """
			username,request_name,sample_name,imaging_request_number,processing_request_number = this_processing_channel_content.fetch1(
				'username','request_name','sample_name','imaging_request_number','processing_request_number')
			restrict_dict_imaging = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number)
			imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict_imaging
			restrict_dict_processing = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number)
			processing_channel_contents = db_lightsheet.Request.ProcessingChannel() & restrict_dict_processing
			# logger.debug(processing_channel_contents)
			""" Loop through and pool all of the job statuses """
			processing_request_job_statuses = []
			for processing_channel_dict in processing_channel_contents:
				""" get the imaging channel contents for this channel
				so that I can figure out which light sheets were used """
				channel_name = processing_channel_dict['channel_name']
				this_imaging_channel_contents = imaging_channel_contents & f'channel_name="{channel_name}"'
				job_status = processing_channel_dict['blended_precomputed_spock_job_progress']
				processing_request_job_statuses.append(job_status)
			logger.debug("job statuses for this processing request:")
			# print(username,)
			logger.debug(username)
			logger.debug(request_name)
			logger.debug(sample_name)
			logger.debug(imaging_request_number)
			logger.debug(processing_request_number)
			
			if all(x=='COMPLETED' for x in processing_request_job_statuses):
				neuroglancer_form_relative_url = os.path.join(
					'/neuroglancer',
					'blended_data_setup',
					username,
					request_name,
					sample_name,
					str(imaging_request_number),
					str(processing_request_number)
					)
				neuroglancer_form_full_url = 'https://' + os.environ['HOSTURL'] + neuroglancer_form_relative_url
				logger.debug("all blended channel data in this processing request"
							 " completely converted to precomputed format!")
				subject = 'Lightserv automated email: Blended data ready to be visualized'
				body = ('Your blended data for sample:\n\n'
						f'request_name: {request_name}\n'
						f'sample_name: {sample_name}\n\n'
						'are now ready to be visualized. '
						f'To visualize your data, visit this link: {neuroglancer_form_full_url}')
				send_email(subject=subject,body=body)
			else:
				logger.debug("Not all blended channels in this request"
							 " are completely converted to precomputed format")
	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_spockadmin.BlendedPrecomputedSpockJob.insert(job_insert_list)
	logger.debug("Entry in BlendedPrecomputedSpockJob() spockadmin table with latest status")

	client.close()

	return "Checked blended precomptued job statuses"
