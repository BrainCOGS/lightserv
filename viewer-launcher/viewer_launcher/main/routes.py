from flask import Blueprint,request
import os
import redis, docker
import secrets
import logging

if os.environ.get("FLASK_MODE") == 'DEV':
	network = 'lightserv-dev'
elif os.environ.get("FLASK_MODE") == 'PROD':
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

	cv_container = client.containers.run('cloudv_viewer',
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
        'SESSION_NAME':session_name
    }


	ng_container = client.containers.run('nglancer_viewer',
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
        'SESSION_NAME':session_name
    }


	ng_container = client.containers.run('nglancer_registration_viewer',
                                  environment=ng_environment,
                                  network=network,
                                  name=ng_container_name,
                                  detach=True) 
	return "success"

@main.route("/dest",methods=['POST'])
def dest():
	logging.debug("")
	logging.debug("Here!")
	if request.method == 'POST':
		logging.debug(request.json)
		return "Got the data!"
