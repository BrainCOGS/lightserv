import redis
import progproxy as pp
from lightserv import cel

import logging
from datetime import datetime, timedelta
import json, requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate=False

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/neuroglancer_tasks.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

@cel.task() 
def ng_viewer_checker():
    """ A celery task to check the activity timestamp
    for all open viewers.
    If it has been more than 30 seconds since last activity,
    then shuts down the viewer and its cloudvolumes and removes them from
    the proxy table. """
    

    proxy_h = pp.progproxy(target_hname='confproxy')
    """ Make the timestamp against which we will compare the viewer timestamps """
    response_all = proxy_h.getroutes()
    proxy_dict_all = json.loads(response_all.text)
    logger.debug("PROXY DICT (ALL ROUTES):")
    logger.debug(proxy_dict_all)
    timeout_timestamp_iso = (datetime.utcnow() - timedelta(seconds=8)).isoformat()
    response = proxy_h.getroutes(inactive_since=timeout_timestamp_iso)
    proxy_dict = json.loads(response.text)
    # proxy_viewer_dict = {key:proxy_dict[key] for key in proxy_dict.keys() if 'viewer' in key}
    expired_session_names = [key.split('/')[-1] for key in proxy_dict.keys() if 'viewer' in key]
    """ Now figure out the session names of each of the expired viewers """   
    logger.debug(f"Expired session names: {expired_session_names}")

    """ Now delete the proxy routes for the viewers and cloudvolumes
    associated with each of these expired sessions"""
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

    """ Now use the session names to take down the actual 
        docker containers for both neuroglancer viewer and cloudvolume
        that were launched for each session """
    logger.debug("removing cloudvolume/neuroglancer containers linked to expired viewers")
    kv = redis.Redis(host="redis", decode_responses=True)
    container_names_to_kill = []
    for session_name in expired_session_names:
        logger.debug(f"in loop for {session_name}")
        session_dict = kv.hgetall(session_name)
        # Cloudvolume containers
        cv_count = int(session_dict['cv_count'])
        for i in range(cv_count):
            # logger.debug(f"in loop over cloudvolume counts")
            cv_container_name = session_dict['cv%i_container_name' % (i+1)]
            container_names_to_kill.append(cv_container_name)

        # Neuroglancer container - there will just be one per session
        ng_container_name = session_dict['ng_container_name']
        container_names_to_kill.append(ng_container_name)
    
    # Have to send the containers to viewer-launcher to kill since we are not root 
    # in this flask container
    if len(container_names_to_kill) > 0:
        containers_to_kill_dict = {'list_of_container_names':container_names_to_kill}
        requests.post('http://viewer-launcher:5005/container_killer',json=containers_to_kill_dict)
       
    return "checked ng viewer health"