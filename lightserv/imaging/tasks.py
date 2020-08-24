from flask import current_app, url_for
import os
import errno
import pickle
import math
import paramiko
import logging
import datajoint as dj

from lightserv import cel, db_spockadmin, db_lightsheet, smtp_connect
from lightserv.processing.utils import determine_status_code
from lightserv.main.tasks import send_email,send_admin_email
from email.message import EmailMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = False

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

	Spawns a series of spock jobs for handling the
	actual computation.
	"""

	""" Read in keys """
	username=kwargs['username']
	request_name=kwargs['request_name']
	sample_name=kwargs['sample_name']
	imaging_request_number=kwargs['imaging_request_number']
	channel_name=kwargs['channel_name']
	channel_index=kwargs['channel_index']
	image_resolution=kwargs['image_resolution']
	number_of_z_planes=kwargs['number_of_z_planes']
	rawdata_subfolder=kwargs['rawdata_subfolder']
	lightsheet=kwargs['lightsheet']
	viz_dir = kwargs['viz_dir'] 

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

	kwargs['rawdata_path'] = rawdata_path
	slurmjobfactor = 20 # the number of processes run per core
	kwargs['slurmjobfactor'] = slurmjobfactor
	
	pickle_fullpath = viz_dir + '/precomputed_params.p'
	with open(pickle_fullpath,'wb') as pkl_file:
		pickle.dump(kwargs,pkl_file)
	logger.debug(f'Saved precomputed pickle file: {pickle_fullpath} ')

	""" Now set up the connection to spock """
	
	if os.environ['FLASK_MODE'] == 'TEST':
		command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_imaging_script.sh"
	else:
		command = ("cd /jukebox/wang/ahoag/precomputed/raw_pipeline; "
				   f"/jukebox/wang/ahoag/precomputed/raw_pipeline/precomputed_pipeline_raw.sh {viz_dir}")
		# command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_pipeline.sh "
		# command = "cd /jukebox/wang/ahoag/precomputed/testing; ./test_fail_pipeline.sh "

	hostname = 'spock.pni.princeton.edu'
	port=22
	spock_username = current_app.config['SPOCK_LSADMIN_USERNAME'] # Use the service account for this step - if it gets overloaded we can switch to user accounts
	client = paramiko.SSHClient()
	client.load_system_host_keys()
	client.set_missing_host_key_policy(paramiko.WarningPolicy)

	client.connect(hostname, port=port, username=spock_username, allow_agent=False,look_for_keys=True)
	stdin, stdout, stderr = client.exec_command(command)

	try:
		response = str(stdout.read().decode("utf-8").strip('\n')) # strips off the final newline
		logger.debug(response)
		jobid_step0, jobid_step1, jobid_step2 = response.split('\n')
	except:
		if lightsheet == 'left':
			dj.Table._update(this_imaging_channel_content,'left_lightsheet_precomputed_spock_job_progress','FAILED')
		else:
			dj.Table._update(this_imaging_channel_content,'right_lightsheet_precomputed_spock_job_progress','FAILED')
		# logger.debug("Error getting response from spock. ")

		return "Error getting response from spock."
	status_step0 = 'SUBMITTED'
	status_step1 = 'SUBMITTED'
	status_step2 = 'SUBMITTED'
	entry_dict   = {
				'lightsheet':lightsheet,
				'jobid_step0':jobid_step0,
				'jobid_step1':jobid_step1,
				'jobid_step2':jobid_step2,
				'username':username,'status_step0':status_step0,
				'status_step1':status_step1,'status_step2':status_step2
				}

	db_spockadmin.RawPrecomputedSpockJob.insert1(entry_dict)    
	logger.info(f"Precomputed (Raw data) job inserted into RawPrecomputedSpockJob() table: {entry_dict}")
	logger.info(f"Precomputed (Raw data) job successfully submitted to spock, jobid_step2: {jobid_step2}")
	try:
		if lightsheet == 'left':
			dj.Table._update(this_imaging_channel_content,'left_lightsheet_precomputed_spock_jobid',str(jobid_step2))
			dj.Table._update(this_imaging_channel_content,'left_lightsheet_precomputed_spock_job_progress','SUBMITTED')
		else:
			dj.Table._update(this_imaging_channel_content,'right_lightsheet_precomputed_spock_jobid',str(jobid_step2))
			dj.Table._update(this_imaging_channel_content,'right_lightsheet_precomputed_spock_job_progress','SUBMITTED')
	except:
		logger.info("Unable to update ImagingChannel() table")
	return f"Submitted jobid: {jobid_step2}"

@cel.task()
def check_raw_precomputed_statuses():
	""" 
	Checks all outstanding precomputed job statuses on spock
	and updates their status in the SpockJobManager() in db_spockadmin
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
	job_contents = db_spockadmin.RawPrecomputedSpockJob()
	unique_contents = dj.U('jobid_step2','username',).aggr(
		job_contents,timestamp='max(timestamp)')*job_contents
	
	# """ Get a list of all jobs we need to check up on, i.e.
	# those that could conceivably change. Also list the problematic_codes
	# which will be used later for error reporting to the user.
	# """

	problematic_codes = ("FAILED","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REVOKED")
	# static_codes = ('COMPLETED','FAILED','BOOT_FAIL','CANCELLED','DEADLINE','OUT_OF_MEMORY','REVOKED')
	ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
	incomplete_contents = unique_contents & f'status_step2 in {ongoing_codes}'
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
	logger.debug("")
	command = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(jobids_str)
	stdin, stdout, stderr = client.exec_command(command)
	stdout_str = stdout.read().decode("utf-8")
	try:
		response_lines = stdout_str.strip('\n').split('\n')
		jobids_received = [x.split('|')[0].split('_')[0] for x in response_lines]
		status_codes_received = [x.split('|')[1] for x in response_lines]
	except:
		logger.debug("Something went wrong parsing output of precomputed sacct query on spock")
		client.close()
		return "Error parsing sacct query of precomputed jobid on spock"
	logger.debug("jobids_received:")
	logger.debug(jobids_received)
	job_status_indices_dict = {jobid:[i for i, x in enumerate(jobids_received) if x == jobid] for jobid in set(jobids_received)} 
	job_insert_list = []
	for jobid,indices_list in job_status_indices_dict.items():
		logger.debug(f"In loop for jobid: {jobid}")
		job_insert_dict = {'jobid_step2':jobid}
		status_codes = [status_codes_received[ii] for ii in indices_list]
		status_step2 = determine_status_code(status_codes)
		logger.debug("Summary status code:")
		logger.debug(status_step2)
		job_insert_dict['status_step2'] = status_step2
		""" Find the username, other jobids associated with this jobid """
		username_thisjob,lightsheet_thisjob,jobid_step0,jobid_step1 = (
			unique_contents & f'jobid_step2={jobid}').fetch1(
			'username','lightsheet','jobid_step0','jobid_step1')
		logger.debug(f"Lightsheet is: {lightsheet_thisjob}")
		job_insert_dict['username']=username_thisjob
		job_insert_dict['jobid_step0']=jobid_step0
		job_insert_dict['jobid_step1']=jobid_step1
		jobid_step_dict = {'step0':jobid_step0,'step1':jobid_step1}

		""" Now figure out the status codes for the earlier dependency jobs """
		this_run_earlier_jobids_str = ','.join([jobid_step0,jobid_step1])
		try:
			command_earlier_steps = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(this_run_earlier_jobids_str)
			stdin_earlier_steps, stdout_earlier_steps, stderr_earlier_steps = client.exec_command(command_earlier_steps)
		except:
			logger.debug("Something went wrong fetching steps 0 and 1 job statuses from spock.")
			client.close()
			return "Error fetching steps 0,1 job statuses from spock"
		stdout_str_earlier_steps = stdout_earlier_steps.read().decode("utf-8")
		logger.debug(stdout_str_earlier_steps)
		try:
			response_lines_earlier_steps = stdout_str_earlier_steps.strip('\n').split('\n')
			jobids_received_earlier_steps = [x.split('|')[0].split('_')[0] for x in response_lines_earlier_steps] # They will be listed as array jobs, e.g. 18521829_[0-5], 18521829_1 depending on their status
			status_codes_received_earlier_steps = [x.split('|')[1] for x in response_lines_earlier_steps]
		except:
			logger.debug("Something went wrong parsing output of sacct query for steps 0,1 on spock")
			client.close()
			return "Error parsing sacct query of jobids for steps 0,1 on spock"

		job_status_indices_dict_earlier_steps = {jobid:[i for i, x in enumerate(jobids_received_earlier_steps) \
			if x == jobid] for jobid in set(jobids_received_earlier_steps)} 
		""" Loop through the earlier steps and figure out their statuses """
		for step_counter in range(2):
		# for jobid_earlier_step,indices_list_earlier_step in job_status_indices_dict_earlier_steps.items():
			jobid_earlier_step = jobid_step_dict[step]
			indices_list_earlier_step = job_status_indices_dict_earlier_steps[jobid_earlier_step]
			status_codes_earlier_step = [status_codes_received_earlier_steps[ii] for ii in indices_list_earlier_step]
			status_this_step = determine_status_code(status_codes_earlier_step)
			status_step_str = f'status_step{step_counter}'
			job_insert_dict[status_step_str] = status_this_step
		job_insert_dict['lightsheet'] = lightsheet_thisjob
		job_insert_list.append(job_insert_dict)
		""" Get the imaging channel entry associated with this jobid
		and update the progress """
		this_imaging_channel_content = db_lightsheet.Request.ImagingChannel() & \
		f'{lightsheet_thisjob}_lightsheet_precomputed_spock_jobid={jobid}'
		
		try:
			dj.Table._update(this_imaging_channel_content,
				f'{lightsheet_thisjob}_lightsheet_precomputed_spock_job_progress',status_step2)
			logger.debug("Updated ImagingChannel() entry")
		except:
			logger.info("Could not update ImagingChannel() entry")
		
		""" If the pipeline is now complete figure out if all of the 
		resolution/channel combinations that in this same imaging request
		are complete. If so, then email the user that their images are ready 
		to be visualized"""
		if status_step2 == 'COMPLETED':
			username,request_name,sample_name,imaging_request_number = this_imaging_channel_content.fetch1(
				'username','request_name','sample_name','imaging_request_number')
			restrict_dict = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number)
			imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict
			imaging_request_job_statuses = []
			for imaging_channel_dict in imaging_channel_contents:
				left_lightsheet_used = imaging_channel_dict['left_lightsheet_used']
				right_lightsheet_used = imaging_channel_dict['right_lightsheet_used']
				if left_lightsheet_used:
					job_status = imaging_channel_dict['left_lightsheet_precomputed_spock_job_progress']
					imaging_request_job_statuses.append(job_status)
				if right_lightsheet_used:
					job_status = imaging_channel_dict['right_lightsheet_precomputed_spock_job_progress']
					imaging_request_job_statuses.append(job_status)
			# logger.debug("job statuses for this imaging request:")
			# logger.debug(imaging_request_job_statuses)
			neuroglancer_form_relative_url = os.path.join(
				'/neuroglancer',
				'raw_data_setup',
				username,
				request_name,
				sample_name,
				str(imaging_request_number)
				)
			neuroglancer_form_full_url = 'https://' + os.environ['HOSTURL'] + neuroglancer_form_relative_url
			if all(x=='COMPLETED' for x in imaging_request_job_statuses):
				# logger.debug("all imaging channels in this request completed!")
				subject = 'Lightserv automated email: Raw data ready to be visualized'
				body = ('Your raw data for sample:\n\n'
						f'request_name: {request_name}\n'
						f'sample_name: {sample_name}\n'
						f'imaging_request_number: {imaging_request_number}\n\n'
						'are now ready to be visualized. '
						f'To visualize your data, visit this link: {neuroglancer_form_full_url}')
				request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
				correspondence_email = request_contents.fetch1('correspondence_email')
				recipients = [correspondence_email]
				if not os.environ['FLASK_MODE'] == 'TEST':
					send_email.delay(subject=subject,body=body,recipients=recipients)
			else:
				logger.debug("Not all imaging channels in this request are completed")
		elif status_step2 == 'CANCELLED' or status_step2 == 'FAILED':
			logger.debug('Raw precomputed pipeline failed. Alerting user and admins')
			(username,request_name,sample_name,
				imaging_request_number,channel_name) = this_imaging_channel_content.fetch1(
				'username','request_name','sample_name',
				'imaging_request_number','channel_name')
			subject = 'Lightserv automated email: Raw data visualized FAILED'
			body = ('The visualization of your raw data for sample:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. We are investigating why this happened and will contact you shortly. '
					f'If you have any questions or know why this might have happened, '
					'feel free to respond to this email.')
			admin_body = ('The visualization of the raw data for sample:\n\n'
					f'request_name: {request_name}\n'
					f'sample_name: {sample_name}\n'
					f'imaging_request_number: {imaging_request_number}\n'
					f'channel_name: {channel_name}\n\n'
					'failed. Email sent to user. ')
			request_contents = db_lightsheet.Request() & \
								{'username':username,'request_name':request_name}
			correspondence_email = request_contents.fetch1('correspondence_email')
			recipients = [correspondence_email]
			if not os.environ['FLASK_MODE'] == 'TEST':
				send_email.delay(subject=subject,body=body,recipients=recipients)
				send_admin_email.delay(subject=subject,body=admin_body)

	# logger.debug("Insert list:")
	# logger.debug(job_insert_list)
	db_spockadmin.RawPrecomputedSpockJob.insert(job_insert_list)
	client.close()

	return "checked statuses"
	
