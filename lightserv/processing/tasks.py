from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app,jsonify)
from lightserv.main.utils import mymkdir
from lightserv.processing.utils import determine_status_code
from lightserv import cel, db_lightsheet, db_spockadmin
from lightserv.main.tasks import (send_email, send_admin_email,
	connect_to_spock)

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
logger.propagate = False
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''

file_handler = logging.FileHandler('logs/processing_tasks.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.addHandler(file_handler)

##################################################
##### Tasks run individually (not scheduled) #####
##################################################

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
	
	''' Fetch the processing params from the db table to run the code '''
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
	we run the pipeline separately for each image resolution
	requested.
	"""

	all_imaging_modes = current_app.config['IMAGING_MODES']
	connection = db_lightsheet.Request.Sample.connection
	with connection.transaction:
		results_list=all_channel_contents.fetch('image_resolution','ventral_up',as_dict=True)
		tup_list = sorted(set([(d['image_resolution'],d['ventral_up']) for d in results_list]))
		for image_resolution,ventral_up in tup_list:
			if image_resolution == '3.6x' or image_resolution == '15x':
				logger.debug("Not running pipeline for Image resolution: {}".format(image_resolution))
				logger.debug("This resolution is not supported yet!")
				continue
			logger.debug(f"Setting up param dicts for Image resolution: {image_resolution}, \
				ventral_up: {bool(ventral_up)}")
			
			this_processing_resolution_content = db_lightsheet.Request.ProcessingResolutionRequest() & \
			 f'request_name="{request_name}"' & f'username="{username}"' & \
			 f'sample_name="{sample_name}"' & f'imaging_request_number="{imaging_request_number}"' & \
			 f'processing_request_number="{processing_request_number}"' & \
			 f'image_resolution="{image_resolution}"'  &  f'ventral_up={ventral_up}'

			logger.debug("grabbing atlas name and final_orientation") 
			atlas_name,final_orientation = this_processing_resolution_content.fetch1('atlas_name','final_orientation')
	
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

			if ventral_up:
				output_directory = os.path.join(sample_basepath,'output',
					f'processing_request_{processing_request_number}',
					f'resolution_{image_resolution}_ventral_up')
			else:
				output_directory = os.path.join(sample_basepath,'output',
					f'processing_request_{processing_request_number}',
					f'resolution_{image_resolution}')
			param_dict['outputdirectory'] = output_directory
			mymkdir(output_directory)

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
			restrict_dict = {'image_resolution':image_resolution,
					'ventral_up':ventral_up}
			channel_contents_this_resolution = all_channel_contents & restrict_dict
			channel_contents_list_this_resolution = channel_contents_this_resolution.fetch(as_dict=True)

			unique_rawdata_subfolders = list(set(channel_contents_this_resolution.fetch('rawdata_subfolder')))
			logger.debug(f"Have the following rawdata folders: {unique_rawdata_subfolders}")
			max_number_of_z_planes = 0
			for ii in range(len(unique_rawdata_subfolders)):
				rawdata_subfolder = unique_rawdata_subfolders[ii]
				# this_rawdata_dict['rawdata_subfolder']=rawdata_subfolder
				if ventral_up:
					rawdata_fullpath = os.path.join(raw_basepath,
						f'resolution_{image_resolution}_ventral_up',
						rawdata_subfolder)
				else:
					rawdata_fullpath = os.path.join(raw_basepath,
						f'resolution_{image_resolution}',
						rawdata_subfolder)
				inputdictionary[rawdata_fullpath] = []  

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
					'ventral_up':ventral_up,
					'image_resolution':image_resolution,'channel_name':channel_name,
					'intensity_correction':True,'datetime_processing_started':now}

					""" Figure out which imaging modes were selected for this channel, 
					e.g. registration, injection detection """
					channel_imaging_modes = [key for key in all_imaging_modes if channel_dict[key] == True]
					this_channel_content = channel_contents_this_resolution & f'channel_name="{channel_name}"'
		
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
							""" For horizontal image orientation we give the option
							of imaging ventral up. If that happened, we need to 
							tell BrainPipe. To tell it, we need to add a "-" sign
							to the z and x dimension strings """
							if ventral_up: 
								z_str = "-2"
								x_str = "-0"
							else:
								z_str = "2"
								x_str = "0"
							y_str = "1"
							if final_orientation == 'sagittal':
								final_orientation_tuple = (z_str,y_str,x_str)
							elif final_orientation == 'horizontal':
								final_orientation_tuple = (x_str,y_str,z_str)
							elif final_orientation == 'coronal':
								final_orientation_tuple = (z_str,x_str,y_str)
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
					inputdictionary[rawdata_fullpath].append(
						[lightsheet_channel_str,str(channel_index).zfill(2)])
					
					processing_channel_insert_dict['lightsheet_channel_str'] = lightsheet_channel_str           
					logger.info("Inserting into ProcessingChannel()")
					logger.info(processing_channel_insert_dict)
					db_lightsheet.Request.ProcessingChannel().insert1(processing_channel_insert_dict,replace=True)

			param_dict['inputdictionary'] = inputdictionary
			logger.debug("inputdictionary:")
			logger.debug(inputdictionary)
			logger.debug("")
			logger.debug("Param dictionary")
			logger.debug(param_dict)

			""" Now write the pickle file with the parameter dictionary """ 
			pickle_fullpath = output_directory + '/param_dict.p'
			with open(pickle_fullpath,'wb') as pkl_file:
				pickle.dump(param_dict,pkl_file)
			# Open up permissions on the file so the pipeline can write to it
			st = os.stat(pickle_fullpath)
			logger.info(f"wrote pickle file: {pickle_fullpath}")
			logger.debug("Permissions on pickle file are originally:")
			logger.debug(st.st_mode)
			# Add group write permissions so that lightserv-test or anyone in 
			os.chmod(pickle_fullpath,st.st_mode | stat.S_IWGRP)
			st_now = os.stat(pickle_fullpath)
			logger.debug("Group should have write permissions to the pickle file now")
			logger.debug(st_now.st_mode)

			""" Now run the spock pipeline via paramiko """

			""" If we have tiled data then we need to run a different
			pipeline than for non-tiled data since terastitcher needs 
			to be used """
			""" If there are no regch entries in the inputdictionary then don't
			run step 3 in the light sheet processing pipeline """
			no_registration_channels = 0
			n_channels_reg = 0
			for x in inputdictionary.values():
				for y in x:
					if y[0] == 'regch':
						n_channels_reg+=1
			
			if n_channels_reg == 0:
				no_registration_channels = 1

			""" Figure out how many channels there are total in this request """
			n_channels_total = sum([len(channel_list) for channel_list in inputdictionary.values()])
			""" Now figure out based on whether we have registration channel how
			we are going to run the code """
			if no_registration_channels:
				logger.debug("No registration channel. Running only steps 0-2 of the pipeline")
				if stitching_method == 'blending':
					logger.debug("Running light sheet pipeline with no stitching (single tile)")
					pipeline_shell_script = 'lightsheet_pipeline_no_stitching_no_reg.sh'
					n_array_jobs_step1 = math.ceil(max_number_of_z_planes/float(slurmjobfactor)) # how many array jobs we need for step 1
				elif stitching_method == 'terastitcher':
					logger.debug("Running light sheet pipeline with stitching (terastitcher)")
					pipeline_shell_script = 'lightsheet_pipeline_stitching_no_reg.sh'
					n_array_jobs_step1 = n_channels_total
			else:
				logger.debug("Have at least one registration channel. Running full pipeline (steps 0-3)")
				if stitching_method == 'blending':
					logger.debug("Running light sheet pipeline with no stitching (single tile)")
					pipeline_shell_script = 'lightsheet_pipeline_no_stitching.sh'
					n_array_jobs_step1 = math.ceil(max_number_of_z_planes/float(slurmjobfactor)) # how many array jobs we need for step 1

				elif stitching_method == 'terastitcher':
					logger.debug("Running light sheet pipeline with stitching (terastitcher)")
					pipeline_shell_script = 'lightsheet_pipeline_stitching.sh'
					n_array_jobs_step1 = n_channels_total
				
			processing_code_dir = current_app.config['PROCESSING_CODE_DIR']
			
			""" Set up the communication with spock """

			""" First get the git commit from brainpipe """
			command_get_commit = f'cd {processing_code_dir}; git rev-parse --short HEAD'

			
			# if os.environ['FLASK_MODE'] == 'TEST' or os.environ['FLASK_MODE'] == 'DEV' :
			if os.environ['FLASK_MODE'] == 'TEST':
				if n_channels_reg > 0:
					command = f"""cd {processing_code_dir}/testing; {processing_code_dir}/testing/test_pipeline.sh"""
				else:   
					command = f"""cd {processing_code_dir}/testing; {processing_code_dir}/testing/test_pipeline_noreg.sh"""
			else:
				# if n_channels_reg > 0:
				#   command = f"""cd {processing_code_dir}/testing; {processing_code_dir}/testing/test_sleep_pipeline.sh"""
				# else: 
				#   command = f"""cd {processing_code_dir}/testing; {processing_code_dir}/testing/test_sleep_pipeline_noreg.sh"""
				command = """cd %s;%s/%s %s %s %s""" % \
				(processing_code_dir,
					processing_code_dir,
					pipeline_shell_script,
					output_directory,
					n_array_jobs_step1,
					n_channels_total
				)
			
			client = connect_to_spock()

			logger.debug("Command:")
			logger.debug(command)
			stdin, stdout, stderr = client.exec_command(command)
			response = str(stdout.read().decode("utf-8").strip('\n')) # strips off the final newline
			logger.debug("Response:")
			logger.debug(response)
			error_response = str(stderr.read().decode("utf-8"))
			logger.debug("Error Response:")
			logger.debug(error_response)

			status = 'SUBMITTED'
			entry_dict = {}
			if no_registration_channels:
				# Then we didn't run step 3 in the pipeline
				jobid_step0, jobid_step1, jobid_step2 = response.split('\n')
			else:
				jobid_step0, jobid_step1, jobid_step2, jobid_step3 = response.split('\n')
				entry_dict['jobid_step3'] = jobid_step3
				entry_dict['status_step3'] = status
			
			entry_dict['jobid_step2'] = jobid_step2
			entry_dict['jobid_step1'] = jobid_step1
			entry_dict['jobid_step0'] = jobid_step0
			entry_dict['username'] = username
			entry_dict['stitching_method'] = stitching_method
			entry_dict['status_step0'] = status
			entry_dict['status_step1'] = status
			entry_dict['status_step2'] = status

			""" Update the job status table in spockadmin schema"""
			logger.debug("Made it here")
			logger.debug(entry_dict)
			db_spockadmin.ProcessingPipelineSpockJob.insert1(entry_dict)    
			logger.info(f"ProcessingResolutionRequest() request was successfully submitted to spock, jobid (step 0): {jobid_step0}")
			""" Update the request tables in lightsheet schema """ 
			if no_registration_channels:
				jobid_final_step = jobid_step2
			else:
				jobid_final_step = jobid_step3 

			dj.Table._update(this_processing_resolution_content,'lightsheet_pipeline_spock_jobid',jobid_final_step)
			logger.debug("Updated spock jobid in ProcessingResolutionRequest() table")
			dj.Table._update(this_processing_resolution_content,'lightsheet_pipeline_spock_job_progress','SUBMITTED')
			logger.debug("Updated spock job progress in ProcessingResolutionRequest() table")

			""" Get the brainpipe commit and add it to processing request contents table """
			
			stdin_commit, stdout_commit, stderr_commit = client.exec_command(command_get_commit)
			brainpipe_commit = str(stdout_commit.read().decode("utf-8").strip('\n'))
			logger.debug("BRAINPIPE COMMIT")
			logger.debug(brainpipe_commit)
			dj.Table._update(this_processing_resolution_content,'brainpipe_commit',brainpipe_commit)
			logger.debug("Updated brainpipe_commit in ProcessingResolutionRequest() table")

			client.close()
	return "SUBMITTED spock job"

@cel.task()
def smartspim_stitch(**kwargs):
	""" An asynchronous celery task (runs in a background process) which
	runs a script on spock to stitch smartspim images for a given 
	imaging channel
	"""
	username=kwargs['username']
	request_name=kwargs['request_name']
	sample_name=kwargs['sample_name']
	channel_name=kwargs['channel_name']
	imaging_request_number=kwargs['imaging_request_number']
	ventral_up=kwargs['ventral_up']
	image_resolution=kwargs['image_resolution']
	rawdata_subfolder=kwargs['rawdata_subfolder']

	stitching_channel_insert_dict = {
		'username':username,
		'request_name':request_name,
		'sample_name':sample_name,
		'imaging_request_number':imaging_request_number,
		'image_resolution':image_resolution,
		'channel_name':channel_name,
		'ventral_up':ventral_up,
	}
	
	if ventral_up:
		rawdata_path = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
				username,request_name,sample_name,
				f"imaging_request_{imaging_request_number}",
				'rawdata',
				f"resolution_{image_resolution}_ventral_up",
				rawdata_subfolder)
		stitched_output_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
				username,request_name,sample_name,
				f"imaging_request_{imaging_request_number}",
				'rawdata',
				f"resolution_{image_resolution}_ventral_up",
				rawdata_subfolder + '_stitched')
	else:
		rawdata_path = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
				username,request_name,sample_name,
				f"imaging_request_{imaging_request_number}",
				'rawdata',
				f"resolution_{image_resolution}",
				rawdata_subfolder)
		stitched_output_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
				username,request_name,sample_name,
				f"imaging_request_{imaging_request_number}",
				'rawdata',
				f"resolution_{image_resolution}",
				rawdata_subfolder + '_stitched')
	# Make stitched output dir 
	mymkdir(stitched_output_dir)
	
	""" Now run spim_stitch via paramiko """

	
	processing_code_dir = os.path.join(
		current_app.config['PROCESSING_CODE_DIR'],
		'smartspim')
	pipeline_shell_script = 'spim_stitching_pipeline.sh'
	""" Set up the communication with spock """

	""" First get the git commit from brainpipe """
	command_get_commit = f'cd {processing_code_dir}; git rev-parse --short HEAD'
	
	if os.environ['FLASK_MODE'] == 'TEST' or os.environ['FLASK_MODE'] == 'DEV':        
		command = f"""cd {processing_code_dir}/testing;./test_stitching.sh"""
	else:
		command = """cd %s;%s/%s %s %s""" % \
		(
			processing_code_dir,
			processing_code_dir,
			pipeline_shell_script,
			rawdata_path,
			stitched_output_dir,
		)
	try:
		client = connect_to_spock()
	except paramiko.ssh_exception.AuthenticationException:
		logger.info(f"Failed to connect to spock to start job. ")
		stitching_channel_insert_dict['smartspim_stitching_spock_job_progress'] = 'NOT_SUBMITTED'
		db_lightsheet.Request.SmartspimStitchedChannel().insert1(
			stitching_channel_insert_dict) 
		return "FAILED"
	logger.debug("Command:")
	logger.debug(command)
	stdin, stdout, stderr = client.exec_command(command)
	response = str(stdout.read().decode("utf-8").strip('\n')) # strips off the final newline
	logger.debug("Stdout Response:")
	logger.debug(response)
	error_response = str(stderr.read().decode("utf-8"))
	if error_response:
		logger.debug("Stderr Response:")
		logger.debug(error_response)
	else:
		logger.debug("No Stderr Response")
	logger.debug("")
	status = 'SUBMITTED'
	entry_dict = {}
	jobid_step0, jobid_step1, jobid_step2, jobid_step3 = response.split('\n')
	entry_dict['username'] = username
	entry_dict['jobid_step3'] = jobid_step3
	entry_dict['jobid_step2'] = jobid_step2
	entry_dict['jobid_step1'] = jobid_step1
	entry_dict['jobid_step0'] = jobid_step0
	entry_dict['status_step0'] = status
	entry_dict['status_step1'] = status
	entry_dict['status_step2'] = status
	entry_dict['status_step3'] = status 

	""" Update the job status table in spockadmin schema """
	logger.debug(entry_dict)
	db_spockadmin.SmartspimStitchingSpockJob.insert1(entry_dict)    
	logger.info(f"SmartspimStitchingSpockJob() entry successfully inserted, jobid (step 0): {jobid_step0}")

	""" Update the request tables in lightsheet schema """ 
	jobid_final_step = jobid_step3 

	stitching_channel_insert_dict['smartspim_stitching_spock_jobid'] = jobid_final_step
	stitching_channel_insert_dict['smartspim_stitching_spock_job_progress'] = 'SUBMITTED'

	""" Get the brainpipe commit and add it to processing request contents table """
	
	stdin_commit, stdout_commit, stderr_commit = client.exec_command(command_get_commit)
	brainpipe_commit = str(stdout_commit.read().decode("utf-8").strip('\n'))
	logger.debug("BRAINPIPE COMMIT")
	logger.debug(brainpipe_commit)
	stitching_channel_insert_dict['brainpipe_commit'] = brainpipe_commit
	now = datetime.now()
	stitching_channel_insert_dict['datetime_stitching_started'] = now
	logger.debug("inserting into SmartspimStitchedChannel():")
	logger.debug(stitching_channel_insert_dict)
	db_lightsheet.Request.SmartspimStitchedChannel().insert1(
			stitching_channel_insert_dict) 
	client.close()
	return "SUBMITTED spock job"

@cel.task()
def smartspim_pystripe(**kwargs):
	""" An asynchronous celery task (runs in a background process) which
	runs a script on spock to run pystripe on smartspim images for a given 
	imaging channel
	"""
	username=kwargs['username']
	request_name=kwargs['request_name']
	sample_name=kwargs['sample_name']
	imaging_request_number=kwargs['imaging_request_number']
	channel_name=kwargs['channel_name']
	image_resolution=kwargs['image_resolution']
	ventral_up=kwargs['ventral_up']
	rawdata_subfolder=kwargs['rawdata_subfolder']
	flat_name_fullpath = kwargs['flat_name_fullpath']

	pystripe_channel_insert_dict = {
		'username':username,
		'request_name':request_name,
		'sample_name':sample_name,
		'imaging_request_number':imaging_request_number,
		'image_resolution':image_resolution,
		'channel_name':channel_name,
		'ventral_up':ventral_up,
		'flatfield_filename':os.path.basename(flat_name_fullpath),
	}
	
	if ventral_up:
		stitched_input_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
				username,request_name,sample_name,
				f"imaging_request_{imaging_request_number}",
				'rawdata',
				f"resolution_{image_resolution}_ventral_up",
				rawdata_subfolder + '_stitched')
		corrected_output_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
				username,request_name,sample_name,
				f"imaging_request_{imaging_request_number}",
				'rawdata',
				f"resolution_{image_resolution}_ventral_up",
				rawdata_subfolder + '_corrected')

		print(f"Using ventral up stitched dir: {stitched_input_dir}")
	else:
		stitched_input_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
				username,request_name,sample_name,
				f"imaging_request_{imaging_request_number}",
				'rawdata',
				f"resolution_{image_resolution}",
				rawdata_subfolder + '_stitched')
		corrected_output_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
				username,request_name,sample_name,
				f"imaging_request_{imaging_request_number}",
				'rawdata',
				f"resolution_{image_resolution}",
				rawdata_subfolder + '_corrected')
	# Make corrected output dir 
	mymkdir(corrected_output_dir)
	
	""" Now run pystripe via paramiko """
	
	processing_code_dir = os.path.join(
		current_app.config['PROCESSING_CODE_DIR'],
		'smartspim')
	pipeline_shell_script = 'spim_pystripe_pipeline.sh'
	""" Set up the communication with spock """

	""" First get the git commit from brainpipe """
	command_get_commit = f'cd {processing_code_dir}; git rev-parse --short HEAD'
	
	if os.environ['FLASK_MODE'] == 'TEST' or os.environ['FLASK_MODE'] == 'DEV' :        
		command = f"""cd {processing_code_dir}/testing; {processing_code_dir}/testing/test_pystripe.sh"""
	else:
		command = """cd %s;%s/%s %s %s %s""" % \
		(
			processing_code_dir,
			processing_code_dir,
			pipeline_shell_script,
			stitched_input_dir,
			flat_name_fullpath,
			corrected_output_dir,
		)
	
	try:
		client = connect_to_spock()
	except paramiko.ssh_exception.AuthenticationException:
		logger.info(f"Failed to connect to spock to start job. ")
		pystripe_channel_insert_dict['smartspim_stitching_spock_job_progress'] = 'NOT_SUBMITTED'

		db_lightsheet.Request.SmartspimPystripeChannel().insert1(
			pystripe_channel_insert_dict) 
		
	logger.debug("Command:")
	logger.debug(command)
	stdin, stdout, stderr = client.exec_command(command)
	response = str(stdout.read().decode("utf-8").strip('\n')) # strips off the final newline
	logger.debug("Stdout Response:")
	logger.debug(response)
	error_response = str(stderr.read().decode("utf-8"))
	if error_response:
		logger.debug("Stderr Response:")
		logger.debug(error_response)
	else:
		logger.debug("No Stderr Response")
	logger.debug("")
	jobid_step0 = response.split('\n')
	status = 'SUBMITTED'
	entry_dict = {}
	entry_dict['username'] = username
	entry_dict['jobid_step0'] = jobid_step0
	entry_dict['status_step0'] = status

	""" Update the job status table in spockadmin schema """
	logger.debug(entry_dict)
	db_spockadmin.SmartspimPystripeSpockJob.insert1(entry_dict)    
	logger.info(f"SmartspimPystripeSpockJob() entry successfully inserted, jobid (step 0): {jobid_step0}")

	""" Update the request tables in lightsheet schema """ 

	pystripe_channel_insert_dict['smartspim_pystripe_spock_jobid'] = jobid_step0
	pystripe_channel_insert_dict['smartspim_pystripe_spock_job_progress'] = 'SUBMITTED'

	now = datetime.now()
	pystripe_channel_insert_dict['datetime_pystripe_started'] = now
	logger.debug("inserting into SmartspimPystripeChannel():")
	logger.debug(pystripe_channel_insert_dict)
	db_lightsheet.Request.SmartspimPystripeChannel().insert1(
			pystripe_channel_insert_dict,replace=True) 
	client.close()
	return "SUBMITTED pystripe spock job"


@cel.task()
def make_precomputed_stitched_data(**kwargs):
	""" Celery task for making precomputed dataset
	(i.e. one that can be read by cloudvolume) from 
	stitched image data after it has been stitched.  

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
	ventral_up=kwargs['ventral_up']
	channel_index=kwargs['channel_index']
	image_resolution=kwargs['image_resolution']
	lightsheet=kwargs['lightsheet']
	rawdata_subfolder=kwargs['rawdata_subfolder']
	viz_dir = kwargs['viz_dir'] 
	processing_pipeline_jobid_step0 = kwargs['processing_pipeline_jobid_step0']

	if ventral_up:
		rawdata_path = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
				username,request_name,sample_name,
				f"imaging_request_{imaging_request_number}",
				"rawdata",
				f"resolution_{image_resolution}_ventral_up",
				rawdata_subfolder)
	else:
		rawdata_path = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
				username,request_name,sample_name,
				f"imaging_request_{imaging_request_number}",
				"rawdata",
				f"resolution_{image_resolution}",
				rawdata_subfolder)
	kwargs['rawdata_path'] = rawdata_path

	""" construct the terastitcher output path """
	channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
	logger.debug("CHANNEL INDEX PADDED")
	logger.debug(channel_index_padded)
	logger.debug("Search string:")
	logger.debug(rawdata_path + f'/*_ch{channel_index_padded}_{lightsheet}_lightsheet_ts_out')
	logger.debug(glob.glob(rawdata_path + '/*ts_out'))
	terastitcher_output_parent_dirs = glob.glob(rawdata_path + f'/*_ch{channel_index_padded}_{lightsheet}_lightsheet_ts_out')
	
	terastitcher_output_parent_dir = terastitcher_output_parent_dirs[0]
	logger.debug("TERASTITCHER OUTPUT DIRECTORY:")
	logger.debug(terastitcher_output_parent_dir)
	""" Find the deepest directory in the terastitcher output folder hierarchy.
	That directory contains the stitched tif files at each z plane """
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
	kwargs['slurmjobfactor'] = slurmjobfactor
	
	pickle_fullpath = viz_dir + '/precomputed_params.p'
	with open(pickle_fullpath,'wb') as pkl_file:
		pickle.dump(kwargs,pkl_file)
	logger.debug(f'Saved precomputed pickle file: {pickle_fullpath} ')

	# """ Now set up the connection to spock """
	if os.environ['FLASK_MODE'] == 'TEST':
		command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_precomputed_stitching_script.sh "
	else:
		command = ("cd /jukebox/wang/ahoag/precomputed/stitched_pipeline; "
				   f"/jukebox/wang/ahoag/precomputed/stitched_pipeline/precomputed_pipeline_stitched.sh {viz_dir}")
		# command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_pipeline.sh "
	
	client = connect_to_spock()
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
				'processing_pipeline_jobid_step0':processing_pipeline_jobid_step0
				}
	logger.debug("Inserting into StitchedPrecomputedSpockJob():")
	logger.debug(entry_dict)
	db_spockadmin.StitchedPrecomputedSpockJob.insert1(entry_dict)    
	logger.info(f"Precomputed (stitched data) job inserted into StitchedPrecomputedSpockJob() table: {entry_dict}")
	logger.info(f"Precomputed (stitched data) job successfully submitted to spock, jobid_step2: {jobid_step2}")
	# logger.debug(type(jobid_step2))
	restrict_dict = dict(
		username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number,
		image_resolution=image_resolution,channel_name=channel_name)
	this_processing_channel_content = db_lightsheet.Request.ProcessingChannel() & restrict_dict 
	try:
		if lightsheet == 'left':
			dj.Table._update(this_processing_channel_content,'left_lightsheet_stitched_precomputed_spock_jobid',str(jobid_step2))
			dj.Table._update(this_processing_channel_content,'left_lightsheet_stitched_precomputed_spock_job_progress','SUBMITTED')
		else:
			dj.Table._update(this_processing_channel_content,'right_lightsheet_stitched_precomputed_spock_jobid',str(jobid_step2))
			dj.Table._update(this_processing_channel_content,'right_lightsheet_stitched_precomputed_spock_job_progress','SUBMITTED')
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
	ventral_up=kwargs['ventral_up']
	channel_name=kwargs['channel_name']
	channel_index=kwargs['channel_index']
	image_resolution=kwargs['image_resolution']
	z_step=kwargs['z_step']

	viz_dir = kwargs['viz_dir'] 
	logger.debug("Visualization directory:")
	logger.debug(viz_dir)
	processing_pipeline_jobid_step0 = kwargs['processing_pipeline_jobid_step0']
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
	kwargs['slurmjobfactor'] = slurmjobfactor
	pickle_fullpath = viz_dir + '/precomputed_params.p'
	with open(pickle_fullpath,'wb') as pkl_file:
		pickle.dump(kwargs,pkl_file)

	logger.debug(f'Saved precomputed pickle file: {pickle_fullpath} ')
	if os.environ['FLASK_MODE'] == 'TEST':
		command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_precomputed_blended_script.sh "
	else:
		command = ("cd /jukebox/wang/ahoag/precomputed/blended_pipeline; "
				   f"/jukebox/wang/ahoag/precomputed/blended_pipeline/precomputed_pipeline_blended.sh {viz_dir}")   # command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_pipeline.sh "
	client = connect_to_spock()
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
				'processing_pipeline_jobid_step0':processing_pipeline_jobid_step0
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
		image_resolution=image_resolution,channel_name=channel_name,
		ventral_up=ventral_up)
	this_processing_channel_content = db_lightsheet.Request.ProcessingChannel() & restrict_dict 
	try:
		dj.Table._update(this_processing_channel_content,'blended_precomputed_spock_jobid',str(jobid_step2))
		dj.Table._update(this_processing_channel_content,'blended_precomputed_spock_job_progress','SUBMITTED')
	except:
		logger.info("Unable to update ProcessingChannel() table")
	return "Finished task submitting precomputed pipeline for blended data"

