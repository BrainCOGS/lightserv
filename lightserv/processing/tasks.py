from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app,jsonify)
from lightserv.main.utils import mymkdir,prettyprinter,db_table_determiner
from lightserv.processing.utils import determine_status_code,get_job_statuses
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

problematic_codes = ("FAILED","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REVOKED")

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
				
				restrict_dict_subfolder = {'rawdata_subfolder':rawdata_subfolder,
					'ventral_up':ventral_up}
				channel_contents_this_subfolder = channel_contents_this_resolution & restrict_dict_subfolder
				channel_contents_dict_list_this_subfolder = channel_contents_this_subfolder.fetch(as_dict=True)
				for channel_dict in channel_contents_dict_list_this_subfolder:      
					logger.debug("Channel dict:")
					logger.debug(channel_dict)
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
					restrict_dict_channel = {'channel_name':channel_name,
						'ventral_up':ventral_up}
					this_channel_content = channel_contents_this_resolution & restrict_dict_channel
		
					""" grab the tiling, number of z planes info from the first entry
					since the parameter dictionary only needs one value for 
					xyz_scale, tiling_overlap, etc...
					and it must be the same for each channel in each rawdata folder
					for the code to run (currently) """
					logger.debug("ii, channel_index:")
					logger.debug(ii)
					logger.debug(channel_index)
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
			processing_resolution_update_dict = this_processing_resolution_content.fetch1()
			processing_resolution_update_dict['lightsheet_pipeline_spock_jobid'] = jobid_final_step
			processing_resolution_update_dict['lightsheet_pipeline_spock_job_progress'] = 'SUBMITTED'

			""" Get the brainpipe commit and add it to processing request contents table """
			
			stdin_commit, stdout_commit, stderr_commit = client.exec_command(command_get_commit)
			brainpipe_commit = str(stdout_commit.read().decode("utf-8").strip('\n'))
			processing_resolution_update_dict['brainpipe_commit'] = brainpipe_commit						
			db_lightsheet.Request.ProcessingResolutionRequest().update1(processing_resolution_update_dict)
			logger.debug("Updated ProcessingResolutionRequest() table")

			client.close()
	return "SUBMITTED spock job"

