from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app,jsonify)
from lightserv.processing.forms import StartProcessingForm, NewProcessingRequestForm
from lightserv.processing.tables import (dynamic_processing_management_table,ImagingOverviewTable,ExistingProcessingTable)
from lightserv import db_lightsheet, db_admin
from lightserv import cel
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
file_handler = logging.FileHandler('logs/processing_tasks.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)


@cel.task()
def run_spock_pipeline(username,request_name,sample_name,imaging_request_number,processing_request_number):
	""" An asynchronous celery task (runs in a background process) which runs step 0 
	in the light sheet pipeline -- i.e. makes the parameter dictionary pickle file
	and grabs a bunch of metadata from the raw files to store in the database.  
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
	channel_content_dict_list = all_channel_contents.fetch(as_dict=True)
	sample_contents_dict = sample_contents.fetch1() 
	sample_basepath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
		request_name,sample_name,f'imaging_request_{imaging_request_number}')
	raw_basepath = os.path.join(sample_basepath,'rawdata')

	""" Loop through the image resolutions requested since 
	a different image resolution necessary means a different spock job.
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

			param_dict['slurmjobfactor'] = 50
			
			""" Now the inputdictionary """
			inputdictionary = {}

			""" Need to find the channels belonging to the same rawdata_subfolder so I can  
			fill out the inputdictionary properly """
			channel_contents_this_resolution = \
				(all_channel_contents & f'image_resolution="{image_resolution}"')
			channel_contents_list_this_resolution = channel_contents_this_resolution.fetch(as_dict=True)

			unique_rawdata_subfolders = list(set(channel_contents_this_resolution.fetch('rawdata_subfolder')))
			logger.debug(f"Have the following rawdata folders: {unique_rawdata_subfolders}")
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
						tiling_scheme,tiling_overlap,z_step,image_orientation = \
							this_channel_content.fetch1(
								'tiling_scheme','tiling_overlap','z_step','image_orientation')
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
			logger.info(f"wrote pickle file: {pickle_fullpath}")

			""" Now run the spock pipeline via paramiko """
			hostname = 'spock.pni.princeton.edu'

			# command = """cd %s;sbatch --export=output_directory='%s' main.sh """ % \
			# (current_app.config['PROCESSING_CODE_DIR'],output_directory)
			# if os.environ['FLASK_MODE'] == 'TEST':
			command = """cd {}/testing; ./test_pipeline.sh""".format(current_app.config['PROCESSING_CODE_DIR'])
			# elif os.environ['FLASK_MODE'] == 'DEV':
			# 	command = """cd {}; ./lightsheet_pipeline.sh""".format(current_app.config['PROCESSING_CODE_DIR'])
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
			stdin, stdout, stderr = client.exec_command(command)
			# jobid = str(stdout.read().decode("utf-8").strip('\n'))
			response = str(stdout.read().decode("utf-8").strip('\n')) # strips off the final newline
			logger.debug(response)
			jobid_step0, jobid_step1, jobid_step2, jobid_step3 = response.split('\n')

			status = 'SUBMITTED'
			entry_dict = {'jobid_step3':jobid_step3,'jobid_step2':jobid_step2,'jobid_step1':jobid_step1,
			'jobid_step0':jobid_step0,'username':username,'status_step0':status,'status_step1':status,
			'status_step2':status,'status_step3':status}
			db_admin.ProcessingPipelineSpockJob.insert1(entry_dict)    
			logger.info(f"ProcessingResolutionRequest() request was successfully submitted to spock, jobid: {jobid_step3}")
			dj.Table._update(this_image_resolution_content,'spock_jobid',jobid_step3)
			dj.Table._update(this_image_resolution_content,'spock_job_progress','SUBMITTED')
			
			# finally:
			client.close()
	return "SUBMITTED spock job"

def determine_status_code(status_codes):
	""" Given a list of status codes 
	from a sacct query on a jobid (could be an array job),
	return the status code of the group. 
	This is somewhat subjective and the rules I have defined are:
	if all statuses are the same then the status is the status that is shared,
	if any have a code that is problematic (see "problematic_codes"), then we return "FAILED"
	if none have problematic codes but there are multiple going, then return "RUNNING"
	"""
	if len(status_codes) > 1:
		if all([status_codes[jj]==status_codes[0] for jj in range(len(status_codes))]):
			# If all are the same then just report whatever that code is
			status=status_codes[0]
		elif any([status_codes[jj] in problematic_codes for jj in range(len(status_codes))]):
			# Check if some have problematic codes 
			status="FAILED"
		else:
			# If none have failed but there are multiple then they must be running
			status="RUNNING"
	else:
		status = status_codes[0]
	if 'CANCELLED' in status: 
		# in case status is "CANCELLED by {UID}"
		status = 'CANCELLED'
	return status

@cel.task()
def processing_job_status_checker():
	""" 
	Checks all outstanding processing job statuses on spock
	and updates their status in the ProcesingPipelineSpockJob() in db_admin
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
	processing_resolution_contents = db_lightsheet.Request.ProcessingResolutionRequest()
   
	""" First get all rows with latest timestamps """
	job_contents = db_admin.ProcessingPipelineSpockJob()
	unique_contents = dj.U('jobid_step3','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	""" Get a list of all jobs we need to check up on, i.e.
	those that could conceivably change. Also list the problematic_codes
	which will be used later for error reporting to the user.
	"""

	problematic_codes = ("FAILED","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REVOKED")
	# static_codes = ('COMPLETED','FAILED','BOOT_FAIL','CANCELLED','DEADLINE','OUT_OF_MEMORY','REVOKED')
	ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
	incomplete_contents = unique_contents & f'status_step3 in {ongoing_codes}'
	jobids = list(incomplete_contents.fetch('jobid_step3'))
	if jobids == []:
		return "No jobs to check"
	jobids_str = ','.join(str(jobid) for jobid in jobids)
	logger.debug(f"Outstanding job ids are: {jobids}")
	port = 22
	username = 'ahoag'
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

	for jobid,indices_list in job_status_indices_dict.items():
		logger.debug(f"Working on jobid={jobid}")
		job_insert_dict = {'jobid_step3':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
		status = determine_status_code(status_codes)
		job_insert_dict['status_step3'] = status
		""" Find the username, other jobids associated with this jobid """
		username_thisjob,jobid_step0,jobid_step1,jobid_step2 = (unique_contents & f'jobid_step3={jobid}').fetch1(
			'username','jobid_step0','jobid_step1','jobid_step2')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		job_insert_dict['jobid_step1']=jobid_step1
		job_insert_dict['jobid_step2']=jobid_step2
		""" Get the imaging channel entry associated with this jobid
		and update the progress """
		this_processing_resolution_content = db_lightsheet.Request.ProcessingResolutionRequest() & \
		f'spock_jobid={jobid}'
		dj.Table._update(this_processing_resolution_content,'spock_job_progress',status)
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
		response_lines_earlier_steps = stdout_str_earlier_steps.strip('\n').split('\n')
		jobids_received_earlier_steps = [x.split('|')[0].split('_')[0] for x in response_lines_earlier_steps] # They will be listed as array jobs, e.g. 18521829_[0-5], 18521829_1 depending on their status
		status_codes_received_earlier_steps = [x.split('|')[1] for x in response_lines_earlier_steps]
		job_status_indices_dict_earlier_steps = {jobid:[i for i, x in enumerate(jobids_received_earlier_steps) \
			if x == jobid] for jobid in set(jobids_received_earlier_steps)} 
		""" Loop through the earlier steps and figure out their statuses """
		step_counter = 0
		for jobid_earlier_step,indices_list_earlier_step in job_status_indices_dict_earlier_steps.items():
			status_codes_earlier_step = [status_codes_received_earlier_steps[ii] for ii in indices_list_earlier_step]
			status = determine_status_code(status_codes_earlier_step)
			status_step_str = f'status_step{step_counter}'
			job_insert_dict[status_step_str] = status
			step_counter +=1 

		# job_insert_list = []
		job_insert_list.append(job_insert_dict)



	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_admin.ProcessingPipelineSpockJob.insert(job_insert_list)
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