@cel.task()
def make_precomputed_downsized_data(**kwargs):
	""" Celery task for making precomputed dataset
	(i.e. one that can be read by cloudvolume) from 
	downsized image data for a single channel.  

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
	ventral_up=kwargs['ventral_up']

	channel_index=kwargs['channel_index']
	image_resolution=kwargs['image_resolution']
	rawdata_subfolder=kwargs['rawdata_subfolder']
	viz_dir = kwargs['viz_dir'] 
	logger.debug("Visualization directory:")
	logger.debug(viz_dir)
	processing_pipeline_jobid_step0 = kwargs['processing_pipeline_jobid_step0']
	downsized_data_path = kwargs['downsized_data_path']
	logger.debug("downsized data path is:")
	logger.debug(downsized_data_path)
	""" downsized data will have same dimesions
	as whichever atlas was used """
	
	kwargs['layer_name'] = f'channel{channel_name}_downsized'
	
	pickle_fullpath = viz_dir + '/precomputed_params.p'
	with open(pickle_fullpath,'wb') as pkl_file:
		pickle.dump(kwargs,pkl_file)

	logger.debug(f'Saved precomputed pickle file: {pickle_fullpath} ')
	if os.environ['FLASK_MODE'] == 'TEST':
		command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_precomputed_downsized_script.sh "
	else:
		command = ("cd /jukebox/wang/ahoag/precomputed/downsized_pipeline; "
				   "/jukebox/wang/ahoag/precomputed/downsized_pipeline/precomputed_pipeline_downsized.sh {}").format(
			viz_dir)

		# command = "cd /jukebox/wang/ahoag/precomputed/downsized_pipeline/testing; ./test_pipeline.sh "
	logger.debug("command:")
	logger.debug(command)
	client = connect_to_spock()
	stdin, stdout, stderr = client.exec_command(command)
	# jobid_final_step = str(stdout.read().decode("utf-8").strip('\n'))
	response = str(stdout.read().decode("utf-8").strip('\n')) # strips off the final newline
	logger.debug("response from spock:")
	logger.debug(response)
	jobid_step0, jobid_step1 = response.split('\n')

	status_step0 = 'SUBMITTED'
	status_step1 = 'SUBMITTED'
	entry_dict   = {
				'jobid_step0':jobid_step0,
				'jobid_step1':jobid_step1,
				'username':username,'status_step0':status_step0,
				'status_step1':status_step1,
				'processing_pipeline_jobid_step0':processing_pipeline_jobid_step0
				}
	logger.debug("Inserting into DownsizedPrecomputedSpockJob():")
	logger.debug(entry_dict)
	db_spockadmin.DownsizedPrecomputedSpockJob.insert1(entry_dict)    
	logger.info(f"Precomputed (downsized data) job inserted into DownsizedPrecomputedSpockJob() table: {entry_dict}")
	logger.info(f"Precomputed (downsized data) job successfully submitted to spock, jobid_step1: {jobid_step1}")
	restrict_dict = dict(
		username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number,
		image_resolution=image_resolution,channel_name=channel_name,
		ventral_up=ventral_up)
	this_processing_channel_content = db_lightsheet.Request.ProcessingChannel() & restrict_dict 
	try:
		dj.Table._update(this_processing_channel_content,'downsized_precomputed_spock_jobid',str(jobid_step1))
		dj.Table._update(this_processing_channel_content,'downsized_precomputed_spock_job_progress','SUBMITTED')
	except:
		logger.info("Unable to update ProcessingChannel() table")
	return "Finished task submitting precomputed pipeline for downsized data"

@cel.task()
def make_precomputed_registered_data(**kwargs):
	""" Celery task for making precomputed dataset
	(i.e. one that can be read by cloudvolume) from 
	registered image data for a single channel.  

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
	ventral_up=kwargs['ventral_up']
	channel_index=kwargs['channel_index']
	atlas_name = kwargs['atlas_name']
	image_resolution=kwargs['image_resolution']
	viz_dir = kwargs['viz_dir'] 
	logger.debug("Visualization directory:")
	logger.debug(viz_dir)
	processing_pipeline_jobid_step0 = kwargs['processing_pipeline_jobid_step0']
	registered_data_path = kwargs['registered_data_path']
	logger.debug("registered data path is:")
	logger.debug(registered_data_path)
	
	slurmjobfactor = 20 # the number of processes to run per core

	kwargs['slurmjobfactor'] = slurmjobfactor
	
	pickle_fullpath = viz_dir + '/precomputed_params.p'
	with open(pickle_fullpath,'wb') as pkl_file:
		pickle.dump(kwargs,pkl_file)

	logger.debug(f'Saved precomputed pickle file: {pickle_fullpath} ')
	if os.environ['FLASK_MODE'] == 'TEST':
		command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_precomputed_registered_script.sh "
	else:
		command = ("cd /jukebox/wang/ahoag/precomputed/registered_pipeline; "
				   "/jukebox/wang/ahoag/precomputed/registered_pipeline/precomputed_pipeline_registered.sh {}").format(
			viz_dir)
		# command = "cd /jukebox/wang/ahoag/precomputed/registered_pipeline/testing; ./test_pipeline.sh "
	logger.debug("command:")
	logger.debug(command)
	
	client = connect_to_spock()

	stdin, stdout, stderr = client.exec_command(command)
	response = str(stdout.read().decode("utf-8").strip('\n')) # strips off the final newline
	logger.debug("response from spock:")
	logger.debug(response)
	jobid_step0, jobid_step1 = response.split('\n')

	status_step0 = 'SUBMITTED'
	status_step1 = 'SUBMITTED'
	entry_dict   = {
				'jobid_step0':jobid_step0,
				'jobid_step1':jobid_step1,
				'username':username,'status_step0':status_step0,
				'status_step1':status_step1,
				'processing_pipeline_jobid_step0':processing_pipeline_jobid_step0
				}
	logger.debug("Inserting into RegisteredPrecomputedSpockJob():")
	logger.debug(entry_dict)
	db_spockadmin.RegisteredPrecomputedSpockJob.insert1(entry_dict)    
	logger.info(f"Precomputed (registered data) job inserted into RegisteredPrecomputedSpockJob() table: {entry_dict}")
	logger.info(f"Precomputed (registered data) job successfully submitted to spock, jobid_step1: {jobid_step1}")
	restrict_dict = dict(
		username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number,
		image_resolution=image_resolution,channel_name=channel_name,
		ventral_up=ventral_up)
	this_processing_channel_content = db_lightsheet.Request.ProcessingChannel() & restrict_dict 
	try:
		dj.Table._update(this_processing_channel_content,'registered_precomputed_spock_jobid',str(jobid_step1))
		dj.Table._update(this_processing_channel_content,'registered_precomputed_spock_job_progress','SUBMITTED')
	except:
		logger.info("Unable to update ProcessingChannel() table")
	return "Finished task submitting precomputed pipeline for registered data"