@cel.task()
def smartspim_stitch(**kwargs):
	""" An asynchronous celery task (runs in a background process) which
	runs a script on spock to stitch smartspim images for a single resolution
	"""
	username=kwargs['username']
	request_name=kwargs['request_name']
	sample_name=kwargs['sample_name']
	imaging_request_number=kwargs['imaging_request_number']
	image_resolution=kwargs['image_resolution']
	n_channels = kwargs['n_channels']

	command_str = f'spim_stitching_pipeline_multichannel.sh {n_channels}'

	# Loop through channels in alphanumeric order (so that lower wavelength channels are first)
	# and add rawdata_path and stitched_output_dir to command_str
	for channel_name in sorted(kwargs['channel_dict'].keys()):
		channel_dict = kwargs['channel_dict'][channel_name]
		ventral_up=channel_dict['ventral_up']
		rawdata_subfolder=channel_dict['rawdata_subfolder']

		rawdata_rootpath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
					username,request_name,sample_name,
					f"imaging_request_{imaging_request_number}",
					'rawdata')
		if ventral_up:
					rawdata_path = os.path.join(rawdata_rootpath,
						f"resolution_{image_resolution}_ventral_up",
						rawdata_subfolder)
					stitched_output_dir = os.path.join(rawdata_rootpath,
							f"resolution_{image_resolution}_ventral_up",
							rawdata_subfolder + '_stitched')
		else:
			rawdata_path = os.path.join(rawdata_rootpath,
					f"resolution_{image_resolution}",
					rawdata_subfolder)
			stitched_output_dir = os.path.join(rawdata_rootpath,
					f"resolution_{image_resolution}",
					rawdata_subfolder + '_stitched')		
				
		command_str += f' {rawdata_path} {stitched_output_dir}'
		# Make stitched output dir 
		mymkdir(stitched_output_dir)
	
	# Now run stitching pipeline 
	processing_code_dir = os.path.join(
		current_app.config['PROCESSING_CODE_DIR'],
		'smartspim')

	# First get the git commit from brainpipe 
	command_get_commit = f'cd {processing_code_dir}; git rev-parse --short HEAD'
	
	if os.environ['FLASK_MODE'] == 'TEST' or os.environ['FLASK_MODE'] == 'DEV':        
		command = f"""cd {processing_code_dir}/testing;./test_stitching.sh {n_channels}"""
	else:
		command = """cd %s;%s/%s """ % \
		(
			processing_code_dir,
			processing_code_dir,
			command_str
		)

	logger.debug("Running command:")
	logger.debug(command)
	try:
		client = connect_to_spock()
	except paramiko.ssh_exception.AuthenticationException:
		logger.info(f"Failed to connect to spock to start job. ")
		# Send email alerting processing admins
		subject = 'Lightserv automated email: Smartspim stitching FAILED to start.'
		body = ('The stitching pipeline failed to start for:\n\n'
				f'username: {username}\n'
				f'request_name: {request_name}\n\n'
				f'sample_name: {sample_name}\n\n'
				f'imaging_request: {imaging_request_number}\n\n'
				f'image_resolution: {image_resolution}\n\n'
				f'This is likely due to a problem with Lightserv connecting to spock.'
				)

		recipients = [x+'@princeton.edu' for x in current_app.config['PROCESSING_ADMINS']]
		if not os.environ['FLASK_MODE'] == 'TEST':
			send_email.delay(subject=subject,body=body,recipients=recipients)

		return "FAILED"

	# Grab brainpipe commit
	stdin_commit, stdout_commit, stderr_commit = client.exec_command(command_get_commit)
	brainpipe_commit = str(stdout_commit.read().decode("utf-8").strip('\n'))
	logger.debug("BRAINPIPE COMMIT")
	logger.debug(brainpipe_commit)

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
		subject = 'Lightserv automated email: Problem starting Smartspim stitching pipeline.'
		body = ('The stitching pipeline failed to start for:\n\n'
				f'username: {username}\n'
				f'request_name: {request_name}\n\n'
				f'rawdata_path: {rawdata_fullpath}\n\n'
				f'Stdout from spock was: {response}\n\n'
				f'Stderr from spock was: {error_response} '
				)

		recipients = [x+'@princeton.edu' for x in current_app.config['PROCESSING_ADMINS']]
		if not os.environ['FLASK_MODE'] == 'TEST':
			send_email.delay(subject=subject,body=body,recipients=recipients)

	else:
		logger.debug("No Stderr Response")
	
	status = 'SUBMITTED'
	jobids_list = response.split('\n')
	
	for ii,channel_name in enumerate(sorted(kwargs['channel_dict'].keys())):
		channel_dict = kwargs['channel_dict'][channel_name]
		ventral_up = channel_dict['ventral_up']

		entry_dict = {}
		entry_dict['username'] = username

		if ii == 0:
			n_jobids = 4
			spockadmin_table = db_spockadmin.SmartspimStitchingSpockJob
		else:
			n_jobids=3
			spockadmin_table = db_spockadmin.SmartspimDependentStitchingSpockJob

		jobids = jobids_list[0:n_jobids]
		for jj in range(n_jobids):	
			entry_dict[f'jobid_step{jj}'] = jobids[jj]
			entry_dict[f'status_step{jj}'] = status

		# exclude jobids from list that were just used for next time through the loop
		jobids_list = jobids_list[n_jobids:]

		""" Update the job status table in spockadmin schema """
		logger.debug(entry_dict)
		spockadmin_table.insert1(entry_dict)    
		logger.info(f"{spockadmin_table}() entry successfully inserted, jobid (step 0): {jobids[0]}")

		""" Update the request tables in lightsheet schema """ 
		jobid_final_step = jobids[-1] 
		stitching_channel_insert_dict = {
			'username':username,
			'request_name':request_name,
			'sample_name':sample_name,
			'imaging_request_number':imaging_request_number,
			'image_resolution':image_resolution,
			'channel_name':channel_name,
			'ventral_up':ventral_up,
		}
		stitching_channel_insert_dict['smartspim_stitching_spock_jobid'] = jobid_final_step
		stitching_channel_insert_dict['smartspim_stitching_spock_job_progress'] = status	
		stitching_channel_insert_dict['brainpipe_commit'] = brainpipe_commit
		now = datetime.now()
		stitching_channel_insert_dict['datetime_stitching_started'] = now

		logger.debug("inserting into SmartspimStitchedChannel():")
		logger.debug(stitching_channel_insert_dict)
		db_lightsheet.Request.SmartspimStitchedChannel().insert1(
				stitching_channel_insert_dict,skip_duplicates=True) 
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
	""" Celery task for making precomputed layer
	for LaVision (aka Miltenyi Biotec UltraMicroscopeII) 
	stitched image data  

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
		command = ("cd /jukebox/wang/ahoag/precomputed/lavision/stitched_pipeline; "
				   f"/jukebox/wang/ahoag/precomputed/lavision/stitched_pipeline/precomputed_pipeline_stitched.sh {viz_dir}")
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
			processing_channel_update_dict = this_processing_channel_content.fetch1()
			processing_channel_update_dict['left_lightsheet_stitched_precomputed_spock_jobid'] = str(jobid_step2)
			processing_channel_update_dict['left_lightsheet_stitched_precomputed_spock_job_progress'] = 'SUBMITTED'
			db_lightsheet.Request.ProcessingChannel().update1(processing_channel_update_dict)
		else:
			processing_channel_update_dict = this_processing_channel_content.fetch1()
			processing_channel_update_dict['right_lightsheet_stitched_precomputed_spock_jobid'] = str(jobid_step2)
			processing_channel_update_dict['right_lightsheet_stitched_precomputed_spock_job_progress'] = 'SUBMITTED'
			db_lightsheet.Request.ProcessingChannel().update1(processing_channel_update_dict)
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
		
	slurmjobfactor = 20 # the number of processes to run per core
	kwargs['slurmjobfactor'] = slurmjobfactor
	pickle_fullpath = viz_dir + '/precomputed_params.p'
	with open(pickle_fullpath,'wb') as pkl_file:
		pickle.dump(kwargs,pkl_file)

	logger.debug(f'Saved precomputed pickle file: {pickle_fullpath} ')
	if os.environ['FLASK_MODE'] == 'TEST':
		command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_precomputed_blended_script.sh "
	else:
		command = ("cd /jukebox/wang/ahoag/precomputed/lavision/blended_pipeline; "
				   f"/jukebox/wang/ahoag/precomputed/lavision/blended_pipeline/precomputed_pipeline_blended.sh {viz_dir}")   # command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_pipeline.sh "
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
		processing_channel_update_dict = this_processing_channel_content.fetch1()
		processing_channel_update_dict['blended_precomputed_spock_jobid'] = str(jobid_step2)
		processing_channel_update_dict['blended_precomputed_spock_job_progress'] = 'SUBMITTED'
		db_lightsheet.Request.ProcessingChannel().update1(processing_channel_update_dict)
		logger.info("Updated ProcessingChannel() table")
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
		command = ("cd /jukebox/wang/ahoag/precomputed/lavision/downsized_pipeline; "
				   "/jukebox/wang/ahoag/precomputed/lavision/downsized_pipeline/precomputed_pipeline_downsized.sh {}").format(
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
		processing_channel_update_dict = this_processing_channel_content.fetch1()
		processing_channel_update_dict['downsized_precomputed_spock_jobid'] = str(jobid_step1)
		processing_channel_update_dict['downsized_precomputed_spock_job_progress'] = 'SUBMITTED'
		db_lightsheet.Request.ProcessingChannel().update1(processing_channel_update_dict)
		logger.info("Updated ProcessingChannel() table")
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
		command = ("cd /jukebox/wang/ahoag/precomputed/lavision/registered_pipeline; "
				   "/jukebox/wang/ahoag/precomputed/lavision/registered_pipeline/precomputed_pipeline_registered.sh {}").format(
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
		processing_channel_update_dict = this_processing_channel_content.fetch1()
		processing_channel_update_dict['registered_precomputed_spock_jobid'] = str(jobid_step1)
		processing_channel_update_dict['registered_precomputed_spock_job_progress'] = 'SUBMITTED'
		db_lightsheet.Request.ProcessingChannel().update1(processing_channel_update_dict)
		logger.info("Updated ProcessingChannel() table")
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

	pystripe_channel_update_dict = this_pystripe_channel_content.fetch1()
	pystripe_channel_update_dict['smartspim_corrected_precomputed_spock_jobid'] = str(jobid_step3)
	pystripe_channel_update_dict['smartspim_corrected_precomputed_spock_job_progress'] = 'SUBMITTED'
	db_lightsheet.Request.SmartspimPystripeChannel().update1(pystripe_channel_update_dict)
	logger.info("Updated SmartspimPystripeChannel() table")

	return "Finished task submitting precomputed pipeline for SmartSPIM corrected data"


#################################################
##### Tasks that will be scheduled regularly ####
#################################################

@cel.task()
def processing_spock_job_status_checker(reg=True):
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
	if reg:
		max_step_index = 3
	else:
		max_step_index = 2
	all_processing_request_contents = db_lightsheet.Request.ProcessingRequest()

	lightsheet_dbtable = db_lightsheet.Request.ProcessingResolutionRequest
	lightsheet_column_name = 'lightsheet_pipeline_spock_jobid'
	
	# First get all rows with latest timestamps """
	job_contents = db_spockadmin.ProcessingPipelineSpockJob()
	unique_contents = dj.U('jobid_step0','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	""" Get a list of all jobs we need to check up on, i.e.
	those that could conceivably change. Also list the problematic_codes
	which will be used later for error reporting to the user.
	"""
	job_insert_list = get_job_statuses(
		unique_contents=unique_contents,
		max_step_index=max_step_index,
		lightsheet_dbtable=db_lightsheet.Request.ProcessingResolutionRequest,
		lightsheet_column_name='lightsheet_pipeline_spock_jobid')
	
	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_spockadmin.ProcessingPipelineSpockJob.insert(job_insert_list)
	logger.debug("Entry in ProcessingPipelineSpockJob() admin table with latest status")

	if not job_insert_list:
		return "No spock jobs need checking"
		
	# Now loop over jobs we checked and perform an action if they completed or failed	
	for job_status_dict in job_insert_list:
		jobid_maxstep = job_status_dict[f'jobid_step{max_step_index}']
		status_maxstep = job_status_dict[f'status_step{max_step_index}']

		this_processing_resolution_content = lightsheet_dbtable() & {lightsheet_column_name:jobid_maxstep}

		(username,request_name,sample_name,imaging_request_number,
		processing_request_number,image_resolution) = this_processing_resolution_content.fetch1(
			"username","request_name","sample_name",
			"imaging_request_number","processing_request_number",
			"image_resolution")
		
		if status_maxstep == 'COMPLETED':
			# Find all processing channels from this same processing resolution request
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
				processing_request_update_dict = processing_request_contents.fetch1()
				processing_request_update_dict['processing_progress'] = 'complete'
				db_lightsheet.Request.ProcessingRequest().update1(processing_request_update_dict)
				logger.info("Updated processing_progress in ProcessingRequest() table ")

				""" Now figure out if all other processing requests for this request have been
				fulfilled. If so, email the user """
				processing_requests = all_processing_request_contents & restrict_dict_request
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

					request_contents = db_lightsheet.Request() & restrict_dict_request
					request_update_dict = request_contents.fetch1()
					request_update_dict['sent_processing_email'] = True
					db_lightsheet.Request().update1(request_update_dict)
					logger.info("Updated Request() Table")
			else:
				logger.debug("Not all processing resolution requests in this "
							 "processing request are completely converted to "
							 "precomputed format")


	
	return "Checked processing job statuses"

@cel.task()
def smartspim_spock_job_status_checker(
	spock_dbtable_str,
	lightsheet_dbtable_str,
	lightsheet_column_name,
	max_step_index):
	""" 
	---PURPOSE---
	A generalized celery task for checking job statuses on spock

	This task that will be run on a periodic schedule

	Checks all outstanding dependent smartspim stitching job
	statuses on spock and updates their status in the
	spock_dbtable and conditionally updates a lightsheet_dbtable
	---INPUT---
	spock_dbtable_str       - string name for the table in schemas/spockadmin.py
	lightsheet_dbtable_str  - string name for the table in schemas/lightsheet.py
	lightsheet_column_name  - string name of the column in the lightsheet table that contains the spock job id
	max_step_index          - the step id of the last step, 0-indexed
	"""
	lightsheet_dbtable = db_table_determiner(schema_str='db_lightsheet',
		dbtable_str=lightsheet_dbtable_str)
	spock_dbtable = db_table_determiner(schema_str='db_admin',
		dbtable_str=spock_dbtable_str)
	all_lightsheet_entries = lightsheet_dbtable()
   
	""" First get all rows with latest timestamps from spock admin table"""
	job_contents = spock_dbtable()
	unique_contents = dj.U('jobid_step0','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	job_insert_list = get_job_statuses(
		unique_contents,
		max_step_index,
		lightsheet_dbtable,
		lightsheet_column_name)
	if not job_insert_list:
		return "No spock jobs need checking"

	# insert into spockadmin table  
	logger.debug(f"Inserting job list into {spock_dbtable_str}")
	logger.debug(job_insert_list)
	spock_dbtable.insert(job_insert_list)
	
	# Now loop over jobs we checked and perform an action if they completed or failed	
	for job_status_dict in job_insert_list:
		status_maxstep = job_status_dict[f'status_step{max_step_index}']
		jobid_maxstep = job_status_dict[f'jobid_step{max_step_index}']
		if status_maxstep == 'COMPLETED':
			# Update datetime this process completed. job status already updated in job status checker above 
			this_lightsheet_content = all_lightsheet_entries & {lightsheet_column_name:jobid_maxstep}
			now = datetime.now()
			replace_lightsheet_dict = this_lightsheet_content.fetch1().copy()

			if lightsheet_column_name == 'smartspim_stitching_spock_jobid':
				replace_key = 'datetime_stitching_completed'
			elif lightsheet_column_name == 'smartspim_pystripe_spock_jobid':
				replace_key = 'datetime_pystripe_completed' 

			replace_lightsheet_dict[replace_key] = now

			lightsheet_dbtable.update1(replace_lightsheet_dict)
			logger.debug(f"Updated {replace_key} in {lightsheet_dbtable_str} table ")

		elif status_maxstep in ["CANCELLED","FAILED"]:
			# Send an email to processing admins alerting them of the failure
			data_bucket_rootpath = current_app.config["DATA_BUCKET_ROOTPATH"]
			this_lightsheet_content = all_lightsheet_entries & {lightsheet_column_name:jobid_maxstep}
			this_lightsheet_dict = this_lightsheet_content.fetch1()
			
			username = this_lightsheet_dict['username']
			request_name = this_lightsheet_dict['request_name']
			sample_name = this_lightsheet_dict['sample_name']
			imaging_request_number = this_lightsheet_dict['imaging_request_number']
			image_resolution = this_lightsheet_dict['image_resolution']
			channel_name = this_lightsheet_dict['channel_name']
			ventral_up = this_lightsheet_dict['ventral_up']

			if lightsheet_column_name == 'smartspim_stitching_spock_jobid':
				pipeline_name = 'stitching'
			elif lightsheet_column_name == 'smartspim_pystripe_spock_jobid':
				pipeline_name = 'pystripe'

			subject = f'Lightserv automated email: Smartspim {pipeline_name} pipeline FAILED.'
			
			body = (f'The {pipeline_name} pipeline FAILED for:\n\n'
					f'username: {username}\n'
					f'request_name: {request_name}\n\n'
					f'sample_name: {sample_name}\n\n'
					f'imaging_request_number: {imaging_request_number}\n\n'
					f'image_resolution: {image_resolution}\n\n'
					f'channel_name: {channel_name}\n\n'
					f'ventral_up: {ventral_up}\n\n'
					f'Spock job info: {prettyprinter(job_status_dict)}'
					)

			recipients = [x+'@princeton.edu' for x in current_app.config['PROCESSING_ADMINS']]
			
			if not os.environ['FLASK_MODE'] == 'TEST':
				send_email.delay(subject=subject,body=body,recipients=recipients)

	


	# for each running process, find all jobids in the processing resolution request tables
	logger.debug(f"Checked job statuses from table {spock_dbtable_str}")
	return "Checked job statuses"

@cel.task()
def precomputed_spock_job_status_checker(
	spock_dbtable_str,
	lightsheet_dbtable_str,
	lightsheet_column_name,
	max_step_index):
	""" 
	A celery task that will be run in a schedule

	Checks all outstanding job statuses on spock
	for a given precomputed pipeline
	and updates statuses in the 
	in the corresponding db_spockadmin table and in ProcessingChannel() in db_lightsheet 

	"""
	if 'downsized' in lightsheet_column_name:
		precomputed_pipeline = 'downsized'
	elif 'blended' in lightsheet_column_name:
		precomputed_pipeline = 'blended'
	elif 'stitched' in lightsheet_column_name:
		precomputed_pipeline = 'stitched'
	elif 'registered' in lightsheet_column_name:
		precomputed_pipeline = 'registered'  

	logger.info(f"Running job status checker for {precomputed_pipeline} precomputed pipeline")

	lightsheet_dbtable = db_table_determiner(schema_str='db_lightsheet',
		dbtable_str=lightsheet_dbtable_str)
	spock_dbtable = db_table_determiner(schema_str='db_admin',
		dbtable_str=spock_dbtable_str)

	# Get all rows with latest timestamps 
	job_contents = spock_dbtable()
	unique_contents = dj.U('jobid_step0','username').aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	# Check statuses of outstanding jobs
	job_insert_list = get_job_statuses(
		unique_contents=unique_contents,
		max_step_index=max_step_index,
		lightsheet_dbtable=lightsheet_dbtable,
		lightsheet_column_name=lightsheet_column_name,
		is_precomputed_task=True)

	for job_status_dict in job_insert_list:

		jobid_maxstep = job_status_dict[f'jobid_step{max_step_index}']
		status_maxstep = job_status_dict[f'status_step{max_step_index}']
		
		if 'stitched' in lightsheet_column_name:
			lightsheet_thisjob = job_status_dict['lightsheet']
			if lightsheet_thisjob == 'left':
				lightsheet_column_name = "left_lightsheet_" + lightsheet_column_name
			else:
				lightsheet_column_name = "right_lightsheet_" + lightsheet_column_name

		this_lightsheet_table_content = lightsheet_dbtable() & {lightsheet_column_name:jobid_maxstep}
		
		if len(this_lightsheet_table_content) == 0:
			logger.debug(f"No {lightsheet_dbtable_str}() entry associated with this jobid. Skipping")
			continue
		logger.debug("this processing channel content:")
		logger.debug(this_lightsheet_table_content)

		# If pipeline failed for this job, alert processing admins via email		
		if status_maxstep in problematic_codes:
			(username,request_name,sample_name,imaging_request_number,
				processing_request_number,channel_name) = this_lightsheet_table_content.fetch1(
				'username','request_name','sample_name',
				'imaging_request_number','processing_request_number',
				'channel_name')

			# Set up email
			
			subject = f'Lightserv automated email: {precomputed_pipeline} data visualization FAILED'
	
			admin_body = (f'The visualization of the {precomputed_pipeline} data for sample:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'processing_request_number: {processing_request_number}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. ')

			if not os.environ['FLASK_MODE'] == 'TEST':
				send_admin_email.delay(subject=subject,body=admin_body)

	if job_insert_list:
		logger.debug("Insert list:")
		logger.debug(job_insert_list)
		spock_dbtable.insert(job_insert_list)
		logger.debug(f"Entry in {spock_dbtable_str} spockadmin table with latest status")
	else:
		logger.debug("No jobs to insert")

	return f"Checked {precomputed_pipeline} precomputed job statuses"

@cel.task()
def check_for_spock_jobs_ready_for_making_precomputed_data():
	""" 
	A celery task that will be run in a schedule

	Checks the status of spock jobs that ran 
	the light sheet pipeline  for which the various 
	steps are complete but whose various precomputed pipelines
	are not yet started.

	For each spock job that satisfies those criteria,
	start the precomputed pipeline(s) that are ready
	to be started given that that step in the pipeline is complete. 
	"""
	
	all_spock_job_contents = db_spockadmin.ProcessingPipelineSpockJob()
	
	step_dict = {
		'blending':1,
		'registered':3
		}

	spock_table_dict = {
		'blending':db_spockadmin.BlendedPrecomputedSpockJob,
		'registered':db_spockadmin.RegisteredPrecomputedSpockJob
	}
	
	for precomputed_pipeline in ['blending','registered']:
		logger.info(f"Checking for jobs ready for {precomputed_pipeline} precomputed pipeline")
		
		step = step_dict[precomputed_pipeline]
		spock_dbtable = spock_table_dict[precomputed_pipeline]

		job_contents = all_spock_job_contents & {
			f'status_step{step}':'COMPLETED'
			}

		unique_contents = dj.U('jobid_step0','username',).aggr(
			job_contents,timestamp='max(timestamp)')*job_contents

		processing_pipeline_jobids_step0 = unique_contents.fetch('jobid_step0') 
		
		""" For each of these jobs, figure out the ones for which the
		precomputed pipeline has not already been started """
		
		for processing_pipeline_jobid_step0 in processing_pipeline_jobids_step0:
			logger.debug(f"Checking out jobid: {processing_pipeline_jobid_step0} ")
			
			stitched_precomputed_spock_job_contents = spock_dbtable() & {
				'processing_pipeline_jobid_step0':processing_pipeline_jobid_step0
			}

			if len(stitched_precomputed_spock_job_contents) > 0:
				logger.info("Precomputed pipeline already started for this job")
				continue
			
			# Get the kwarg dictionary for 
			# this processing resolution request.
			
			# Is this a spock job that ran steps 0-2 
			# or 0-3 (i.e. used registration) 
			processing_pipeline_db_contents = unique_contents & \
				f'jobid_step0="{processing_pipeline_jobid_step0}"'
			(processing_pipeline_jobid_step2,
				processing_pipeline_jobid_step3) = processing_pipeline_db_contents.fetch1(
				'jobid_step2','jobid_step3')

			if processing_pipeline_jobid_step3:
				this_processing_resolution_request = db_lightsheet.Request.ProcessingResolutionRequest() & {
					'lightsheet_pipeline_spock_jobid':processing_pipeline_jobid_step3
				}
			else:
				this_processing_resolution_request = db_lightsheet.Request.ProcessingResolutionRequest() & {
					'lightsheet_pipeline_spock_jobid':processing_pipeline_jobid_step2
				}

			# Find the ProcessingChannel() entries 
			# for this processing resolution request
			
			joined_processing_channel_contents = this_processing_resolution_request * \
				db_lightsheet.Request.ProcessingChannel() * \
				db_lightsheet.Request.ImagingChannel()
			
			# for each of these channels, start the precomputed pipeline
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
				left_lightsheet_used = this_processing_channel_contents['left_lightsheet_used']
				right_lightsheet_used = this_processing_channel_contents['right_lightsheet_used']
				z_step = this_processing_channel_contents['z_step'] 
				lightsheet_channel_str = this_processing_channel_contents['lightsheet_channel_str']
				
				# Set up kwarg dict of common keys 
				precomputed_kwargs = dict(
					username=username,
					request_name=request_name,
					sample_name=sample_name,
					imaging_request_number=imaging_request_number,
					processing_request_number=processing_request_number,
					image_resolution=image_resolution,channel_name=channel_name,
					ventral_up=ventral_up,
					channel_index=channel_index,
					z_step=z_step,
					processing_pipeline_jobid_step0=processing_pipeline_jobid_step0)

				# Handle specific things for blending vs. registered pipelines
				if precomputed_pipeline == 'blending':

					blended_data_rootpath = os.path.join(
						data_bucket_rootpath,
						username,
						request_name,sample_name,
						f"imaging_request_{imaging_request_number}",
						"output",
						f"processing_request_{processing_request_number}")

					viz_dir = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "viz",
							 f"processing_request_{processing_request_number}",
							 "blended")

					if ventral_up:

						blended_data_path = os.path.join(blended_data_rootpath, 
							 f"resolution_{image_resolution}_ventral_up",
							 "full_sizedatafld",
							 f"{rawdata_subfolder}_ch{channel_index_padded}")

						channel_viz_dir = os.path.join(blended_viz_dir,f'channel_{channel_name}_ventral_up')

					else:
						blended_data_path = os.path.join(blended_data_rootpath,
							 f"resolution_{image_resolution}",
							 "full_sizedatafld",
							 f"{rawdata_subfolder}_ch{channel_index_padded}")
					
						channel_viz_dir = os.path.join(blended_viz_dir,f'channel_{channel_name}')

					precomputed_kwargs['blended_data_path'] = blended_data_path
					layer_name = f'channel{channel_name}_blended'
					
				elif precomputed_pipeline == 'registered':

					registered_data_rootpath = os.path.join(
						data_bucket_rootpath,username,
						request_name,sample_name,
						f"imaging_request_{imaging_request_number}",
						"output",
						 f"processing_request_{processing_request_number}")

					viz_dir = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "viz",
							 f"processing_request_{processing_request_number}",
							 "registered")

					if ventral_up:

						registered_data_path = os.path.join(registered_data_rootpath, 
									 f"resolution_{image_resolution}_ventral_up",
									 "elastix")

						channel_viz_dir = os.path.join(registered_viz_dir,
							f'channel_{channel_name}_{lightsheet_channel_str}_ventral_up')

						layer_name = f'channel{channel_name}_registered_ventral_up'
					else:
						
						registered_data_path = os.path.join(registered_data_rootpath,
									 f"resolution_{image_resolution}",
									 "elastix")

						channel_viz_dir = os.path.join(registered_viz_dir,
							f'channel_{channel_name}_{lightsheet_channel_str}')

						layer_name = f'channel{channel_name}_registered'

					precomputed_kwargs['registered_data_path'] = registered_data_path
					precomputed_kwargs['lightsheet_channel_str'] = lightsheet_channel_str
					precomputed_kwargs['rawdata_subfolder'] = rawdata_subfolder
					precomputed_kwargs['atlas_name'] = atlas_name

				# Make precomputed layer directory
				layer_dir = os.path.join(channel_viz_dir,layer_name)
				mymkdir(layer_dir)
				logger.debug(f"Created directory {layer_dir}")
				precomputed_kwargs['layer_name'] = layer_name
				

				if not os.environ['FLASK_MODE'] == 'TEST':
					if precomputed_pipeline == 'blending':
						make_precomputed_blended_data.delay(**precomputed_kwargs)
					elif precomputed_pipeline == 'registered':
						make_precomputed_registered_data.delay(**precomputed_kwargs)
					logger.info("Sent task to start the {precomputed_pipeline} pipeline")

	return "Checked for light sheet pipeline jobs which are ready for precomputed pipelines"

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

		pystripe_channel_update_dict = this_pystripe_channel_content.fetch1()
		pystripe_channel_update_dict[replace_key] = status_step3
		db_lightsheet.Request.SmartspimPystripeChannel().update1(pystripe_channel_update_dict)

		logger.info(f"Updated {replace_key} in SmartspimPystripeChannel() table ")

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
