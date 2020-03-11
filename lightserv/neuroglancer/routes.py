from flask import (render_template, request, redirect,
                   Blueprint, session, url_for, flash,
                   Markup, Request, Response,abort)
import docker
import redis

import progproxy as pp
import logging
import time
import secrets
import os
import json
from lightserv import cel
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/ng_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

neuroglancer = Blueprint('neuroglancer',__name__)

@neuroglancer.route("/ngdemo")
def ngdemo():
    """ A route for a minimal working example of launching two cloudvolume 
    docker containers
    and neuroglancer container with a layer for each cloudvolume.
    This route will provide a link for the neuroglancer viewer hosting that cloudvolume """
    hosturl = os.environ.get('HOSTURL')
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')

    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)

    session_name = secrets.token_hex(6)
    # session_name = 'my_ng_session'
    viewer_id = "viewer1" # for storing the viewer info in redis
    # kv.hmset(session_name,{"viewer_id":viewer_id})
    kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

    # Set up environment to be shared by all cloudvolumes
    cv_environment = {
        'PYTHONPATH':'/opt/libraries',
        'CONFIGPROXY_AUTH_TOKEN':"'31507a9ddf3e41cf86b58ffede2db68326657437704461ae2c1a4018d55e18f0'",
        'SESSION_NAME':session_name
    }

    # Set up first cloudvolume
    cv1_container_name = '{}_cv1_container'.format(session_name)
    cv1_name = "testvol1"
    layer1_type = "image"
    cv1_localhost_path = '/jukebox/LightSheetData/lightserv_testing/neuroglancer/oostland_m27' 
    
    cv1_mounts = {
        cv1_localhost_path:{
            'bind':'/mnt/data',
            'mode':'ro'
            },
    }
    cv1_container = client.containers.run('cloudv',
                                  volumes=cv1_mounts,
                                  environment=cv_environment,
                                  network='lightserv',
                                  name=cv1_container_name,
                                  detach=True)
    # Enter the cv information into redis so I can get it in the neuroglancer container
    kv.hmset(session_name, {"cv1_container_name": cv1_container_name,
        "cv1_name": cv1_name, "layer1_type":layer1_type})
    # increment the number of cloudvolumes so it is up to date
    kv.hincrby(session_name,'cv_count',1)
    
    # register with the confproxy so that it can be seen from outside the nglancer network
    proxy_h = pp.progproxy(target_hname='confproxy')
    proxypath_1 = os.path.join('cloudvols',session_name,cv1_name)
    proxy_h.addroute(proxypath=proxypath_1,proxytarget=f"http://{cv1_container_name}:1337")

    # Set up the second cloudvolume
    cv2_container_name = '{}_cv2_container'.format(session_name)
    cv2_name = "testvol2"
    layer2_type = "segmentation"
    cv2_localhost_path = '/jukebox/LightSheetData/lightserv_testing/neuroglancer/princetonmouse' 
    
    cv2_mounts = {
        cv2_localhost_path:{
            'bind':'/mnt/data',
            'mode':'ro'
            },
    }
    cv2_container = client.containers.run('cloudv',
                                  volumes=cv2_mounts,
                                  environment=cv_environment,
                                  network='lightserv',
                                  name=cv2_container_name,
                                  detach=True)
    # Enter the cv information into redis so I can get it in the neuroglancer container
    kv.hmset(session_name, {"cv2_container_name": cv2_container_name,
        "cv2_name": cv2_name, "layer2_type":layer2_type})
    # increment the number of cloudvolumes so it is up to date
    kv.hincrby(session_name,'cv_count',1)
    
    # register with the confproxy so that it can be seen from outside the nglancer network
    proxy_h = pp.progproxy(target_hname='confproxy')
    proxypath_2 = os.path.join('cloudvols',session_name,cv2_name)
    proxy_h.addroute(proxypath=proxypath_2,proxytarget=f"http://{cv2_container_name}:1337")

    # Run the ng container which adds the viewer info to redis
    ng_container_name = '{}_ng_container'.format(session_name)
    ng_environment = {
        'HOSTURL':hosturl,
        'PYTHONPATH':'/opt/libraries',
        'CONFIGPROXY_AUTH_TOKEN':"'31507a9ddf3e41cf86b58ffede2db68326657437704461ae2c1a4018d55e18f0'",
        'SESSION_NAME':session_name
    }
    ng_container = client.containers.run('nglancer',
                                  environment=ng_environment,
                                  network='lightserv',
                                  name=ng_container_name,
                                  detach=True) 
    # Add the ng container name to redis session key level
    kv.hmset(session_name, {"ng_container_name": ng_container_name})
    # Add ng viewer url to config proxy so it can be seen from outside of the nglancer network eventually
    proxy_h.addroute(proxypath=f'viewers/{session_name}', proxytarget=f"http://{ng_container_name}:8080/")

    # Spin until the neuroglancer viewer token from redis becomes available (may be waiting on the neuroglancer container to finish writing to redis)
    # time.sleep(1.5      )
    while True:
        session_dict = kv.hgetall(session_name)
        if 'viewer' in session_dict.keys():
            break
        else:
            logger.debug("Still spinning; waiting for redis entry for neuoglancer viewer")
            time.sleep(0.25)
    logger.debug("viewer entry successfully added to redis")
    viewer_json_str = kv.hgetall(session_name)['viewer']
    viewer_dict = json.loads(viewer_json_str)
    # logger.debug(f"Redis contents for viewer")
    # logger.debug(viewer_dict)
    session_dict= kv.hgetall(session_name)
    # session_dict = json.loads(session_json_str)
    logger.debug(f"Redis contents for this session")
    logger.debug(session_dict)
    
    neuroglancerurl = f"http://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
    return f"""
<html>
    <head>
        <title>Containerized neuroglancer links</title>
    </head>
    <body>
        <h1>neuroglancercv</h1>
        <h2>Links: </h2>

        <a href={neuroglancerurl} target="_blank"> Neuroglancer </a>
    </body>
</html>"""