@cel.task()
def send_processing_reminder_email(**reminder_email_kwargs):
	""" Asynchronous task to send an email, assuming
	the processing request has not been started yet. """
	if os.environ['FLASK_MODE'] == 'TEST':	 	
		print("Not sending reminder email since this is a test.")
		return "Email not sent because are in TEST mode"
	subject = reminder_email_kwargs['subject']
	body = reminder_email_kwargs['body']
	recipients = reminder_email_kwargs['recipients']
	username = reminder_email_kwargs['username']
	request_name = reminder_email_kwargs['request_name']
	sample_name = reminder_email_kwargs['sample_name']
	imaging_request_number = reminder_email_kwargs['imaging_request_number']
	processing_request_number = reminder_email_kwargs['processing_request_number']

	restrict_dict = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number)
	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & restrict_dict
	logger.debug("processing request contents:")
	logger.debug(processing_request_contents)
	processing_progress = processing_request_contents.fetch1('processing_progress')
	if processing_progress != 'incomplete':
		logger.info("Processing already started for this processing request. Not sending reminder email. ")
		logger.info(processing_request_contents)
		return "Processing reminder email not necessary"

	sender_email = 'lightservhelper@gmail.com'
	
	msg = EmailMessage()
	msg['Subject'] = subject
	msg['From'] = sender_email
	if os.environ['FLASK_MODE'] == 'DEV':
		msg['To'] = 'ahoag@princeton.edu' # to me while in DEV phase
	elif os.environ['FLASK_MODE'] == 'PROD':
		msg['To'] = ','.join(recipients)
	msg.set_content(body)                    
	smtp_server = smtp_connect()
	smtp_server.send_message(msg)
	return "Processing reminder email sent!"
