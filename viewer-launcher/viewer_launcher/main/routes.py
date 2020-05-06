from flask import Blueprint,request
import os
import redis, docker
import secrets
import logging

flask_mode = os.environ.get("FLASK_MODE")
if flask_mode == 'DEV':
	network = 'lightserv-dev'
elif flask_mode == 'PROD':
	network = 'lightserv-prod'

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
	cv_container = client.containers.run(cv_image,
								  volumes=cv_mounts,
								  network=network,
								  name=cv_container_name,
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
        'SESSION_NAME':session_name,
        'FLASK_MODE':os.environ['FLASK_MODE']
    }

	if flask_mode == 'DEV':
		ng_reg_image = 'nglancer_viewer:latest'
	elif flask_mode == 'PROD':
		ng_reg_image = 'nglancer_viewer:prod'
	ng_container = client.containers.run(ng_reg_image,
                                  environment=ng_environment,
                                  network=network,
                                  name=ng_container_name,
                                  detach=True) 
	return "success"