@cel.task()
def make_precomputed_smartspim_corrected_data(**kwargs):
	""" Celery task for making precomputed dataset
	(i.e. one that can be read by cloudvolume) from 
	corrected smartspim image data after pystripe has been run.  

	Spawns a series of spock jobs for handling
	the actual computation
	"""
	
	""" Read in keys """
	username = kwargs['username']
	request_name = kwargs['request_name']
	sample_name = kwargs['sample_name']
	imaging_request_number = kwargs['imaging_request_number']
	image_resolution = kwargs['image_resolution']
	channel_name = kwargs['channel_name']
	ventral_up = kwargs['ventral_up']
	# Figure out z step from ImagingChannel() entry
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & kwargs
	z_step = imaging_channel_contents.fetch1('z_step') # microns

	all_channels_smartspim = current_app.config["SMARTSPIM_IMAGING_CHANNELS"]
	channel_index = all_channels_smartspim.index(channel_name)
	if ventral_up:
		image_resolution_subfolder = f"resolution_{image_resolution}_ventral_up"
		layer_name = f"channel_{channel_name}_corrected_ventral_up"
	else:
		image_resolution_subfolder = f"resolution_{image_resolution}"
		layer_name = f"channel_{channel_name}_corrected"
	data_bucket_rootpath = current_app.config["DATA_BUCKET_ROOTPATH"]

	blended_data_path = os.path.join(data_bucket_rootpath,
		username,request_name,sample_name,
		f"imaging_request_{imaging_request_number}",
		"rawdata",
		image_resolution_subfolder,
		f"Ex_{channel_name}_Em_{channel_index}_corrected")
	viz_dir = os.path.join(data_bucket_rootpath,
		username,request_name,sample_name,
		f"imaging_request_{imaging_request_number}",
		"viz","rawdata")
	mymkdir(viz_dir)
	
	pickle_kwargs = dict(blended_data_path=blended_data_path,
		layer_name=layer_name,
		image_resolution=image_resolution,
		z_step=z_step)
	
	pickle_fullpath = viz_dir + f'/precomputed_params_{image_resolution}_ch{channel_name}.p'
	with open(pickle_fullpath,'wb') as pkl_file:
		pickle.dump(pickle_kwargs,pkl_file)
	
	logger.debug(f'Saved precomputed pickle file: {pickle_fullpath} ')

	# """ Now set up the connection to spock """
	if os.environ['FLASK_MODE'] == 'TEST' or os.environ['FLASK_MODE'] == 'DEV' :
		command = "cd /jukebox/wang/ahoag/precomputed/smartspim/testing; ./test_precomputed_corrected_script.sh "
	else:
		command = ("cd /jukebox/wang/ahoag/precomputed/smartspim/corrected_pipeline; "
				   f"/jukebox/wang/ahoag/precomputed/smartspim/corrected_pipeline/precomputed_pipeline_corrected.sh "
				   f"{viz_dir} {image_resolution} {channel_name}")
	
	client = connect_to_spock()

	stdin, stdout, stderr = client.exec_command(command)
	response = str(stdout.read().decode("utf-8").strip('\n')) # strips off the final newline
	logger.debug("response from spock:")
	logger.debug(response)
	jobid_step0, jobid_step1, jobid_step2, jobid_step3  = response.split('\n')

	status_step0 = 'SUBMITTED'
	status_step1 = 'SUBMITTED'
	status_step2 = 'SUBMITTED'
	status_step3 = 'SUBMITTED'
	entry_dict   = {
				'username':username,
				'jobid_step0':jobid_step0,
				'jobid_step1':jobid_step1,
				'jobid_step2':jobid_step2,
				'jobid_step3':jobid_step3,
				'status_step0':status_step0,
				'status_step1':status_step1,'status_step2':status_step2,
				'status_step3':status_step3,
				}
	logger.debug("Inserting into SmartspimCorrectedPrecomputedSpockJob():")
	logger.debug(entry_dict)
	db_spockadmin.SmartspimCorrectedPrecomputedSpockJob.insert1(entry_dict)    
	logger.info(f"Precomputed (corrected data) job inserted into SmartspimCorrectedPrecomputedSpockJob() table: {entry_dict}")
	logger.info(f"Precomputed (corrected data) job successfully submitted to spock, jobid_step3: {jobid_step3}")
	
	# Now insert into SmartspimPystripeChannel() table
	restrict_dict_pystripe_table = dict(
		username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		image_resolution=image_resolution,channel_name=channel_name,
		ventral_up=ventral_up)
	this_pystripe_channel_content = db_lightsheet.Request.SmartspimPystripeChannel() &\
		restrict_dict_pystripe_table 
	dj.Table._update(this_pystripe_channel_content,'smartspim_corrected_precomputed_spock_jobid',
		str(jobid_step3))
	dj.Table._update(this_pystripe_channel_content,'smartspim_corrected_precomputed_spock_job_progress',
		"SUBMITTED")
	return "Finished task submitting precomputed pipeline for SmartSPIM corrected data"


