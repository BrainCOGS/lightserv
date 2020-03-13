import os
import errno
import docker
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
	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	# Set up precomputed container
	precomputed_container_name = 'precomputed_container'
	layer1_type = "image"
	precomputed_localhost_path = '/jukebox/LightSheetData/lightserv_testing/neuroglancer/oostland_m27' 
	username=kwargs['username']
	request_name=kwargs['request_name']
	sample_name=kwargs['sample_name']
	imaging_request_number=kwargs['imaging_request_number']
	channel_name=kwargs['channel_name']
	image_resolution=kwargs['image_resolution']
	number_of_z_planes=kwargs['number_of_z_planes']
	rawdata_subfolder=kwargs['rawdata_subfolder']

	x_dim,y_dim,z_dim = 2160,2560,int(number_of_z_planes)

	print(f'Setting up container to make precomputed data: {precomputed_container_name}')
	precomputed_localhost_path = (f"/jukebox/LightSheetData/lightserv_testing/{username}/"
								 f"{request_name}/{sample_name}/"
								 f"imaging_request_{imaging_request_number}/rawdata/"
								 f"{rawdata_subfolder}")
	output_dir = (f"/jukebox/LightSheetData/lightserv_testing/{username}/"
								 f"{request_name}/{sample_name}/"
								 f"imaging_request_{imaging_request_number}/viz")
	# try:
	# os.makedirs(output_dir)
	# except OSError as exc: 
	# 	if exc.errno == errno.EEXIST and os.path.isdir(output_dir):
	# 		pass

	precomputed_volumes = {
			precomputed_localhost_path:{
					'bind':'/mnt/data',
					'mode':'ro'
					},
			output_dir:{
					'bind':'/mnt/viz/',
					'mode':'rw'
			}
	}
	print(output_dir)
	# layer_name = f'{request_name}-{sample_name}-channel{channel_name}_raw'
	layer_name = 'raw'
	command = f'python /opt/make_precomputed_rawdata.py --x_dim={x_dim} --y_dim={y_dim} --z_dim={z_dim} --layer_name={layer_name}'
	# run precomputed container
	print("Launching container")
	precomputed_container = client.containers.run('precomputed',
									volumes=precomputed_volumes,
									command=command,
									detach=False)	

