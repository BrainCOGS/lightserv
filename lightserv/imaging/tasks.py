import os
import errno
import pickle
import math
import paramiko
from lightserv import cel


import logging

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

	""" Now append to kwargs to make the parameter dictionary
	to save on /jukebox so spock can see it """
	# x_dim,y_dim,z_dim = 2160,2560,int(number_of_z_planes)

	rawdata_path = (f"/jukebox/LightSheetData/lightserv_testing/{username}/"
								 f"{request_name}/{sample_name}/"
								 f"imaging_request_{imaging_request_number}/rawdata/"
								 f"{rawdata_subfolder}")
	viz_dir = (f"/jukebox/LightSheetData/lightserv_testing/{username}/"
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
	
	command = ("cd /jukebox/wang/ahoag/precomputed; sbatch --parsable --export=ALL,n_array_jobs_step1={}"
			   ",n_array_jobs_step2={},viz_dir='{}' /jukebox/wang/ahoag/precomputed/precomputed_pipeline.sh").format(
		n_array_jobs_step1,n_array_jobs_step2,viz_dir)
	# command = "cd /jukebox/wang/ahoag/precomputed; sbatch --parsable --export=ALL,viz_dir='{}' /jukebox/wang/ahoag/precomputed/precomputed_pipeline.sh".format(
	# 	viz_dir)
	print("Running command on spock:")
	print(command)
	hostname = 'spock.pni.princeton.edu'
	port=22
	username='ahoag'
	client = paramiko.SSHClient()
	client.load_system_host_keys()
	client.set_missing_host_key_policy(paramiko.WarningPolicy)

	client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)
	stdin, stdout, stderr = client.exec_command(command)
	print("stderr (if any):")
	print(stderr.read().decode("utf-8"))
	jobid = str(stdout.read().decode("utf-8").strip('\n'))

	# status = 'SUBMITTED'
	return f"Submitted jobid: {jobid}"