@cel.task() 
def ng_viewer_checker():
    """ A celery task to check the activity timestamp
    for all open viewers.
    If it has been more than 30 seconds since last activity,
    then shuts down the viewer and its cloudvolumes and removes them from
    the proxy table. """
    
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    proxy_h = pp.progproxy(target_hname='confproxy')
    """ Make the timestamp against which we will compare the viewer timestamps """
    timeout_timestamp_iso = (datetime.utcnow() - timedelta(seconds=2)).isoformat()
    response = proxy_h.getroutes(inactive_since=timeout_timestamp_iso)
    proxy_dict = json.loads(response.text)
    # proxy_viewer_dict = {key:proxy_dict[key] for key in proxy_dict.keys() if 'viewer' in key}
    expired_session_names = [key.split('/')[-1] for key in proxy_dict.keys() if 'viewer' in key]
    """ Now figure out the session names of each of the expired viewers """   
    # session_names = [key.split('/')[-1] for key in proxy_viewer_dict.keys()]
    logger.debug('')
    logger.debug("Expired session names:")
    logger.debug(expired_session_names)
    """ Now delete the proxy routes for the viewers and cloudvolumes"""
    for expired_session_name in expired_session_names:
        # first ng viewers
        ng_proxypath = f'/viewers/{expired_session_name}'
        proxy_h.deleteroute(ng_proxypath)
        # now find any cloudvolumes with this session name
        cv_proxypaths = [key for key in proxy_dict.keys() if f'cloudvols/{expired_session_name}' in key]
        logger.debug("expired cloudvolume proxypaths:")
        logger.debug(cv_proxypaths)
        for cv_proxypath in cv_proxypaths:
            proxy_h.deleteroute(cv_proxypath)

    """ Now use the session names to take down the cloudvolume containers 
        and the neuroglancer container that were launched for each session """
    # logger.debug("removing cloudvolume/neuroglancer containers linked to expired viewers")
    kv = redis.Redis(host="redis", decode_responses=True)
    for session_name in expired_session_names:
        # logger.debug(f"in loop for {session_name}")
        session_dict = kv.hgetall(session_name)
        # Cloudvolume containers
        cv_count = int(session_dict['cv_count'])
        for i in range(cv_count):
            # logger.debug(f"in loop over cloudvolume counts")
            cv_container_name = session_dict['cv%i_container_name' % (i+1)]
            # logger.debug(f"Looking up cv container name: {cv_container_name}")
            cv_container = client.containers.get(cv_container_name)
            # logger.debug("Got the cloudvolume container")
            logger.debug(f"Killing cloudvolume container: {cv_container_name}")
            cv_container.kill()           
            logger.debug("killed the cloudvolume container")
        # Neuroglancer container
        ng_container_name = session_dict['ng_container_name']
        # logger.debug(f"Killing ng container: {ng_container_name}")
        ng_container = client.containers.get(ng_container_name)
        # logger.debug("Got the neuroglancer container")
        logger.debug(f"Killing neuroglancer container: {ng_container_name}")
        ng_container.kill()           
        logger.debug(f"Killed the neuroglancer container")
    
    # final_timeout_timestamp_iso = (datetime.utcnow() - timedelta(seconds=5)).isoformat()
    current_routes_response = proxy_h.getroutes()
    logger.info('Proxy routes are now:')
    logger.info(current_routes_response.text)
    return "success"

@neuroglancer.route('/viewer_health_check') 
def ng_health_checker():
    ng_viewer_checker.delay()
    return "Success"

if __name__ == "__main__":
    app.run(host="0.0.0.0")
