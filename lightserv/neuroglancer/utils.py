import os, json, requests, logging, time

import redis

import progproxy as pp

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate=False

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/neuroglancer_utils.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

def generate_neuroglancer_url(payload,ng_image=None):
    """ A convenience function that takes a list of cloudvolume paths/metadata
    and launches cloudvolume containers and a neuroglancer viewer container
    and returns a link to the viewer. The cloudvolumes and neuroglancer
    containers are registered with the configurable proxy.

    """
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)

    session_name = payload['session_name']
    kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

    # Connect to progproxy so I can communicate with it
    proxy_h = pp.progproxy(target_hname='confproxy')

    # Set up environment to be shared by all cloudvolumes
    cv_environment = {
    'PYTHONPATH':'/opt/libraries',
    'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
    'SESSION_NAME':session_name
    }

    cv_dict_list = payload['cv_dict_list']
    cv_number=0
    for cv_dict in cv_dict_list:
        cv_number = cv_dict['cv_number']
        cv_container_name = cv_dict['cv_container_name']
        cv_name = cv_dict['cv_name']
        layer_type = cv_dict['layer_type']

        """ send the data to the viewer-launcher
        to launch the cloudvolume """                       
        requests.post('http://viewer-launcher:5005/cvlauncher',json=cv_dict)
        logger.debug("Made post request to viewer-launcher to launch cloudvolume")

        """ Enter the cv information into redis
        so I can get it from within the neuroglancer container """
        kv.hmset(session_name, {f"cv{cv_number}_container_name": cv_container_name,
            f"cv{cv_number}_name": cv_name, f"layer{cv_number}_type":layer_type})
        # increment the number of cloudvolumes so it is up to date
        kv.hincrby(session_name,'cv_count',1)
        # register with the confproxy so that it can be seen from outside the nglancer network
        proxypath = os.path.join('cloudvols',session_name,cv_name)
        proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:1337")

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    if ng_image == 'custom' or not ng_image:
        requests.post('http://viewer-launcher:5005/ng_custom_launcher',json=ng_dict)
    elif ng_image == 'ontology':
        requests.post('http://viewer-launcher:5005/ng_ontology_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
    # Add the ng container name to redis session key level
    kv.hmset(session_name, {"ng_container_name": ng_container_name})
    # Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network 
    proxy_h.addroute(proxypath=f'viewers/{session_name}', 
        proxytarget=f"http://{ng_container_name}:8080/")
    # if ng_image == 'ontology':
    #     proxy_h.addroute(proxypath=f'ng_api', 
    #         proxytarget=f"http://{ng_container_name}:5000/")
    logger.debug(f"Added {ng_container_name} to redis and confproxy")

    # Spin until the neuroglancer viewer token from redis becomes available 
    # (may be waiting on the neuroglancer container to finish writing to redis)
    # This happens in the post request to viewer-launcher
    while True:
        session_dict = kv.hgetall(session_name)
        if 'viewer' in session_dict.keys():
            break
        else:
            logger.debug("Still spinning; waiting for redis entry for neuoglancer viewer")
            time.sleep(0.25)
    viewer_json_str = kv.hgetall(session_name)['viewer']
    viewer_dict = json.loads(viewer_json_str)
    logger.debug(f"Redis contents for viewer")
    logger.debug(viewer_dict)
    proxy_h.getroutes()
    
    neuroglancerurl = f"http://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
    return neuroglancerurl