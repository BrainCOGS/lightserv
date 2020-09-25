from flask import Blueprint,request,jsonify
import os
import redis, docker
import secrets
import logging

flask_mode = os.environ.get("FLASK_MODE")
if flask_mode == 'DEV':
	network = 'lightserv-dev'
elif flask_mode == 'PROD':
	network = 'lightserv-prod'
elif flask_mode == 'TEST':
	network = 'lightserv-test'

logging.basicConfig(level=logging.DEBUG)

main = Blueprint('main',__name__)

@main.route("/") 
def base(): 
	return "home of viewer-launcher"

@main.route("/cvlauncher",methods=['POST']) 
def cvlauncher(): 
	logging.debug("POST request to /cvlauncher in viewer-launcher")

	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	cv_dict = request.json
	cv_name = cv_dict['cv_name'] # the name of the layer in Neuroglancer
	layer_type = cv_dict['layer_type']
	cv_path = cv_dict['cv_path'] # where the info file and precomputed data will live
	session_name = cv_dict['session_name']
	cv_container_name = cv_dict['cv_container_name'] # The name given to the docker container

	cv_mounts = {
		cv_path:{
			'bind':'/mnt/data',
			'mode':'ro'
			},
	}
	if flask_mode == 'DEV':
		cv_image = 'cloudv_viewer:latest'
	elif flask_mode == 'PROD':
		cv_image = 'cloudv_viewer:prod'
	elif flask_mode == 'TEST':
		cv_image = 'cloudv_viewer:test'
	cv_container = client.containers.run(cv_image,
								  volumes=cv_mounts,
								  network=network,
								  name=cv_container_name,
								  detach=True)
	return "success"

@main.route("/corslauncher",methods=['POST']) 
def corslauncher(): 
	""" Launches a CORS static webserver. Useful 
	for the precomputed annotation layers,
	which are not supported by cloudvolume yet """
	logging.debug("POST request to /corslauncher in viewer-launcher")

	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	cv_dict = request.json
	# cv_name = cv_dict['cv_name'] # the name of the layer in Neuroglancer
	layer_type = cv_dict['layer_type']
	cv_path = cv_dict['cv_path'] # where the info file and precomputed data will live
	session_name = cv_dict['session_name']
	cv_container_name = cv_dict['cv_container_name'] # The name given to the docker container

	cv_mounts = {
		cv_path:{
			'bind':'/web',
			'mode':'ro'
			},
	}

	cv_environment = ["CORS=true"]
	if flask_mode == 'DEV':
		image = 'halverneus/static-file-server:latest'

	elif flask_mode == 'PROD':
		image = 'halverneus/static-file-server:v1.8.0'

	cv_container = client.containers.run(image,
								  volumes=cv_mounts,
								  environment=cv_environment,
								  network=network,
								  name=cv_container_name,
								  detach=True)
	return "success"

@main.route("/ng_raw_launcher",methods=['POST']) 
def ng_raw_launcher(): 
	logging.debug("POST request to /ng_raw_launcher in viewer-launcher")
	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	ng_dict = request.json
	ng_container_name = ng_dict['ng_container_name'] # the name of the layer in Neuroglancer
	session_name = ng_dict['session_name']
	hosturl = ng_dict['hosturl']
	ng_environment = {
		'HOSTURL':hosturl,
        'SESSION_NAME':session_name,
        'FLASK_MODE':os.environ['FLASK_MODE']
    }

	if flask_mode == 'DEV':
		ng_raw_image = 'nglancer_raw_viewer:latest'
	elif flask_mode == 'PROD':
		ng_raw_image = 'nglancer_raw_viewer:prod'
	elif flask_mode == 'TEST':
		ng_raw_image = 'nglancer_raw_viewer:test'
	ng_container = client.containers.run(ng_raw_image,
                                  environment=ng_environment,
                                  network=network,
                                  name=ng_container_name,
                                  detach=True) 
	return "success"

