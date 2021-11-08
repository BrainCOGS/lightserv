from lightserv.main.tasks import connect_to_spock

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = False
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''

file_handler = logging.FileHandler('logs/processing_utils.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.addHandler(file_handler)

ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
problematic_codes = ("FAILED","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REVOKED")

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

def get_job_statuses(
	unique_contents,
	max_step_index,
	lightsheet_dbtable,
	lightsheet_column_name,
	is_precomputed_task=False):
	# Get a list of all jobs we need to check up on
	incomplete_contents = unique_contents & f'status_step{max_step_index} in {ongoing_codes}'
	jobids = list(incomplete_contents.fetch(f'jobid_step{max_step_index}'))
	
	if jobids == []:
		logger.debug("No jobs to check")
		return []

	jobids_str = ','.join(str(jobid) for jobid in jobids)
	logger.debug(f"Outstanding job ids are: {jobids}")
	
	job_insert_list = []
	
	# connect via ssh
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
		
		# Make a dictionary keeping track of the statuses of array jobs of a given jobid
		# like {'1234567':[0,1,2],'1234568':[0]} for a jobid that has 3 array jobs 
		# and one that has no array jobs 
		job_status_indices_dict = {
			jobid:[i for i, x in enumerate(jobids_received) if x == jobid] \
			for jobid in set(jobids_received)} 
		
	except:
		logger.debug("Something went wrong fetching job statuses from spock.")
		client.close()
		return "Error fetching job statuses from spock"

	# Loop through outstanding jobs and determine their statuses
	# Use array jobs to make a "pooled" status if necessary 
	for jobid,indices_list in job_status_indices_dict.items():
		logger.debug(f"Working on jobid={jobid}")
		
		# Start assembling an insert for the spock table
		job_insert_dict = {f'jobid_step{max_step_index}':jobid}

		status_codes = [status_codes_received[ii] for ii in indices_list]
		status_maxstep = determine_status_code(status_codes)
		logger.debug(f"Status code for this job is: {status_maxstep}")
		job_insert_dict[f'status_step{max_step_index}'] = status_maxstep
		
		# Find the username, other jobids associated with this jobid 
		jobids_to_fetch = [f'jobid_step{ii}' for ii in range(max_step_index)] 
		fields_to_fetch = ['username'] + jobids_to_fetch
		if is_precomputed_task:
			fields_to_fetch += ['processing_pipeline_jobid_step0']
			if 'stitched' in lightsheet_column_name:
				fields_to_fetch += ['lightsheet'] 

		this_content = unique_contents & {f'jobid_step{max_step_index}':jobid}
		fetched_contents=this_content.fetch(*fields_to_fetch,as_dict=True)[0]
		for key,val in fetched_contents.items(): 
			job_insert_dict[key]=val
		jobid_step_dict = {f'step{ii}':job_insert_dict[f'jobid_step{ii}'] for ii in range(max_step_index)}

		# update spock job progress in lightsheet table
		if 'stitched' in lightsheet_column_name:
			lightsheet_thisjob = job_status_dict['lightsheet']
			if lightsheet_thisjob == 'left':
				lightsheet_column_name = "left_lightsheet_" + lightsheet_column_name
			else:
				lightsheet_column_name = "right_lightsheet_" + lightsheet_column_name
		this_lightsheet_content = lightsheet_dbtable() & {lightsheet_column_name:jobid}

		if len(this_lightsheet_content) == 0:
			logger.debug(f"No entry found in lightsheet table: {lightsheet_dbtable}")
			continue
		logger.debug("this lightsheet content:")
		logger.debug(this_lightsheet_content)
		this_lightsheet_dict = this_lightsheet_content.fetch1()
		replace_lightsheet_dict =  this_lightsheet_dict.copy()
		lightsheet_replace_key = lightsheet_column_name.replace('jobid','job_progress')
		replace_lightsheet_dict[lightsheet_replace_key] = status_maxstep
		
		lightsheet_dbtable().update1(replace_lightsheet_dict,)
		logger.debug("Updated smartspim_stitching_spock_job_progress in SmartspimStitchedChannel() table ")
		
		# Figure out the status codes for the earlier dependency jobs
		this_run_earlier_jobids_str = ','.join([job_insert_dict[f'jobid_step{ii}'] for ii in range(max_step_index)])
		
		if this_run_earlier_jobids_str != '':			
		
			try:
				command_earlier_steps = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f1,2""".format(this_run_earlier_jobids_str)
				stdin_earlier_steps, stdout_earlier_steps, stderr_earlier_steps = client.exec_command(command_earlier_steps)
			except:
				logger.debug("Something went wrong fetching job statuses from spock.")
				client.close()
				return "Error fetching job statuses from spock"
			
			stdout_str_earlier_steps = stdout_earlier_steps.read().decode("utf-8")
			
			try:
				response_lines_earlier_steps = stdout_str_earlier_steps.strip('\n').split('\n')
				jobids_received_earlier_steps = [x.split('|')[0].split('_')[0] for x in response_lines_earlier_steps] # They will be listed as array jobs, e.g. 18521829_[0-5], 18521829_1 depending on their status
				status_codes_received_earlier_steps = [x.split('|')[1] for x in response_lines_earlier_steps]
			except:
				logger.debug("Something went wrong parsing output of sacct query for earlier steps on spock")
				client.close()
				return "Error parsing sacct query of jobids for steps 0-2 on spock"

			job_status_indices_dict_earlier_steps = {jobid:[i for i, x in enumerate(jobids_received_earlier_steps) \
				if x == jobid] for jobid in set(jobids_received_earlier_steps)} 
			
			# Loop through the earlier steps and figure out their statuses 
			logger.debug("looping through earlier steps (if any) to figure out statuses")

			for step_counter in range(max_step_index):
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
		job_insert_list.append(job_insert_dict)

	client.close()
	
	return job_insert_list