#################################################
##### Tasks that will be scheduled regularly ####
#################################################

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
	all_processing_request_contents = db_lightsheet.Request.ProcessingRequest()
   
	""" First get all rows with latest timestamps """
	job_contents = db_spockadmin.ProcessingPipelineSpockJob()
	unique_contents = dj.U('jobid_step0','username',).aggr(
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
	logger.debug(f"Outstanding job ids are: {jobids_str}")
	
	try:
		client = connect_to_spock()
	except:
		logger.debug("Something went wrong connecting to spock.")
		return "Error connecting to spock"
	logger.debug("connected to spock")
	# try:
	command = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(jobids_str)
	logger.debug("Running command on spock:")
	logger.debug(command)
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

	""" Loop through outstanding jobs and determine their statuses """
	for jobid,indices_list in job_status_indices_dict.items():
		logger.debug(f"Working on jobid={jobid}")
		job_insert_dict = {'jobid_step3':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
		status_step3 = determine_status_code(status_codes)
		logger.debug(f"Status code for this job is: {status_step3}")
		job_insert_dict['status_step3'] = status_step3
		""" Find the username, other jobids associated with this jobid """
		(username_thisjob,jobid_step0,jobid_step1,
			jobid_step2,stitching_method) = (unique_contents & f'jobid_step3={jobid}').fetch1(
			'username','jobid_step0','jobid_step1','jobid_step2','stitching_method')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		job_insert_dict['jobid_step1']=jobid_step1
		job_insert_dict['jobid_step2']=jobid_step2
		job_insert_dict['stitching_method']=stitching_method
		jobid_step_dict = {'step0':jobid_step0,'step1':jobid_step1,'step2':jobid_step2}

		""" Get the processing resolution entry associated with this jobid
		and update the progress """
		this_processing_resolution_content = db_lightsheet.Request.ProcessingResolutionRequest() & \
		f'lightsheet_pipeline_spock_jobid={jobid}'
		if len(this_processing_resolution_content) == 0:
			logger.debug("No ProcessingResolutionRequest() associated with this jobid. Skipping")
			continue
		logger.debug("this processing resolution content:")
		logger.debug(this_processing_resolution_content)
		dj.Table._update(this_processing_resolution_content,
			'lightsheet_pipeline_spock_job_progress',status_step3)
		logger.debug("Updated lightsheet_pipeline_spock_job_progress in ProcessingResolutionRequest() table ")
		
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
		logger.debug("looping through steps 0-2 to figure out statuses")
		for step_counter in range(3):
		# for jobid_earlier_step,indices_list_earlier_step in job_status_indices_dict_earlier_steps.items():
			step = f'step{step_counter}'
			jobid_earlier_step = jobid_step_dict[step]
			indices_list_earlier_step = job_status_indices_dict_earlier_steps[jobid_earlier_step]
			status_codes_earlier_step = [status_codes_received_earlier_steps[ii] for ii in indices_list_earlier_step]
			status = determine_status_code(status_codes_earlier_step)
			status_step_str = f'status_step{step_counter}'
			job_insert_dict[status_step_str] = status
			logger.debug(f"status of {step} is {status}")
			step_counter +=1 
		logger.debug("done with earlier steps")
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
			""" Find all processing channels from this same processing resolution request """
			logger.debug("checking to see whether all processing resolution requests "
						 "are complete in this processing request are complete")
			restrict_dict_processing = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number)
			processing_request_contents = all_processing_request_contents & restrict_dict_processing
			processing_resolution_contents = db_lightsheet.Request.ProcessingResolutionRequest() & \
				restrict_dict_processing
			
			""" Loop through and pool all of the job statuses """
			processing_request_job_statuses = []
			
			for processing_resolution_dict in processing_resolution_contents:
				job_status = processing_resolution_dict['lightsheet_pipeline_spock_job_progress']
				processing_request_job_statuses.append(job_status)

			logger.debug("job statuses for this processing request:")
			logger.debug(processing_request_job_statuses)
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
				
				restrict_dict_request = {'username':username,'request_name':request_name}
				request_contents = db_lightsheet.Request() & restrict_dict_request
				
				dj.Table._update(processing_request_contents,'processing_progress','complete')
				""" Now figure out if all other processing requests for this request have been
				fulfilled. If so, email the user """
				processing_requests = db_lightsheet.Request.ProcessingRequest() & restrict_dict_request
				processing_progresses = processing_requests.fetch('processing_progress')
				logger.debug("processing progresses for this request:")
				logger.debug(processing_progresses)
				if all([x=='complete' for x in processing_progresses]):
					logger.debug("All processing requests complete in this request. Sending email to user.")
					processed_products_directory = os.path.join(data_bucket_rootpath,username,
							 request_name,'$sample_name',
							 f"imaging_request_{imaging_request_number}",
							 "output",
							 f"processing_request_{processing_request_number}")
					subject = 'Lightserv automated email: Processing done.'
					body = ('The processing is now complete for all samples in your request:\n\n'
							f'username: {username}\n'
							f'request_name: {request_name}\n\n'
							f'The processed products are available in each sample directory: {processed_products_directory}')
					correspondence_email = request_contents.fetch1('correspondence_email')
					recipients = [correspondence_email]
					if not os.environ['FLASK_MODE'] == 'TEST':
						send_email.delay(subject=subject,body=body,recipients=recipients)
					dj.Table._update(request_contents,'sent_processing_email',True)
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

	return "Checked processing job statuses"

@cel.task()
def processing_job_status_checker_noreg():
	""" 
	A celery task that will be run in a schedule

	Checks the job statuses for the 
	processing pipeline where we did not run step 3 on spock
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
	all_processing_request_contents = db_lightsheet.Request.ProcessingRequest()
   
	""" First get all rows with latest timestamps """
	job_contents = db_spockadmin.ProcessingPipelineSpockJob() & \
		'jobid_step3 is NULL'
	unique_contents = dj.U('jobid_step0','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents 

	""" Get a list of all jobs we need to check up on, i.e.
	those that could conceivably change. Also list the problematic_codes
	which will be used later for error reporting to the user.
	"""

	# static_codes = ('COMPLETED','FAILED','BOOT_FAIL','CANCELLED','DEADLINE','OUT_OF_MEMORY','REVOKED')
	ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
	incomplete_contents = unique_contents & f'status_step2 in {ongoing_codes}'
	jobids = list(incomplete_contents.fetch('jobid_step2'))
	if jobids == []:
		return "No jobs to check"
	jobids_str = ','.join(str(jobid) for jobid in jobids)
	logger.debug(f"Outstanding job ids are: {jobids}")
	
	try:
		client = connect_to_spock()
	except:
		logger.debug("Something went wrong connecting to spock.")
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
		job_insert_dict = {'jobid_step2':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
		status_step2 = determine_status_code(status_codes)
		logger.debug(f"Status code for this job is: {status_step2}")
		job_insert_dict['status_step2'] = status_step2
		""" Find the username, other jobids associated with this jobid """
		(username_thisjob,jobid_step0,
			jobid_step1,stitching_method) = (unique_contents & f'jobid_step2={jobid}').fetch1(
			'username','jobid_step0','jobid_step1','stitching_method')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		job_insert_dict['jobid_step1']=jobid_step1
		job_insert_dict['stitching_method']=stitching_method
		
		jobid_step_dict = {'step0':jobid_step0,'step1':jobid_step1}

		""" Get the imaging channel entry associated with this jobid
		and update the progress """
		this_processing_resolution_content = db_lightsheet.Request.ProcessingResolutionRequest() & \
		f'lightsheet_pipeline_spock_jobid={jobid}'
		logger.debug("this processing resolution content:")
		logger.debug(this_processing_resolution_content)
		dj.Table._update(this_processing_resolution_content,
			'lightsheet_pipeline_spock_job_progress',status_step2)
		logger.debug("Updated lightsheet_pipeline_spock_job_progress in ProcessingResolutionRequest() table ")
		
		""" Now figure out the status codes for the earlier dependency jobs """
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
		""" Loop through the earlier steps and figure out their statuses """
		for step_counter in range(2):
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
		if status_step2 == 'COMPLETED':
			""" Find all processing channels from this same processing request """
			restrict_dict_imaging = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number)
			imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict_imaging
			restrict_dict_processing = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number)
			processing_resolution_contents = db_lightsheet.Request.ProcessingResolutionRequest() & \
				restrict_dict_processing
			processing_request_contents = all_processing_request_contents & restrict_dict_processing
			# logger.debug(processing_channel_contents)
			""" Loop through and pool all of the job statuses """
			processing_request_job_statuses = []
			for processing_resolution_dict in processing_resolution_contents:
				job_status = processing_resolution_dict['lightsheet_pipeline_spock_job_progress']
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
				restrict_dict_request = {'username':username,'request_name':request_name}
				request_contents = db_lightsheet.Request() & restrict_dict_request
				correspondence_email = request_contents.fetch1('correspondence_email')
				recipients = [correspondence_email]
				if not os.environ['FLASK_MODE'] == 'TEST':
					send_email.delay(subject=subject,body=body,recipients=recipients)
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


	return "Checked processing job statuses"

@cel.task()
def smartspim_stitching_job_status_checker():
	""" 
	A celery task that will be run in a schedule

	Checks all outstanding smartspim stitching job statuses on spock
	and updates their status in the db_spockadmin.SmartspimStitchingSpockJob()
	in db_spockadmin
	and SmartspimStitchedChannel() in db_lightsheet.

	When the stitching pipeline is done, check to 
	see if all channels in this resolution request are 
	done stitching. If so, send the email to user
	saying their data are stitched.

	When one channel is done start the  
	stitching precomputed pipeline 

	"""
	all_stitching_entries = db_lightsheet.Request.SmartspimStitchedChannel()
   
	""" First get all rows with latest timestamps """
	job_contents = db_spockadmin.SmartspimStitchingSpockJob()
	unique_contents = dj.U('jobid_step0','username',).aggr(
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
	
	client = connect_to_spock()
	
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
		(username_thisjob,jobid_step0,jobid_step1,
			jobid_step2) = (unique_contents & f'jobid_step3={jobid}').fetch1(
			'username','jobid_step0','jobid_step1','jobid_step2')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		job_insert_dict['jobid_step1']=jobid_step1
		job_insert_dict['jobid_step2']=jobid_step2
		jobid_step_dict = {'step0':jobid_step0,'step1':jobid_step1,'step2':jobid_step2}

		""" Get the lightsheet SmartspimStitchedChannel() entry associated with this jobid
		and update the progress """
		this_stitching_content = all_stitching_entries & \
			f'smartspim_stitching_spock_jobid={jobid}'
		if len(this_stitching_content) == 0:
			logger.debug("No entry found in SmartspimStitchedChannel() table")
			continue
		logger.debug("this stitching content:")
		logger.debug(this_stitching_content)
		dj.Table._update(this_stitching_content,
			'smartspim_stitching_spock_job_progress',status_step3)
		logger.debug("Updated smartspim_stitching_spock_job_progress in SmartspimStitchedChannel() table ")
		
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
		logger.debug("looping through steps 0-2 to figure out statuses")
		for step_counter in range(3):
		# for jobid_earlier_step,indices_list_earlier_step in job_status_indices_dict_earlier_steps.items():
			step = f'step{step_counter}'
			jobid_earlier_step = jobid_step_dict[step]
			indices_list_earlier_step = job_status_indices_dict_earlier_steps[jobid_earlier_step]
			status_codes_earlier_step = [status_codes_received_earlier_steps[ii] for ii in indices_list_earlier_step]
			status = determine_status_code(status_codes_earlier_step)
			status_step_str = f'status_step{step_counter}'
			job_insert_dict[status_step_str] = status
			logger.debug(f"status of {step} is {status}")
			step_counter +=1 
		logger.debug("done with earlier steps")
		""" If this pipeline run is now 100 percent complete,
		figure out if all of the other pipeline runs 
		that exist for this same processing request
		are also complete.
		If so, then update the processing progress 
		and email the user"""
		
		if status_step3 == 'COMPLETED':
			# update datetime stitching completed
			this_stitching_content = all_stitching_entries & \
				f'smartspim_stitching_spock_jobid={jobid}'
			now = datetime.now()			
			dj.Table._update(this_stitching_content,
				'datetime_stitching_completed',now)
			logger.debug("Updated datetime_stitching_completed in SmartspimStitchedChannel() table ")

		job_insert_list.append(job_insert_dict)

	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_spockadmin.SmartspimStitchingSpockJob.insert(job_insert_list)
	logger.debug("Entry in SmartspimStitchingSpockJob() admin table with latest status")

	client.close()

	# for each running process, find all jobids in the processing resolution request tables
	return "Checked processing job statuses"

@cel.task()
def smartspim_pystripe_job_status_checker():
	""" 
	A celery task that will be run in a schedule

	Checks all outstanding smartspim pystripe job statuses on spock
	and updates their status in the db_spockadmin.SmartspimPystripeSpockJob()
	in db_spockadmin
	and SmartspimPystripeChannel() in db_lightsheet.

	When the pystripe pipeline is done, check to 
	see if all channels in this sample are 
	done stitching. If so, send the email to user/admins
	saying the data are pystriped.
 

	"""
	all_pystripe_entries = db_lightsheet.Request.SmartspimPystripeChannel()
   
	""" First get all rows with latest timestamps """
	job_contents = db_spockadmin.SmartspimPystripeSpockJob()
	unique_contents = dj.U('jobid_step0','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	""" Get a list of all jobs we need to check up on, i.e.
	those that could conceivably change. Also list the problematic_codes
	which will be used later for error reporting to the user.
	"""

	# static_codes = ('COMPLETED','FAILED','BOOT_FAIL','CANCELLED','DEADLINE','OUT_OF_MEMORY','REVOKED')
	ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
	incomplete_contents = unique_contents & f'status_step0 in {ongoing_codes}'
	jobids = list(incomplete_contents.fetch('jobid_step0'))
	if jobids == []:
		return "No jobs to check"
	jobids_str = ','.join(str(jobid) for jobid in jobids)
	logger.debug(f"Outstanding job ids are: {jobids}")
	
	client = connect_to_spock()
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
		job_insert_dict = {'jobid_step0':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
		status_step0 = determine_status_code(status_codes)
		logger.debug(f"Status code for this job is: {status_step0}")
		job_insert_dict['status_step0'] = status_step0
		""" Find the username, other jobids associated with this jobid """
		username_thisjob = (unique_contents & f'jobid_step0={jobid}').fetch1(
			'username')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['jobid_step0']=jobid

		""" Get the lightsheet SmartspimPystripeChannel() entry associated with this jobid
		and update the progress """
		this_pystripe_content = all_pystripe_entries & \
			f'smartspim_pystripe_spock_jobid={jobid}'
		if len(this_pystripe_content) == 0:
			logger.debug("No entry found in SmartspimPystripeChannel() table")
			continue
		logger.debug("this pystripe content:")
		logger.debug(this_pystripe_content)
		pystripe_dict = this_pystripe_content.fetch1()
		pystripe_dict['smartspim_pystripe_spock_job_progress'] = status_step0
		this_pystripe_content.delete_quick()
		db_lightsheet.Request.SmartspimPystripeChannel().insert1(pystripe_dict)
		### Datajoint bug in _update -- FIXME by upgrading to dj v0.13.1
		# dj.Table._update(this_pystripe_content,
		# 	'smartspim_pystripe_spock_job_progress',status_step0)
		logger.debug("Updated SmartspimPystripeChannel() entry with current job status")
		
		if status_step0 == 'COMPLETED':
			# Update SmartspimPystripeChannel() entry to indicate that pystripe is complete
			this_pystripe_content = all_pystripe_entries & \
			f'smartspim_pystripe_spock_jobid={jobid}'
			this_pystripe_dict = this_pystripe_content.fetch1()
			this_pystripe_dict['pystripe_performed'] = 1
			this_pystripe_content.delete_quick()
			db_lightsheet.Request.SmartspimPystripeChannel().insert1(pystripe_dict)
			# dj.Table._update(this_pystripe_content,
			# 'pystripe_performed',1)
			logger.debug("Pystripe complete, marked pystripe_performed=1 in SmartspimPystripeChannel() channel")
			# Launch precomputed pipeline for corrected blended images
			# this_pystripe_dict = this_pystripe_content.fetch1()
			username = this_pystripe_dict['username']
			request_name = this_pystripe_dict['request_name']
			sample_name = this_pystripe_dict['sample_name']
			imaging_request_number = this_pystripe_dict['imaging_request_number']
			image_resolution = this_pystripe_dict['image_resolution']
			channel_name = this_pystripe_dict['channel_name']
			ventral_up = this_pystripe_dict['ventral_up']
			
			precomputed_kwargs = dict(
				username = username,
				request_name = request_name,
				sample_name = sample_name,
				imaging_request_number = imaging_request_number,
				image_resolution = image_resolution,
				channel_name = channel_name,
				ventral_up = ventral_up)

			make_precomputed_smartspim_corrected_data.delay(**precomputed_kwargs)

			logger.info("Started precomputed job for corrected data")

			""" Find all SmartspimPystripeChannel() entries from this same sample_name """
			logger.debug("checking to see whether all channels in this sample name "
						 "have completed pystripe")
			(username,request_name,sample_name,imaging_request_number,image_resolution) = this_pystripe_content.fetch1(
					"username","request_name","sample_name",
					"imaging_request_number","image_resolution")
			restrict_dict_imaging_channel = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number)
			imaging_channel_contents = \
				db_lightsheet.Request.ImagingChannel() & \
				restrict_dict_imaging_channel
			ventral_up_allchannels = imaging_channel_contents.fetch('ventral_up')

			pystripe_channel_contents = \
				db_lightsheet.Request.SmartspimPystripeChannel() & \
				restrict_dict_imaging_channel
			""" Loop through and pool all of the job statuses """
			pystripe_job_statuses = pystripe_channel_contents.fetch(
				'smartspim_pystripe_spock_job_progress')
		
			data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
			if any(ventral_up_allchannels):
				output_directory = os.path.join(data_bucket_rootpath,username,
								 request_name,sample_name,
								 f"imaging_request_{imaging_request_number}",
								 "rawdata",
								 f"resolution_{image_resolution}_ventral_up")
			else:
				output_directory = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "rawdata",
							 f"resolution_{image_resolution}")

			if all(x=='COMPLETED' for x in pystripe_job_statuses) and \
				len(pystripe_job_statuses) == len(imaging_channel_contents):
				if len(pystripe_channel_contents) > 1:
					all_channels_pystripe_list = pystripe_channel_contents.fetch('channel_name')
					all_channels_pystripe = ', '.join(all_channels_pystripe_list) 
				else:
					all_channels_pystripe = pystripe_channel_contents.fetch1('channel_name')
				logger.debug("The pystripe pipeline for all channels"
							 " in this imaging request are complete!")
				subject = 'Lightserv automated email: Preprocessed SmartSPIM images ready'
				body = ('All images for your sample:\n\n'
						f'request_name: {request_name}\n'
						f'sample_name: {sample_name}\n'
						'are done preprocessing.   \n\n'
						'The preprocessed image TIFF stacks are available for each channel in the *_corrected/ subfolders '
						f'on bucket here: {output_directory}')
				restrict_dict_request = {'username':username,'request_name':request_name}
				request_contents = db_lightsheet.Request() & restrict_dict_request
				correspondence_email = request_contents.fetch1('correspondence_email')
				recipients = [correspondence_email]
				if not os.environ['FLASK_MODE'] == 'TEST':
					pass
					# send_email.delay(subject=subject,body=body,recipients=recipients)

			else:
				logger.debug("Not all channels in this "
							 "imaging request are done being pystriped")

		job_insert_list.append(job_insert_dict)

	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_spockadmin.SmartspimPystripeSpockJob.insert(job_insert_list)
	logger.debug("Entry in SmartspimPystripeSpockJob() admin table with latest status")

	client.close()


	
	# for each running process, find all jobids in the processing resolution request tables
	return "Checked processing job statuses"


""" Stitched precomputed pipeline """

@cel.task()
def check_for_spock_jobs_ready_for_making_precomputed_stitched_data():
	""" 
	A celery task that will be run in a schedule

	Checks for spock jobs for the light sheet pipeline 
	that use stitching_method='terastitcher' (i.e. stitched)
	for which step 1 (the stitching) is complete AND
	whose precomputed pipeline for visualizing the stitched
	data products is not yet started.

	For each spock job that satisfies those criteria,
	start the precomputed pipeline for stitched data 
	corresponding to that imaging resolution request
	"""
   
	""" First get all rows from the light sheet 
	pipeline where stitching_method='terastitcher'
	and step1='COMPLETED', finding the entries 
	with the latest timestamps """
	job_contents = db_spockadmin.ProcessingPipelineSpockJob() & \
		'stitching_method="terastitcher"' & 'status_step1="COMPLETED"'
	unique_contents = dj.U('jobid_step0','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents

	processing_pipeline_jobids_step0 = unique_contents.fetch('jobid_step0') 
	logger.debug('These are the step 0 jobids of the processing pipeline '
				 'with stitching_method="terastitcher" and a COMPLETED step 1:')
	logger.debug(processing_pipeline_jobids_step0)
	logger.debug("")
	
	""" For each of these jobs, figure out the ones for which the
	stitched precomputed pipeline has not already been started """
	
	for processing_pipeline_jobid_step0 in processing_pipeline_jobids_step0:
		logger.debug(f"Checking out jobid: {processing_pipeline_jobid_step0} ")
		
		""" Check whether the stitched precomputed pipeline has been started for this 
		processing resolution request """

		stitched_precomputed_spock_job_contents = db_spockadmin.StitchedPrecomputedSpockJob() & \
			f'processing_pipeline_jobid_step0="{processing_pipeline_jobid_step0}"'
		if len(stitched_precomputed_spock_job_contents) > 0:
			logger.info("Precomputed pipeline already started for this job")
			continue
		""" Kick off a stitched precomputed spock job 
		First need to get the kwarg dictionary for 
		this processing resolution request.
		To get that need to cross-reference the
		ProcessingResolutionRequest()
		table"""
		
		""" First figure out if this is a spock job that ran steps 0-2 
		or 0-3 (i.e. used registration) """
		processing_pipeline_db_contents = unique_contents & \
			f'jobid_step0="{processing_pipeline_jobid_step0}"'
		(processing_pipeline_jobid_step2,
			processing_pipeline_jobid_step3) = processing_pipeline_db_contents.fetch1(
			'jobid_step2','jobid_step3')

		if processing_pipeline_jobid_step3:
			logger.debug("Only steps 0-2 were run in this pipeline")
			this_processing_resolution_request = db_lightsheet.Request.ProcessingResolutionRequest() & \
				f'lightsheet_pipeline_spock_jobid="{processing_pipeline_jobid_step3}"'
		else:
			logger.debug("Steps 0-3 were run in this pipeline")
			this_processing_resolution_request = db_lightsheet.Request.ProcessingResolutionRequest() & \
				f'lightsheet_pipeline_spock_jobid="{processing_pipeline_jobid_step2}"'
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
				processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
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
				if not os.environ['FLASK_MODE'] == 'TEST':
					make_precomputed_stitched_data.delay(**precomputed_kwargs)
					logger.info("Sent precomputed task for tiling left lightsheet")
			if right_lightsheet_used:
				this_viz_dir = os.path.join(channel_viz_dir,'right_lightsheet')
				mymkdir(this_viz_dir)
				logger.debug(f"Created directory {this_viz_dir}")
				precomputed_kwargs['lightsheet'] = 'right'
				precomputed_kwargs['viz_dir'] = this_viz_dir
				if not os.environ['FLASK_MODE'] == 'TEST':
					make_precomputed_stitched_data.delay(**precomputed_kwargs)
					logger.info("Sent precomputed task for tiling right lightsheet")

	return "Checked for light sheet pipeline jobs whose data have been stitched"

@cel.task()
def stitched_precomputed_job_status_checker():
	""" 
	A celery task that will be run in a schedule

	Checks all outstanding job statuses on spock
	for the precomputed stitched (stitched) pipeline
	and updates their status in the StitchedPrecomputedSpockJob()
	in db_spockadmin
	and ProcessingChannel() in db_lightsheet 

	"""
   
	""" First get all rows with latest timestamps """
	job_contents = db_spockadmin.StitchedPrecomputedSpockJob()
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
	
	client = connect_to_spock()
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
		(username_thisjob,lightsheet_thisjob,
			processing_pipeline_jobid_step0_thisjob,
			jobid_step0,jobid_step1) = (
				unique_contents & f'jobid_step2={jobid}').fetch1(
				'username','lightsheet',
				'processing_pipeline_jobid_step0','jobid_step0','jobid_step1')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['lightsheet']=lightsheet_thisjob
		job_insert_dict['processing_pipeline_jobid_step0']=processing_pipeline_jobid_step0_thisjob
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
			restrict_dict = dict(left_lightsheet_stitched_precomputed_spock_jobid=jobid)
			replace_key = 'left_lightsheet_stitched_precomputed_spock_job_progress'
		elif lightsheet_thisjob == 'right':
			restrict_dict = dict(right_lightsheet_stitched_precomputed_spock_jobid=jobid)
			replace_key = 'right_lightsheet_stitched_precomputed_spock_job_progress'
		this_processing_channel_content = db_lightsheet.Request.ProcessingChannel() & restrict_dict
		logger.debug("this processing channel content:")
		logger.debug(this_processing_channel_content)
		dj.Table._update(this_processing_channel_content,replace_key,status_step2)
		logger.debug(f"Updated {replace_key} in ProcessingChannel() table ")

		""" If this pipeline run is now 100 percent complete,
		figure out if all of the other stitched precomputed
		pipelines that exist in this same processing request
		and see if they are also complete.
		If so, then email the user that their stitched images
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
				ventral_up = processing_channel_dict['ventral_up']
				restrict_dict = {'channel_name':channel_name,'ventral_up':ventral_up}
				this_imaging_channel_contents = imaging_channel_contents & restrict_dict
				left_lightsheet_used = this_imaging_channel_contents.fetch1('left_lightsheet_used')
				right_lightsheet_used = this_imaging_channel_contents.fetch1('right_lightsheet_used')
				if left_lightsheet_used:
					job_status = processing_channel_dict['left_lightsheet_stitched_precomputed_spock_job_progress']
					processing_request_job_statuses.append(job_status)
				if right_lightsheet_used:
					job_status = processing_channel_dict['right_lightsheet_stitched_precomputed_spock_job_progress']
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
				'general_data_setup',
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
						f'sample_name: {sample_name}\n'
						f'imaging_request_number: {imaging_request_number}\n'
						f'processing_request_number: {processing_request_number}\n\n'
						'are now ready to be visualized. '
						f'To visualize your data, visit this link: {neuroglancer_form_full_url}')
				restrict_dict_request = {'username':username,'request_name':request_name}
				request_contents = db_lightsheet.Request() & restrict_dict_request
				correspondence_email = request_contents.fetch1('correspondence_email')
				recipients = [correspondence_email]
				# if not os.environ['FLASK_MODE'] == 'TEST':
				# 	send_email.delay(subject=subject,body=body,recipients=recipients)
			else:
				logger.debug("Not all processing channels in this request"
							 " are completely converted to precomputed format")
		elif status_step2 == 'CANCELLED' or status_step2 == 'FAILED':
			logger.debug('stitched precomputed pipeline failed. Alerting user and admins')
			(username,request_name,sample_name,imaging_request_number,
				processing_request_number,channel_name) = this_processing_channel_content.fetch1(
				'username','request_name','sample_name',
				'imaging_request_number','processing_request_number',
				'channel_name')
			subject = 'Lightserv automated email: Raw data visualization FAILED'
			body = ('The visualization of your stitched data for sample:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'processing_request_number: {processing_request_number}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. We are investigating why this happened and will contact you shortly. '
					f'If you have any questions or know why this might have happened, '
					'feel free to respond to this email.')
			admin_body = ('The visualization of the stitched data for sample:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'processing_request_number: {processing_request_number}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. Email sent to user. ')
			request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
			correspondence_email = request_contents.fetch1('correspondence_email')
			recipients = [correspondence_email]
			if not os.environ['FLASK_MODE'] == 'TEST':
				# send_email.delay(subject=subject,body=body,recipients=recipients)
				send_admin_email.delay(subject=subject,body=admin_body)
	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_spockadmin.StitchedPrecomputedSpockJob.insert(job_insert_list)
	logger.debug("Entry in StitchedPrecomputedSpockJob() spockadmin table with latest status")

	client.close()

	return "Checked stitched precomptued job statuses"

""" Blended precomputed pipeline """

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
	unique_contents = dj.U('jobid_step0','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents

	processing_pipeline_jobids_step0 = unique_contents.fetch('jobid_step0') 
	logger.debug('These are the step 0 jobids of the processing pipeline '
				 'with a COMPLETED step 1:')
	logger.debug(processing_pipeline_jobids_step0)
	logger.debug("")
	
	""" For each of these jobs, figure out the ones for which the
	blended precomputed pipeline has not already been started """
	
	for processing_pipeline_jobid_step0 in processing_pipeline_jobids_step0:
		logger.debug(f"Checking out jobid: {processing_pipeline_jobid_step0} ")
		
		""" Check whether the blended precomputed pipeline has been started for this 
		processing resolution request """
		
		blended_precomputed_spock_job_contents = db_spockadmin.BlendedPrecomputedSpockJob() & \
			f'processing_pipeline_jobid_step0="{processing_pipeline_jobid_step0}"'
		
		if len(blended_precomputed_spock_job_contents) > 0:
			logger.info("Precomputed pipeline already started for this job")
			continue

		""" First figure out if this is a spock job that ran steps 0-2 
		or 0-3 (i.e. used registration) """
		processing_pipeline_db_contents = unique_contents & \
			f'jobid_step0="{processing_pipeline_jobid_step0}"'
		processing_pipeline_jobid_step2,processing_pipeline_jobid_step3 = processing_pipeline_db_contents.fetch1(
			'jobid_step2','jobid_step3')
	
		if processing_pipeline_jobid_step3:
			logger.debug("This is a job that ran steps 0-3 of the light sheet pipeline")
			this_processing_resolution_request = db_lightsheet.Request.ProcessingResolutionRequest() & \
				f'lightsheet_pipeline_spock_jobid="{processing_pipeline_jobid_step3}"'
		else:
			logger.debug("This is a job that ran steps 0-2 of the light sheet pipeline")
			this_processing_resolution_request = db_lightsheet.Request.ProcessingResolutionRequest() & \
				f'lightsheet_pipeline_spock_jobid="{processing_pipeline_jobid_step2}"'
		
		""" Now find all of the ProcessingChannel() entries 
		corresponding to this processing resolution request """
		logger.debug("this processing resolution request")
		logger.debug(this_processing_resolution_request)
		joined_processing_channel_contents = this_processing_resolution_request * \
			db_lightsheet.Request.ProcessingChannel() * \
			db_lightsheet.Request.ImagingChannel()
		# logger.debug("processing channel contents")
		# logger.debug(joined_processing_channel_contents)
		for this_processing_channel_contents in joined_processing_channel_contents:
			username=this_processing_channel_contents['username']
			request_name = this_processing_channel_contents['request_name']
			sample_name = this_processing_channel_contents['sample_name']
			imaging_request_number = this_processing_channel_contents['imaging_request_number']
			processing_request_number = this_processing_channel_contents['processing_request_number']
			image_resolution = this_processing_channel_contents['image_resolution']
			ventral_up = this_processing_channel_contents['ventral_up']
			channel_name = this_processing_channel_contents['channel_name']
			channel_index = this_processing_channel_contents['imspector_channel_index']
			rawdata_subfolder = this_processing_channel_contents['rawdata_subfolder']
			data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
			channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
			if ventral_up:
				blended_data_path = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "output",
							 f"processing_request_{processing_request_number}",
							 f"resolution_{image_resolution}_ventral_up",
							 "full_sizedatafld",
							 f"{rawdata_subfolder}_ch{channel_index_padded}")
			else:
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
				ventral_up=ventral_up,
				channel_index=channel_index,
				processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
				z_step=z_step,blended_data_path=blended_data_path)

			blended_viz_dir = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "viz",
							 f"processing_request_{processing_request_number}",
							 "blended")
			mymkdir(blended_viz_dir)
			logger.debug(f"Created directory {blended_viz_dir}")
			if ventral_up:
				channel_viz_dir = os.path.join(blended_viz_dir,f'channel_{channel_name}_ventral_up')
			else:
				channel_viz_dir = os.path.join(blended_viz_dir,f'channel_{channel_name}')
			mymkdir(channel_viz_dir)
			logger.debug(f"Created directory {channel_viz_dir}")
			precomputed_kwargs['viz_dir'] = channel_viz_dir
			if not os.environ['FLASK_MODE'] == 'TEST':
				make_precomputed_blended_data.delay(**precomputed_kwargs)
				logger.info("Sent precomputed task for blended data")

	return "Checked for light sheet pipeline jobs whose data have been blended"