@main.route("/nglauncher",methods=['POST']) 
def nglauncher(): 
	logging.debug("POST request to /nglauncher in viewer-launcher")
	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	ng_dict = request.json
	ng_container_name = ng_dict['ng_container_name'] # the name of the layer in Neuroglancer
	session_name = ng_dict['session_name']
	hosturl = ng_dict['hosturl']
	ng_environment = {
        'HOSTURL':hosturl,
        'SESSION_NAME':session_name,
        'FLASK_MODE':os.environ['FLASK_MODE']
    }

	if flask_mode == 'DEV':
		ng_image = 'nglancer_viewer:latest'
	elif flask_mode == 'PROD':
		ng_image = 'nglancer_viewer:prod'
	elif flask_mode == 'TEST':
		ng_image = 'nglancer_viewer:test'
	ng_container = client.containers.run(ng_image,
                                  environment=ng_environment,
                                  network=network,
                                  name=ng_container_name,
                                  detach=True) 
	return "success"

@main.route("/ng_reg_launcher",methods=['POST']) 
def ng_reg_launcher(): 
	logging.debug("POST request to /ng_reg_launcher in viewer-launcher")
	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	ng_dict = request.json
	ng_container_name = ng_dict['ng_container_name'] # the name of the layer in Neuroglancer
	session_name = ng_dict['session_name']
	hosturl = ng_dict['hosturl']
	ng_environment = {
		'HOSTURL':hosturl,
        'SESSION_NAME':session_name,
        'FLASK_MODE':os.environ['FLASK_MODE']
    }

	if flask_mode == 'DEV':
		ng_reg_image = 'nglancer_registration_viewer:latest'
	elif flask_mode == 'PROD':
		ng_reg_image = 'nglancer_registration_viewer:prod'
	elif flask_mode == 'TEST':
		ng_reg_image = 'nglancer_registration_viewer:test'
	ng_container = client.containers.run(ng_reg_image,
                                  environment=ng_environment,
                                  network=network,
                                  name=ng_container_name,
                                  detach=True) 
	return "success"

@main.route("/ng_custom_launcher",methods=['POST']) 
def ng_custom_launcher(): 
	logging.debug("POST request to /ng_custom_launcher in viewer-launcher")
	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	ng_dict = request.json
	ng_container_name = ng_dict['ng_container_name'] # the name of the layer in Neuroglancer
	session_name = ng_dict['session_name']
	hosturl = ng_dict['hosturl']
	ng_environment = {
		'HOSTURL':hosturl,
        'SESSION_NAME':session_name,
        'FLASK_MODE':os.environ['FLASK_MODE']
    }

	if flask_mode == 'DEV':
		ng_custom_image = 'nglancer_custom_viewer:latest'
	elif flask_mode == 'PROD':
		ng_custom_image = 'nglancer_custom_viewer:prod'
	ng_container = client.containers.run(ng_custom_image,
                                  environment=ng_environment,
                                  network=network,
                                  name=ng_container_name,
                                  detach=True) 
	return "success"

@main.route("/ng_ontology_launcher",methods=['POST']) 
def ng_ontology_launcher(): 
	logging.debug("POST request to /ng_ontology_launcher in viewer-launcher")
	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	ng_dict = request.json
	ng_container_name = ng_dict['ng_container_name'] # the name of the layer in Neuroglancer
	session_name = ng_dict['session_name']
	hosturl = ng_dict['hosturl']
	ng_environment = {
		'HOSTURL':hosturl,
        'SESSION_NAME':session_name,
        'FLASK_MODE':os.environ['FLASK_MODE']
    }

	if flask_mode == 'DEV':
		ng_ontology_image = 'nglancer_ontology_viewer:latest'
	elif flask_mode == 'PROD':
		ng_ontology_image = 'nglancer_ontology_viewer:prod'
	ng_container = client.containers.run(ng_ontology_image,
                                  environment=ng_environment,
                                  network=network,
                                  name=ng_container_name,
                                  detach=True) 
	return "success"


