from flask import current_app
import os
import errno
import pickle
import math
import paramiko
import logging
from lightserv import cel, db_admin, db_lightsheet

import datajoint as dj


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/imaging_tasks.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

@cel.task()
def make_precomputed_rawdata(**kwargs):
	""" Celery task for making precomputed dataset
	(i.e. one that can be read by cloudvolume) from raw 
	image data from the light sheet microscope. 

	Spawns a docker container to handle the actual computation
	"""

	""" Read in keys """
	username=kwargs['username']
	request_name=kwargs['request_name']
	sample_name=kwargs['sample_name']
	imaging_request_number=kwargs['imaging_request_number']
	channel_name=kwargs['channel_name']
	image_resolution=kwargs['image_resolution']
	number_of_z_planes=kwargs['number_of_z_planes']
	rawdata_subfolder=kwargs['rawdata_subfolder']

	restrict_dict = dict(username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		image_resolution=image_resolution,channel_name=channel_name)
	this_imaging_channel_content = db_lightsheet.Request.ImagingChannel() & restrict_dict
	logger.debug(this_imaging_channel_content)
	""" Now append to kwargs to make the parameter dictionary
	to save on /jukebox so spock can see it """
	# x_dim,y_dim,z_dim = 2160,2560,int(number_of_z_planes)

	rawdata_path = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
								 f"{request_name}/{sample_name}/"
								 f"imaging_request_{imaging_request_number}/rawdata/"
								 f"{rawdata_subfolder}")
	viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
								 f"{request_name}/{sample_name}/"
								 f"imaging_request_{imaging_request_number}/viz")
	kwargs['rawdata_path'] = rawdata_path
	kwargs['viz_dir'] = viz_dir
	kwargs['layer_name'] = f'channel{channel_name}_raw'
	slurmjobfactor = 20 # the number of processes run per core
	n_array_jobs_step1 = math.ceil(number_of_z_planes/float(slurmjobfactor)) # how many array jobs we need for step 1
	n_array_jobs_step2 = 5 # how many array jobs we need for step 2
	kwargs['slurmjobfactor'] = slurmjobfactor
	kwargs['n_array_jobs_step1'] = n_array_jobs_step1
	kwargs['n_array_jobs_step2'] = n_array_jobs_step2
	
	pickle_fullpath = viz_dir + '/precomputed_params.p'
	with open(pickle_fullpath,'wb') as pkl_file:
		pickle.dump(kwargs,pkl_file)
	logger.debug(f'Saved precomputed pickle file: {pickle_fullpath} ')

	""" Now set up the connection to spock """
	
	# command = ("cd /jukebox/wang/ahoag/precomputed; "
	# 		   "/jukebox/wang/ahoag/precomputed/precomputed_pipeline.sh {} {} {}").format(
	# 	n_array_jobs_step1,n_array_jobs_step2,viz_dir)
	command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_pipeline.sh "
	# command = "cd /jukebox/wang/ahoag/precomputed; sbatch --parsable --export=ALL,viz_dir='{}' /jukebox/wang/ahoag/precomputed/precomputed_pipeline.sh".format(
	# 	viz_dir)
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
	logger.debug(response)
	jobid_step0, jobid_step1, jobid_step2 = response.split('\n')

	status = 'SUBMITTED'
	entry_dict = {'jobid_step0':jobid_step0,
				  'jobid_step1':jobid_step1,
				  'jobid_step2':jobid_step2,
				  'username':username,'status':status}
	db_admin.RawPrecomputedSpockJob.insert1(entry_dict)    
	logger.info(f"Precomputed (Raw data) job inserted into RawPrecomputedSpockJob() table: {entry_dict}")
	logger.info(f"Precomputed (Raw data) job successfully submitted to spock, jobid_step2: {jobid_step2}")
	# logger.debug(type(jobid_step2))
	dj.Table._update(this_imaging_channel_content,'raw_precomputed_spock_jobid',str(jobid_step2))
	dj.Table._update(this_imaging_channel_content,'raw_precomputed_spock_job_progress','SUBMITTED')
	return f"Submitted jobid: {jobid_step2}"

@cel.task()
def check_raw_precomputed_statuses():
	""" 
	Checks all outstanding precomputed job statuses on spock
	and updates their status in the SpockJobManager() in db_admin
	and ProcessingResolutionRequest() in db_lightsheet, 
	then finally figures out which ProcessingRequest() 
	entities are now complete based on the potentially multiple
	ProcessingResolutionRequest() entries they reference.

	A ProcessingRequest() can consist of several jobs because
	jobs are at the ProcessingResolutionRequest() level. 

	set the processing_progress in the ProcessingRequest() 
	table to 'failed'. If all jobs completed, then set 
	processing_progress to 'complete'
	"""

	""" First get all rows with latest timestamps """
	# return "made it"
	job_contents = db_admin.RawPrecomputedSpockJob()
	unique_contents = dj.U('jobid_step2','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	# """ Get a list of all jobs we need to check up on, i.e.
	# those that could conceivably change. Also list the problematic_codes
	# which will be used later for error reporting to the user.
	# """

	problematic_codes = ("FAILED","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REVOKED")
	# static_codes = ('COMPLETED','FAILED','BOOT_FAIL','CANCELLED','DEADLINE','OUT_OF_MEMORY','REVOKED')
	ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
	incomplete_contents = unique_contents & f'status in {ongoing_codes}'
	# logger.debug(incomplete_contents)
	jobids = list(incomplete_contents.fetch('jobid_step2'))
	if jobids == []:
		return "No jobs to check"
	jobids_str = ','.join(str(jobid) for jobid in jobids)
	logger.debug(f"Outstanding job ids are: {jobids}")
	port = 22
	username = 'ahoag'
	hostname = 'spock.pni.princeton.edu'
	# try:
	client = paramiko.SSHClient()
	client.load_system_host_keys()
	client.set_missing_host_key_policy(paramiko.WarningPolicy)
	
	client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)
	logger.debug("connected to spock")
	command = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(jobids_str)
	stdin, stdout, stderr = client.exec_command(command)
	stdout_str = stdout.read().decode("utf-8")
	response_lines = stdout_str.strip('\n').split('\n')
	jobids_received = [x.split('|')[0].split('_')[0] for x in response_lines]
	status_codes_received = [x.split('|')[1] for x in response_lines]
	logger.debug(jobids_received)
	job_status_indices_dict = {jobid:[i for i, x in enumerate(jobids_received) if x == jobid] for jobid in set(jobids_received)} 
	job_insert_list = []
	for jobid,indices_list in job_status_indices_dict.items():
		job_insert_dict = {'jobid_step2':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
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
		job_insert_dict['status'] = status
		""" Find the username, other jobids associated with this jobid """
		username_thisjob,jobid_step0,jobid_step1 = (unique_contents & f'jobid_step2={jobid}').fetch1(
			'username','jobid_step0','jobid_step1')
		job_insert_dict['username']=username_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		job_insert_dict['jobid_step1']=jobid_step1
		job_insert_list.append(job_insert_dict)
		""" Get the imaging channel entry associated with this jobid
		and update the progress """
		this_imaging_channel_content = db_lightsheet.Request.ImagingChannel() & \
		f'raw_precomputed_spock_jobid={jobid}'
		dj.Table._update(this_imaging_channel_content,'raw_precomputed_spock_job_progress',status)
	logger.debug("Insert list:")
	logger.debug(job_insert_list)
	db_admin.RawPrecomputedSpockJob.insert(job_insert_list,replace=True)
	client.close()
	# except:
	# 	logger.debug("Problem connecting to spock or processing jobids")
	# finally:
		
	return "checked statuses"
	