@cel.task()
def blended_precomputed_job_status_checker():
	""" 
	A celery task that will be run in a schedule

	Checks all outstanding job statuses on spock
	for the precomputed blended pipeline
	and updates their status in the BlendedPrecomputedSpockJob()
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
	
	client = connect_to_spock()
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
		(username_thisjob,processing_pipeline_jobid_step0_thisjob,
			jobid_step0,jobid_step1) = (
			unique_contents & f'jobid_step2={jobid}').fetch1(
			'username','processing_pipeline_jobid_step0','jobid_step0','jobid_step1')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['processing_pipeline_jobid_step0']=processing_pipeline_jobid_step0_thisjob
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
		logger.debug("Looping over earlier steps")
		for step_counter in range(2):
			step = f'step{step_counter}'
			jobid_earlier_step = jobid_step_dict[step]
			indices_list_earlier_step = job_status_indices_dict_earlier_steps[jobid_earlier_step]
			status_codes_earlier_step = [status_codes_received_earlier_steps[ii] for ii in indices_list_earlier_step]
			status = determine_status_code(status_codes_earlier_step)
			status_step_str = f'status_step{step_counter}'
			logger.debug(f"{step} with status: {status}")
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
				ventral_up = processing_channel_dict['ventral_up']
				restrict_dict = {'channel_name':channel_name,'ventral_up':ventral_up}
				this_imaging_channel_contents = imaging_channel_contents & restrict_dict
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
					'general_data_setup',
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
				request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
				correspondence_email = request_contents.fetch1('correspondence_email')
				recipients = [correspondence_email]
				# if not os.environ['FLASK_MODE'] == 'TEST':
				# 	send_email.delay(subject=subject,body=body,recipients=recipients)
			else:
				logger.debug("Not all blended channels in this request"
							 " are completely converted to precomputed format")

		elif status_step2 == 'CANCELLED' or status_step2 == 'FAILED':
			logger.debug('Blended precomputed pipeline failed. Alerting user and admins')
			(username,request_name,sample_name,imaging_request_number,
				processing_request_number,channel_name) = this_processing_channel_content.fetch1(
				'username','request_name','sample_name',
				'imaging_request_number','processing_request_number',
				'channel_name')
			subject = 'Lightserv automated email: Blended data visualization FAILED'
			body = ('The visualization of your blended data for sample:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'processing_request_number: {processing_request_number}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. We are investigating why this happened and will contact you shortly. '
					f'If you have any questions or know why this might have happened, '
					'feel free to respond to this email.')
			admin_body = ('The visualization of the blended data for sample:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'processing_request_number: {processing_request_number}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. Email sent to user.')
			request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
			correspondence_email = request_contents.fetch1('correspondence_email')
			recipients = [correspondence_email]
			if not os.environ['FLASK_MODE'] == 'TEST':
				# send_email.delay(subject=subject,body=body,recipients=recipients)
				send_admin_email.delay(subject=subject,body=admin_body)
	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_spockadmin.BlendedPrecomputedSpockJob.insert(job_insert_list)
	logger.debug("Entry in BlendedPrecomputedSpockJob() spockadmin table with latest status")

	client.close()

	return "Checked blended precomptued job statuses"

""" Downsized precomputed pipeline """

@cel.task()
def check_for_spock_jobs_ready_for_making_precomputed_downsized_data():
	""" 
	A celery task that will be run in a schedule

	Checks for spock jobs for the light sheet pipeline 
	for which all steps (specifically the final step, step 3)
	is complete AND whose precomputed pipeline for visualizing
	the downsized data products is not yet started.

	For each spock job that satisfies those criteria,
	start the precomputed pipeline for downsized data 
	corresponding to that processing resolution request
	"""
   
	""" First get all rows from the light sheet 
	pipeline where status_step3='COMPLETED', finding the entries 
	with the latest timestamps """
	job_contents = db_spockadmin.ProcessingPipelineSpockJob() & \
		'status_step3="COMPLETED"'
	unique_contents = dj.U('jobid_step0','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents

	processing_pipeline_jobids_step0 = unique_contents.fetch('jobid_step0') 
	logger.debug('These are the step 0 jobids of the processing pipeline '
				 'where the entire pipeline is COMPLETED:')
	logger.debug(processing_pipeline_jobids_step0)
	logger.debug("")
	
	""" For each of these jobs, figure out the ones for which the
	blended precomputed pipeline has not already been started """
	
	for processing_pipeline_jobid_step0 in processing_pipeline_jobids_step0:
		logger.debug(f"Checking out jobid: {processing_pipeline_jobid_step0} ")
		
		""" Check whether the blended precomputed pipeline has been started for this 
		processing resolution request """
		
		downsized_precomputed_spock_job_contents = db_spockadmin.DownsizedPrecomputedSpockJob() & \
			f'processing_pipeline_jobid_step0="{processing_pipeline_jobid_step0}"'
		if len(downsized_precomputed_spock_job_contents) > 0:
			logger.info("Precomputed pipeline already started for this job")
			continue

		""" Kick off a downsized precomputed spock job 
		First need to get the kwarg dictionary for 
		this processing resolution request.
		To get that need to cross-reference the
		ProcessingResolutionRequest()
		table"""
		

		""" First figure out if this is a spock job that ran steps 0-2 
		or 0-3 (i.e. used registration) """
		processing_pipeline_db_contents = unique_contents & \
			f'jobid_step0="{processing_pipeline_jobid_step0}"'
		processing_pipeline_jobid_step2,processing_pipeline_jobid_step3 = processing_pipeline_db_contents.fetch1(
			'jobid_step2','jobid_step3')
	
		if processing_pipeline_jobid_step3:
			logger.debug("This is a job that ran steps 0-3 of the light sheet pipeline")
			this_processing_resolution_request = db_lightsheet.Request.ProcessingResolutionRequest() & \
				f'lightsheet_pipeline_spock_jobid="{processing_pipeline_jobid_step3}"'
		else:
			logger.debug("This is a job that ran steps 0-2 of the light sheet pipeline")
			this_processing_resolution_request = db_lightsheet.Request.ProcessingResolutionRequest() & \
				f'lightsheet_pipeline_spock_jobid="{processing_pipeline_jobid_step2}"'
		
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
			ventral_up = this_processing_channel_contents['ventral_up']
			channel_index = this_processing_channel_contents['imspector_channel_index']
			rawdata_subfolder = this_processing_channel_contents['rawdata_subfolder']
			atlas_name = this_processing_channel_contents['atlas_name']
			data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
			channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
			if ventral_up:
				downsized_data_path = os.path.join(data_bucket_rootpath,username,
								 request_name,sample_name,
								 f"imaging_request_{imaging_request_number}",
								 "output",
								 f"processing_request_{processing_request_number}",
								 f"resolution_{image_resolution}_ventral_up")
			else: 
				downsized_data_path = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "output",
							 f"processing_request_{processing_request_number}",
							 f"resolution_{image_resolution}")
			# rawdata_subfolder = this_processing_channel_contents['rawdata_subfolder'
			""" number of z planes could be altered in the case of tiling due to terastitcher 
			so we will calculate it on the fly when doing the precomputed steps """
			precomputed_kwargs = dict(
				username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number,
				image_resolution=image_resolution,channel_name=channel_name,
				ventral_up=ventral_up,
				channel_index=channel_index,rawdata_subfolder=rawdata_subfolder,
				processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
				downsized_data_path=downsized_data_path,atlas_name=atlas_name)
			downsized_viz_dir = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "viz",
							 f"processing_request_{processing_request_number}",
							 "downsized")
			mymkdir(downsized_viz_dir)
			logger.debug(f"Created directory {downsized_viz_dir}")
			if ventral_up:
				channel_viz_dir = os.path.join(downsized_viz_dir,
					f'channel_{channel_name}_ventral_up')
			else:
				channel_viz_dir = os.path.join(downsized_viz_dir,
					f'channel_{channel_name}')
			mymkdir(channel_viz_dir)
			logger.debug(f"Created directory {channel_viz_dir}")
			precomputed_kwargs['viz_dir'] = channel_viz_dir
			if not os.environ['FLASK_MODE'] == 'TEST':
				make_precomputed_downsized_data.delay(**precomputed_kwargs)
				logger.info("Sent precomputed task for making downsized data")

	return "Checked for light sheet pipeline jobs whose data have been downsized"

@cel.task()
def downsized_precomputed_job_status_checker():
	""" 
	A celery task that will be run in a schedule

	Checks all outstanding job statuses on spock
	for the precomputed downsized pipeline
	and updates their status in the DownsizedPrecomputedSpockJob()
	in db_spockadmin
	and ProcessingChannel() in db_lightsheet 

	"""
	""" First get all rows with latest timestamps """
	job_contents = db_spockadmin.DownsizedPrecomputedSpockJob()
	unique_contents = dj.U('jobid_step1','username').aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	""" Get a list of all jobs we need to check up on, i.e.
	those that could conceivably change. """

	ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
	incomplete_contents = unique_contents & f'status_step1 in {ongoing_codes}'
	jobids = list(incomplete_contents.fetch('jobid_step1'))
	if jobids == []:
		return "No jobs to check"
	jobids_str = ','.join(str(jobid) for jobid in jobids)
	logger.debug(f"Outstanding job ids are: {jobids}")
	
	client = connect_to_spock()
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
		job_insert_dict = {'jobid_step1':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
		status_step1 = determine_status_code(status_codes)
		logger.debug(f"Status code for this job is: {status_step1}")
		job_insert_dict['status_step1'] = status_step1
		""" Find the username, other jobids associated with this jobid """
		username_thisjob,processing_pipeline_jobid_step0_thisjob,jobid_step0 = (
			unique_contents & f'jobid_step1={jobid}').fetch1(
			'username','processing_pipeline_jobid_step0','jobid_step0')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['processing_pipeline_jobid_step0']=processing_pipeline_jobid_step0_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		
		jobid_step_dict = {'step0':jobid_step0}
		""" Similarly, figure out the status codes for the earlier dependency jobs """
		this_run_earlier_jobids_str = ','.join([jobid_step0])
		try:
			command_earlier_steps = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(this_run_earlier_jobids_str)
			stdin_earlier_steps, stdout_earlier_steps, stderr_earlier_steps = client.exec_command(command_earlier_steps)
		except:
			logger.debug("Something went wrong fetching step 0 job statuses from spock.")
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
		for step_counter in range(1):
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
		restrict_dict = dict(downsized_precomputed_spock_jobid=jobid)
		replace_key = 'downsized_precomputed_spock_job_progress'
		this_processing_channel_content = db_lightsheet.Request.ProcessingChannel() & restrict_dict
		logger.debug("this processing channel content:")
		logger.debug(this_processing_channel_content)
		dj.Table._update(this_processing_channel_content,replace_key,status_step1)
		logger.debug(f"Updated {replace_key} in ProcessingChannel() table ")

		""" If this pipeline run is now 100 percent complete,
		figure out if all of the other downsized precomputed
		pipelines that exist in this same processing request
		and see if they are also complete.
		If so, then email the user that their downsized images
		are ready to be visualized"""

		if status_step1 == 'COMPLETED':
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

			""" Loop through and pool all of the job statuses """
			processing_request_job_statuses = []
			for processing_channel_dict in processing_channel_contents:
				""" get the imaging channel contents for this channel
				so that I can figure out which light sheets were used """
				channel_name = processing_channel_dict['channel_name']
				ventral_up = processing_channel_dict['ventral_up']
				restrict_dict = {'channel_name':channel_name,'ventral_up':ventral_up}
				this_imaging_channel_contents = imaging_channel_contents & restrict_dict
				job_status = processing_channel_dict['downsized_precomputed_spock_job_progress']
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
					'general_data_setup',
					username,
					request_name,
					sample_name,
					str(imaging_request_number),
					str(processing_request_number)
					)
				neuroglancer_form_full_url = 'https://' + os.environ['HOSTURL'] + neuroglancer_form_relative_url
				logger.debug("all downsized channel data in this processing request"
							 " completely converted to precomputed format!")
				subject = 'Lightserv automated email: downsized data ready to be visualized'
				body = ('Your downsized data for sample:\n\n'
						f'request_name: {request_name}\n'
						f'sample_name: {sample_name}\n\n'
						'are now ready to be visualized. '
						f'To visualize your data, visit this link: {neuroglancer_form_full_url}')
				request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
				correspondence_email = request_contents.fetch1('correspondence_email')
				recipients = [correspondence_email]
				# if not os.environ['FLASK_MODE'] == 'TEST':
				# 	send_email.delay(subject=subject,body=body,recipients=recipients)
			else:
				logger.debug("Not all downsized channels in this request"
							 " are completely converted to precomputed format")
		elif status_step1 == 'CANCELLED' or status_step1 == 'FAILED':
			logger.debug('Downsized precomputed pipeline failed. Alerting user and admins')
			(username,request_name,sample_name,imaging_request_number,
				processing_request_number,channel_name) = this_processing_channel_content.fetch1(
				'username','request_name','sample_name',
				'imaging_request_number','processing_request_number',
				'channel_name')
			subject = 'Lightserv automated email: Downsized data visualization FAILED'
			body = ('The visualization of your downsized data for sample:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'processing_request_number: {processing_request_number}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. We are investigating why this happened and will contact you shortly. '
					f'If you have any questions or know why this might have happened, '
					'feel free to respond to this email.')
			admin_body = ('The visualization of the downsized data for sample:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'processing_request_number: {processing_request_number}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. Email sent to user.')
			request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
			correspondence_email = request_contents.fetch1('correspondence_email')
			recipients = [correspondence_email]
			if not os.environ['FLASK_MODE'] == 'TEST':
				# send_email.delay(subject=subject,body=body,recipients=recipients)
				send_admin_email.delay(subject=subject,body=admin_body)
	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_spockadmin.DownsizedPrecomputedSpockJob.insert(job_insert_list)
	logger.debug("Entry in DownsizedPrecomputedSpockJob() spockadmin table with latest status")

	client.close()

	return "Checked downsized precomputed job statuses"

""" Registered precomputed pipeline """

@cel.task()
def check_for_spock_jobs_ready_for_making_precomputed_registered_data():
	""" 
	A celery task that will be run in a schedule

	Checks for spock jobs for the light sheet pipeline 
	for which all steps (specifically the final step, step 3)
	is complete AND whose precomputed pipeline for visualizing
	the registered data products is not yet started.

	For each spock job that satisfies those criteria,
	start the precomputed pipeline for each channel
	in this processing resolution request
	"""
   
	""" First get all rows from the light sheet 
	pipeline where status_step1='COMPLETED', finding the entries 
	with the latest timestamps """
	job_contents = db_spockadmin.ProcessingPipelineSpockJob() & \
		'status_step3="COMPLETED"'
	unique_contents = dj.U('jobid_step0','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents

	processing_pipeline_jobids_step0 = unique_contents.fetch('jobid_step0') 
	logger.debug('These are the step 0 jobids of the processing pipeline '
				 'where the entire pipeline is COMPLETED:')
	logger.debug(processing_pipeline_jobids_step0)
	logger.debug("")
	
	""" For each of these jobs, figure out the ones for which the
	blended precomputed pipeline has not already been started """
	
	for processing_pipeline_jobid_step0 in processing_pipeline_jobids_step0:
		logger.debug(f"Checking out jobid: {processing_pipeline_jobid_step0} ")
		
		""" Check whether the registered precomputed pipeline has been started for this 
		processing resolution request """
		
		registered_precomputed_spock_job_contents = db_spockadmin.RegisteredPrecomputedSpockJob() & \
			f'processing_pipeline_jobid_step0="{processing_pipeline_jobid_step0}"'
		if len(registered_precomputed_spock_job_contents) > 0:
			logger.info("Precomputed pipeline already started for this job")
			continue

		""" Kick off a registered precomputed spock job 
		for each channel in this run
		of the processing pipeline (could be 1-4)

		First need to get the kwarg dictionary for 
		this processing resolution request.
		To get that need to cross-reference the
		ProcessingResolutionRequest()
		table. In this case we know the pipeline has a step 3
		so we don't need to do the check whether step 2 or step 3
		is the final step in the pipeline."""

		processing_pipeline_db_contents = unique_contents & \
			f'jobid_step0="{processing_pipeline_jobid_step0}"'
		logger.debug("made it here")
		logger.debug(processing_pipeline_db_contents)
		processing_pipeline_jobid_step3 = processing_pipeline_db_contents.fetch1(
			'jobid_step3')

		logger.debug("jobid_step3:")
		logger.debug(processing_pipeline_jobid_step3)
		this_processing_resolution_request = db_lightsheet.Request.ProcessingResolutionRequest() & \
			f'lightsheet_pipeline_spock_jobid={processing_pipeline_jobid_step3}'
		logger.debug('Processing resolution request:')
		logger.debug(this_processing_resolution_request)
		atlas_name = this_processing_resolution_request.fetch1('atlas_name')
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
			ventral_up = this_processing_channel_contents['ventral_up']
			channel_index = this_processing_channel_contents['imspector_channel_index']
			rawdata_subfolder = this_processing_channel_contents['rawdata_subfolder']
			lightsheet_channel_str = this_processing_channel_contents['lightsheet_channel_str']
			data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
			if ventral_up:
				registered_data_path = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "output",
							 f"processing_request_{processing_request_number}",
							 f"resolution_{image_resolution}_ventral_up",
							 "elastix")
			else:
				registered_data_path = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "output",
							 f"processing_request_{processing_request_number}",
							 f"resolution_{image_resolution}",
							 "elastix")

			""" number of z planes could be altered in the case of tiling due to terastitcher 
			so we will calculate it on the fly when doing the precomputed steps """
			precomputed_kwargs = dict(
				username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number,
				image_resolution=image_resolution,channel_name=channel_name,
				ventral_up=ventral_up,
				channel_index=channel_index,
				lightsheet_channel_str=lightsheet_channel_str,
				rawdata_subfolder=rawdata_subfolder,
				atlas_name=atlas_name,
				processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
				registered_data_path=registered_data_path)

			registered_viz_dir = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "viz",
							 f"processing_request_{processing_request_number}",
							 "registered")
			mymkdir(registered_viz_dir)
			logger.debug(f"Created directory {registered_viz_dir}")
			if ventral_up:
				channel_viz_dir = os.path.join(registered_viz_dir,
					f'channel_{channel_name}_{lightsheet_channel_str}_ventral_up')
			else:
				channel_viz_dir = os.path.join(registered_viz_dir,
					f'channel_{channel_name}_{lightsheet_channel_str}')
			mymkdir(channel_viz_dir)
			logger.debug(f"Created directory {channel_viz_dir}")
			precomputed_kwargs['viz_dir'] = channel_viz_dir
			if ventral_up:
				layer_name = f'channel{channel_name}_registered_ventral_up'
			else:
				layer_name = f'channel{channel_name}_registered'
			layer_dir = os.path.join(channel_viz_dir,layer_name)
			mymkdir(layer_dir)
			logger.debug(f"Created directory {layer_dir}")
			precomputed_kwargs['layer_name'] = layer_name
			if not os.environ['FLASK_MODE'] == 'TEST':
				make_precomputed_registered_data.delay(**precomputed_kwargs)
				logger.info("Sent precomputed task for tiling registered data")

	return "Checked for light sheet pipeline jobs whose data have been registered"

@cel.task()
def registered_precomputed_job_status_checker():
	""" 
	A celery task that will be run in a schedule

	Checks all outstanding job statuses on spock
	for the precomputed registered pipeline
	and updates their status in the RegisteredPrecomputedSpockJob()
	in db_spockadmin
	and ProcessingChannel() in db_lightsheet 

	"""
	""" First get all rows with latest timestamps """
	job_contents = db_spockadmin.RegisteredPrecomputedSpockJob()
	unique_contents = dj.U('jobid_step1','username').aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	""" Get a list of all jobs we need to check up on, i.e.
	those that could conceivably change. """

	ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
	incomplete_contents = unique_contents & f'status_step1 in {ongoing_codes}'
	jobids = list(incomplete_contents.fetch('jobid_step1'))
	if jobids == []:
		return "No jobs to check"
	jobids_str = ','.join(str(jobid) for jobid in jobids)
	logger.debug(f"Outstanding job ids are: {jobids}")
	
	client = connect_to_spock()

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
		job_insert_dict = {'jobid_step1':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
		status_step1 = determine_status_code(status_codes)
		logger.debug(f"Status code for this job is: {status_step1}")
		job_insert_dict['status_step1'] = status_step1
		""" Find the username, other jobids associated with this jobid """
		username_thisjob,processing_pipeline_jobid_step0_thisjob,jobid_step0 = (
			unique_contents & f'jobid_step1={jobid}').fetch1(
			'username','processing_pipeline_jobid_step0','jobid_step0')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['processing_pipeline_jobid_step0']=processing_pipeline_jobid_step0_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		
		jobid_step_dict = {'step0':jobid_step0}
		""" Similarly, figure out the status codes for the earlier dependency jobs """
		this_run_earlier_jobids_str = ','.join([jobid_step0])
		try:
			command_earlier_steps = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(this_run_earlier_jobids_str)
			stdin_earlier_steps, stdout_earlier_steps, stderr_earlier_steps = client.exec_command(command_earlier_steps)
		except:
			logger.debug("Something went wrong fetching step 0 job statuses from spock.")
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
		for step_counter in range(1):
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
		restrict_dict = dict(registered_precomputed_spock_jobid=jobid)
		replace_key = 'registered_precomputed_spock_job_progress'
		this_processing_channel_content = db_lightsheet.Request.ProcessingChannel() & restrict_dict
		logger.debug("this processing channel content:")
		logger.debug(this_processing_channel_content)
		dj.Table._update(this_processing_channel_content,replace_key,status_step1)
		logger.debug(f"Updated {replace_key} in ProcessingChannel() table ")

		""" If this pipeline run is now 100 percent complete,
		figure out if all of the other registered precomputed
		pipelines that exist in this same processing request
		and see if they are also complete.
		If so, then email the user that their registered images
		are ready to be visualized"""

		if status_step1 == 'COMPLETED':
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

			""" Loop through and pool all of the job statuses """
			processing_request_job_statuses = []
			for processing_channel_dict in processing_channel_contents:
				""" get the imaging channel contents for this channel
				so that I can figure out which light sheets were used """
				channel_name = processing_channel_dict['channel_name']
				ventral_up = processing_channel_dict['ventral_up']
				restrict_dict = {'channel_name':channel_name,'ventral_up':ventral_up}
				this_imaging_channel_contents = imaging_channel_contents & restrict_dict
				job_status = processing_channel_dict['registered_precomputed_spock_job_progress']
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
					'general_data_setup',
					username,
					request_name,
					sample_name,
					str(imaging_request_number),
					str(processing_request_number)
					)
				neuroglancer_form_full_url = 'https://' + os.environ['HOSTURL'] + neuroglancer_form_relative_url
				logger.debug("all registered channel data in this processing request"
							 " completely converted to precomputed format!")
				subject = 'Lightserv automated email: registered data ready to be visualized'
				body = ('Your registered data for sample:\n\n'
						f'request_name: {request_name}\n'
						f'sample_name: {sample_name}\n\n'
						'are now ready to be visualized. '
						f'To visualize your data, visit this link: {neuroglancer_form_full_url}')
				request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
				correspondence_email = request_contents.fetch1('correspondence_email')
				recipients = [correspondence_email]
				if not os.environ['FLASK_MODE'] == 'TEST':
					send_email.delay(subject=subject,body=body,recipients=recipients)
			else:
				logger.debug("Not all registered channels in this request"
							 " are completely converted to precomputed format")
		elif status_step1 == 'CANCELLED' or status_step1 == 'FAILED':
			logger.debug('Registered precomputed pipeline failed. Alerting user and admins')
			(username,request_name,sample_name,imaging_request_number,
				processing_request_number,channel_name) = this_processing_channel_content.fetch1(
				'username','request_name','sample_name',
				'imaging_request_number','processing_request_number',
				'channel_name')
			subject = 'Lightserv automated email: Registered data visualization FAILED'
			body = ('The visualization of your registered data for:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'processing_request_number: {processing_request_number}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. We are investigating why this happened and will contact you shortly. '
					f'If you have any questions or know why this might have happened, '
					'feel free to respond to this email.')
			admin_body = ('The visualization of the registered data for sample:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'processing_request_number: {processing_request_number}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. Email sent to user.')
			request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
			correspondence_email = request_contents.fetch1('correspondence_email')
			recipients = [correspondence_email]
			if not os.environ['FLASK_MODE'] == 'TEST':
				# send_email.delay(subject=subject,body=body,recipients=recipients)
				send_admin_email.delay(subject=subject,body=admin_body)
	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_spockadmin.RegisteredPrecomputedSpockJob.insert(job_insert_list)
	logger.debug("Entry in RegisteredPrecomputedSpockJob() spockadmin table with latest status")

	client.close()

	return "Checked registered precomputed job statuses"

""" Smartspim corrected precomputed pipeline """
@cel.task()
def smartspim_corrected_precomputed_job_status_checker():
	""" 
	A celery task that will be run in a schedule

	Checks all outstanding job statuses on spock
	for the precomputed smartspim corrected pipeline
	and updates their status in the SmartspimCorrectedPrecomputedSpockJob()
	in db_spockadmin
	and SmartspimPystripeChannel() in db_lightsheet 
	"""
   
	""" First get all rows with latest timestamps """
	job_contents = db_spockadmin.SmartspimCorrectedPrecomputedSpockJob()
	unique_contents = dj.U('jobid_step3','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	""" Get a list of all jobs we need to check up on, i.e.
	those that could conceivably change. """

	ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
	incomplete_contents = unique_contents & f'status_step3 in {ongoing_codes}'
	jobids = list(incomplete_contents.fetch('jobid_step3'))
	if jobids == []:
		return "No jobs to check"
	jobids_str = ','.join(str(jobid) for jobid in jobids)
	logger.debug(f"Outstanding job ids are: {jobids}")
	
	client = connect_to_spock()
	logger.debug("connected to spock")
	try:
		command = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(jobids_str)
		stdin, stdout, stderr = client.exec_command(command)

		stdout_str = stdout.read().decode("utf-8")
		logger.debug("The response from spock is:")
		logger.debug(stdout_str)
		response_lines = stdout_str.strip('\n').split('\n')
		jobids_received = [x.split('|')[0].split('_')[0] for x in response_lines] # They could be listed as array jobs, e.g. 18521829_[0-5], 18521829_1, or just 18521829 depending on their status
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
		job_insert_dict = {'jobid_step3':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
		status_step3 = determine_status_code(status_codes)
		logger.debug(f"Status code for this job is: {status_step3}")
		job_insert_dict['status_step3'] = status_step3
		""" Find the username, other jobids associated with this jobid """
		(username_thisjob,jobid_step0,jobid_step1,jobid_step2) = (
				unique_contents & f'jobid_step3={jobid}').fetch1(
				'username','jobid_step0',
				'jobid_step1','jobid_step2')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		job_insert_dict['jobid_step1']=jobid_step1
		job_insert_dict['jobid_step2']=jobid_step2
		jobid_step_dict = {
			'step0':jobid_step0,
			'step1':jobid_step1,
			'step2':jobid_step2}
		
		""" Similarly, figure out the status codes for the earlier dependency jobs """
		this_run_earlier_jobids_str = ','.join([jobid_step0,jobid_step1,jobid_step2])
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

		""" Get the pystripe channel entry associated with this jobid
		and update the progress """
		restrict_dict = dict(smartspim_corrected_precomputed_spock_jobid=jobid)
		replace_key = 'smartspim_corrected_precomputed_spock_job_progress'
		this_pystripe_channel_content = db_lightsheet.Request.SmartspimPystripeChannel() & restrict_dict
		logger.debug("this pystripe channel content:")
		logger.debug(this_pystripe_channel_content)
		dj.Table._update(this_pystripe_channel_content,replace_key,status_step3)
		logger.debug(f"Updated {replace_key} in SmartspimPystripeChannel() table ")

		""" If this pipeline run is now 100 percent complete,
		figure out if all of the other stitched precomputed
		pipelines that exist in this same processing request
		and see if they are also complete.
		If so, then email the user that their stitched images
		are ready to be visualized"""

		if status_step3 == 'COMPLETED':
			""" Find all pystripe channels from this same imaging request """
			username,request_name,sample_name,imaging_request_number = this_pystripe_channel_content.fetch1(
				'username','request_name','sample_name','imaging_request_number')
			pystripe_imaging_request_restrict_dict = dict(
				username=username,
				request_name=request_name,
				sample_name=sample_name,
				imaging_request_number=imaging_request_number)
			pystripe_channel_contents_this_imaging_request = db_lightsheet.Request.SmartspimPystripeChannel() & \
				pystripe_imaging_request_restrict_dict

			# Loop over all channels in this imaging request and see 
			# if they are all done with the precomputed pipeline
			pystripe_channel_precomputed_job_statuses = []
			for pystripe_channel_dict in pystripe_channel_contents_this_imaging_request:
				job_status = pystripe_channel_dict['smartspim_corrected_precomputed_spock_job_progress']				
				pystripe_channel_precomputed_job_statuses.append(job_status)
			logger.debug("job statuses for this imaging request:")
			logger.debug(pystripe_channel_precomputed_job_statuses)
			

			if all(x=='COMPLETED' for x in pystripe_channel_precomputed_job_statuses):

				logger.debug("all pystriped imaging channels in this imaging request"
							 " completely converted to precomputed format!")
				neuroglancer_form_relative_url = os.path.join(
					'/neuroglancer',
					'general_data_setup',
					username,
					request_name,
					sample_name,
					str(imaging_request_number),
					"1")
				neuroglancer_form_full_url = 'https://' + os.environ['HOSTURL'] + neuroglancer_form_relative_url
				subject = 'Lightserv automated email: Preprocessed data ready to be visualized'
				body = ('The stitched and corrected data for sample:\n\n'
						f'request_name: {request_name}\n'
						f'sample_name: {sample_name}\n'
						f'imaging_request_number: {imaging_request_number}\n'
						'are now ready to be visualized. '
						f'To visualize your data, visit this link: {neuroglancer_form_full_url}')
				restrict_dict_request = {'username':username,'request_name':request_name}
				request_contents = db_lightsheet.Request() & restrict_dict_request
				correspondence_email = request_contents.fetch1('correspondence_email')
				recipients = [correspondence_email]
				if not os.environ['FLASK_MODE'] == 'TEST':
					send_email.delay(subject=subject,body=body,recipients=recipients)
			else:
				logger.debug("Not all processing channels in this request"
							 " are completely converted to precomputed format")
		elif status_step3 == 'CANCELLED' or status_step3 == 'FAILED':
			logger.debug('smartspim corrected precomputed pipeline failed. Alerting user and admins')
			(username,request_name,sample_name,imaging_request_number,
				image_resolution,channel_name) = this_pystripe_channel_content.fetch1(
				'username','request_name','sample_name','imaging_request_number',
				'image_resolution','channel_name')
			subject = 'Lightserv automated email: Preprocessed data visualization FAILED'
			# body = ('The visualization of your stitched and corrected data for sample:\n\n'
			# 		f'request_name: {request_name}\n'
			# 		f'sample_name: {sample_name}\n\n'
			# 		f'imaging_request_number: {imaging_request_number}\n'
			# 		f'image_resolution: {image_resolution}\n'
			# 		f'channel_name: {channel_name}\n\n'
			# 		'failed. We are investigating why this happened and will contact you shortly. '
			# 		f'If you have any questions or know why this might have happened, '
			# 		'feel free to respond to this email.')
			admin_body = ('The visualization of the stitched data for sample:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'image_resolution: {image_resolution}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. Email sent to user. ')
			# request_contents = db_lightsheet.Request() & \
			# 					{'username':username,'request_name':request_name}
			# correspondence_email = request_contents.fetch1('correspondence_email')
			# recipients = [correspondence_email]
			if not os.environ['FLASK_MODE'] == 'TEST':
				# send_email.delay(subject=subject,body=body,recipients=recipients)
				send_admin_email.delay(subject=subject,body=admin_body)
	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_spockadmin.SmartspimCorrectedPrecomputedSpockJob.insert(job_insert_list)
	logger.debug("Entry in SmartspimCorrectedPrecomputedSpockJob() spockadmin table with latest status")

	client.close()

	return "Checked smartspim corrected precomptued job statuses"