@main.route("/ng_ontology_pma_launcher",methods=['POST']) 
def ng_ontology_pma_launcher(): 
	logging.debug("POST request to /ng_ontology_pma_launcher in viewer-launcher")
	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	ng_dict = request.json
	ng_container_name = ng_dict['ng_container_name'] # the name of the layer in Neuroglancer
	session_name = ng_dict['session_name']
	hosturl = ng_dict['hosturl']
	ng_environment = {
		'HOSTURL':hosturl,
        'SESSION_NAME':session_name,
        'FLASK_MODE':os.environ['FLASK_MODE']
    }

	if flask_mode == 'DEV':
		ng_ontology_image = 'nglancer_ontology_pma_viewer:latest'
	elif flask_mode == 'PROD':
		ng_ontology_image = 'nglancer_ontology_pma_viewer:prod'
	ng_container = client.containers.run(ng_ontology_image,
                                  environment=ng_environment,
                                  network=network,
                                  name=ng_container_name,
                                  detach=True) 
	return "success"


@main.route("/ng_sandbox_launcher",methods=['POST']) 
def ng_sandbox_launcher(): 
	logging.debug("POST request to /ng_sandbox_launcher in viewer-launcher")
	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	ng_dict = request.json
	ng_container_name = ng_dict['ng_container_name'] # the name of the layer in Neuroglancer
	session_name = ng_dict['session_name']
	hosturl = ng_dict['hosturl']
	ng_environment = {
		'HOSTURL':hosturl,
        'SESSION_NAME':session_name,
        'FLASK_MODE':os.environ['FLASK_MODE']
    }

	if flask_mode == 'DEV':
		ng_sandbox_image = 'nglancer_sandbox_viewer:latest'
	elif flask_mode == 'PROD':
		ng_sandbox_image = 'nglancer_sandbox_viewer:prod'
	logging.debug("ng_sandbox_image is:")
	logging.debug(ng_sandbox_image)
	ng_container = client.containers.run(ng_sandbox_image,
                                  environment=ng_environment,
                                  network=network,
                                  name=ng_container_name,
                                  detach=True) 
	logging.debug("Launched container")
	return "success"

@main.route("/container_killer",methods=['POST']) 
def container_killer(): 
	logging.debug("POST request to /container_killer in viewer-launcher")
	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	container_dict = request.json
	container_names_to_kill = container_dict['list_of_container_names'] # the name of the layer in Neuroglancer
	logging.debug("Received container names to kill:")
	logging.debug(container_names_to_kill)
	for container_name in container_names_to_kill:
		container = client.containers.get(container_name)
		logging.debug(f"Killing docker container: {container_name}")
		container.kill()           
		logging.debug(f"Killed the container")
	
	return "success"

@main.route("/get_container_info",methods=['POST']) 
def get_container_info(): 
	""" Given container names returns container IDs """ 
	logging.debug("POST request to /get_container_info in viewer-launcher")
	client = docker.DockerClient(base_url='unix://var/run/docker.sock')
	container_dict = request.json
	container_names_to_id = container_dict['list_of_container_names'] # the name of the layer in Neuroglancer
	logging.debug("Received container names to get info for:")
	logging.debug(container_names_to_id)
	container_info_dict = {}
	for container_name in container_names_to_id:
		try:
			container = client.containers.get(container_name)
		except:
			logging.debug("Error retrieving the container by name. It was manually deleted")
			container_info_dict[container_name] = {
				'container_id':None,
				'container_image':None
			}
			continue
		container_id = container.short_id
		container_image =  container.attrs['Config']['Image']
			
		container_info_dict[container_name] = {
			'container_id':container_id,
			'container_image':container_image
		}
	
	return jsonify(container_info_dict)