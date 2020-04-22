from flask import (render_template, request, redirect,
                   Blueprint, session, url_for, flash,
                   Markup, Request, Response,abort, current_app)
import redis
import logging
import time
import secrets
import os
import requests
import json
from datetime import datetime, timedelta
from .forms import (RawDataSetupForm,StitchedDataSetupForm,
    BlendedDataSetupForm, RegisteredDataSetupForm,
    DownsizedDataSetupForm)
from .tables import (ImagingRequestTable, ProcessingRequestTable)
from lightserv import cel, db_lightsheet
from lightserv.main.utils import (check_imaging_completed,
    check_imaging_request_precomputed,log_http_requests)

import progproxy as pp

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/neuroglancer_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

neuroglancer = Blueprint('neuroglancer',__name__)

@neuroglancer.route("/neuroglancer/raw_data_setup/<username>/<request_name>/<sample_name>/<imaging_request_number>",
    methods=['GET','POST'])
@check_imaging_completed
@check_imaging_request_precomputed
@log_http_requests
def raw_data_setup(username,request_name,sample_name,imaging_request_number):
    """ A route for displaying a form for users to choose how
    they want their raw data (from a given imaging request) 
    visualized in Neuroglancer.
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """
    form = RawDataSetupForm(request.form)
    restrict_dict = dict(username=username,request_name=request_name,
                sample_name=sample_name,imaging_request_number=imaging_request_number)
    imaging_request_contents = db_lightsheet.Request.ImagingRequest() & restrict_dict
    imaging_request_table = ImagingRequestTable(imaging_request_contents)
    imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict

    if request.method == 'POST':
        logger.debug('POST request')
        config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
        # Redis setup for this session
        kv = redis.Redis(host="redis", decode_responses=True)
        hosturl = os.environ['HOSTURL'] # via dockerenv
        data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']

        if form.validate_on_submit():
            logger.debug("Form validated")
            """ loop through each image resolution sub-form 
            and make a neuroglancer viewer link for each one """
            for ii in range(len(form.image_resolution_forms)):
                session_name = secrets.token_hex(6)
                # session_name = 'my_ng_session'
                viewer_id = "viewer1" # for storing the viewer info in redis
                # kv.hmset(session_name,{"viewer_id":viewer_id})
                kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

                # Set up environment to be shared by all cloudvolumes
                cv_environment = {
                    'PYTHONPATH':'/opt/libraries',
                    'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
                    'SESSION_NAME':session_name
                }
                layer_type = "image"
                       
                cv_number = 0 # to keep track of how many cloudvolumes in this viewer
                image_resolution_form = form.image_resolution_forms[ii]
                """ Loop through channels and spawn a cloudvolume 
                within this session for each light sheet used """
                for jj in range(len(image_resolution_form.channel_forms)):
                    channel_form = image_resolution_form.channel_forms[jj]
                    channel_name = channel_form.channel_name.data
                    viz_left_lightsheet = channel_form.viz_left_lightsheet.data
                    viz_right_lightsheet = channel_form.viz_right_lightsheet.data
                    
                    for lightsheet in ['left','right']:
                        if lightsheet == 'left':
                            if not viz_left_lightsheet:
                                continue
                        elif lightsheet == 'right':
                            if not viz_right_lightsheet:
                                continue
                        cv_container_name = f'{session_name}_raw_{channel_name}_{lightsheet}_ls_container'
                        cv_name = f"{channel_name}_{lightsheet}_ls_raw"
                        cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                            sample_name,f'imaging_request_{imaging_request_number}','viz',
                            'raw',f'channel_{channel_name}',f'{lightsheet}_lightsheet',
                            f'channel{channel_name}_raw_{lightsheet}_lightsheet')      
                        
                        cv_number += 1                        
                        """ send the data to the viewer-launcher
                        to launch the cloudvolume """                       
                        cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
                            cv_container_name=cv_container_name,
                            layer_type=layer_type,session_name=session_name)
                        requests.post('http://viewer-launcher:5005/cvlauncher',json=cv_dict)
                        logger.debug("Made post request to viewer-launcher to launch cloudvolume")

                        
                        """ Enter the cv information into redis
                        so I can get it from within the neuroglancer container """
                        kv.hmset(session_name, {f"cv{cv_number}_container_name": cv_container_name,
                            f"cv{cv_number}_name": cv_name, f"layer{cv_number}_type":layer_type})
                        # increment the number of cloudvolumes so it is up to date
                        kv.hincrby(session_name,'cv_count',1)
                        # register with the confproxy so that it can be seen from outside the nglancer network
                        proxy_h = pp.progproxy(target_hname='confproxy')
                        proxypath = os.path.join('cloudvols',session_name,cv_name)
                        proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:1337")
                """ Now spawn a neuroglancer container which will make
                layers for each of the spawned cloudvolumes """
                ng_container_name = f'{session_name}_ng_container'
                ng_dict = {}
                ng_dict['hosturl'] = hosturl
                ng_dict['ng_container_name'] = ng_container_name
                ng_dict['session_name'] = session_name
                """ send the data to the viewer-launcher
                to launch the ng viewer """                       
                
                requests.post('http://viewer-launcher:5005/nglauncher',json=ng_dict)
                logger.debug("Made post request to viewer-launcher to launch ng viewer")
                
                # Add the ng container name to redis session key level
                kv.hmset(session_name, {"ng_container_name": ng_container_name})
                # Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network 
                proxy_h.addroute(proxypath=f'viewers/{session_name}', 
                    proxytarget=f"http://{ng_container_name}:8080/")
                logger.debug(f"Added {ng_container_name} to redis and confproxy")
                # Add the ng container name to redis session key level
                kv.hmset(session_name, {"ng_container_name": ng_container_name})
                # Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network 
                proxy_h.addroute(proxypath=f'viewers/{session_name}', 
                    proxytarget=f"http://{ng_container_name}:8080/")

                # Spin until the neuroglancer viewer token from redis becomes available (may be waiting on the neuroglancer container to finish writing to redis)
                while True:
                    session_dict = kv.hgetall(session_name)
                    if 'viewer' in session_dict.keys():
                        break
                    else:
                        logging.debug("Still spinning; waiting for redis entry for neuoglancer viewer")
                        time.sleep(0.25)
                viewer_json_str = kv.hgetall(session_name)['viewer']
                viewer_dict = json.loads(viewer_json_str)
                logging.debug(f"Redis contents for viewer")
                logging.debug(viewer_dict)
                proxy_h.getroutes()
                # logger.debug("Proxy contents:")
                # logger.debug(proxy_contents)
                
                neuroglancerurl = f"http://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
                logger.debug(neuroglancerurl)
                return render_template('neuroglancer/viewer_link.html',neuroglancerurl=neuroglancerurl)

        else: # form not validated
            flash("There were errors below. Correct them in order to proceed.")
            logger.debug(form.errors)


    """Loop through all imaging resolutions and render a 
    a sub-form for each"""
    unique_image_resolutions = sorted(set(imaging_channel_contents.fetch('image_resolution')))
    channel_contents_lists = []
    """ First clear out any existing subforms from previous http requests """
    while len(form.image_resolution_forms) > 0:
        form.image_resolution_forms.pop_entry()

    for ii in range(len(unique_image_resolutions)):
        image_resolution = unique_image_resolutions[ii]
        # logger.debug(f"image resolution: {image_resolution}")

        form.image_resolution_forms.append_entry()
        this_image_resolution_form = form.image_resolution_forms[ii]
        this_image_resolution_form.image_resolution.data = image_resolution
        """ Gather all imaging channels at this image resolution """
        imaging_channel_contents_this_resolution = (imaging_channel_contents & \
            f'image_resolution="{image_resolution}"')
        imaging_channels_this_resolution = imaging_channel_contents_this_resolution.fetch('channel_name')
        """ Loop through all channels at this resolution and render 
        a sub-sub-form for each """
        channel_contents_lists.append([])
        for jj in range(len(imaging_channels_this_resolution)):
            channel_name = imaging_channels_this_resolution[jj]
            # logger.debug(f"channel: {channel_name}")
            this_image_resolution_form.channel_forms.append_entry()
            this_channel_form = this_image_resolution_form.channel_forms[jj]
            this_channel_form.channel_name.data = channel_name
            """ Figure out which light sheets were imaged """
            this_channel_content_dict = (imaging_channel_contents_this_resolution & \
                f'channel_name="{channel_name}"').fetch1()
            # logger.debug(channel_name)
            # logger.debug(this_channel_content_dict)
           
            channel_contents_lists[ii].append(this_channel_content_dict)
            # logger.debug(this_channel_content) 
        # logger.debug(imaging_channel_dict)

    return render_template('neuroglancer/raw_data_setup.html',form=form,
        channel_contents_lists=channel_contents_lists,imaging_request_table=imaging_request_table)

@neuroglancer.route("/neuroglancer/stitched_data_setup/<username>/<request_name>/<sample_name>/<imaging_request_number>/<processing_request_number>",
    methods=['GET','POST'])
@check_imaging_completed
@log_http_requests
def stitched_data_setup(username,request_name,sample_name,
    imaging_request_number,processing_request_number): # don't change the url 
    """ A route for displaying a form for users to choose how
    they want their stitched data (from a given processing request) 
    visualized in Neuroglancer.
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """

    form = StitchedDataSetupForm(request.form)
    imaging_restrict_dict = dict(username=username,request_name=request_name,
                sample_name=sample_name,imaging_request_number=imaging_request_number)
    imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & imaging_restrict_dict
    processing_restrict_dict = dict(username=username,request_name=request_name,
                sample_name=sample_name,imaging_request_number=imaging_request_number,
                processing_request_number=processing_request_number)

    processing_request_contents = db_lightsheet.Request.ProcessingRequest() & processing_restrict_dict
    processing_request_table = ProcessingRequestTable(processing_request_contents)
    processing_channel_contents = db_lightsheet.Request.ProcessingChannel() & processing_restrict_dict

    if request.method == 'POST':
        logger.debug('POST request')
        # Redis setup for this session
        
        hosturl = os.environ['HOSTURL'] # via dockerenv
        data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']

        if form.validate_on_submit():
            logger.debug("Form validated")
            """ loop through each image resolution sub-form 
            and make a neuroglancer viewer link for each one,
            spawning cloudvolumes for each channel/lightsheet combo """
            kv = redis.Redis(host="redis", decode_responses=True)

            for ii in range(len(form.image_resolution_forms)):
                session_name = secrets.token_hex(6)
                viewer_id = "viewer1" # for storing the viewer info in redis
                # kv.hmset(session_name,{"viewer_id":viewer_id})
                kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

                # Set up environment to be shared by all cloudvolumes
                
                cv_number = 0 # to keep track of how many cloudvolumes in this viewer
                image_resolution_form = form.image_resolution_forms[ii]
                """ Loop through channels and spawn a cloudvolume 
                within this session for each light sheet used """
                for jj in range(len(image_resolution_form.channel_forms)):
                    
                    channel_form = image_resolution_form.channel_forms[jj]
                    channel_name = channel_form.channel_name.data
                    viz_left_lightsheet = channel_form.viz_left_lightsheet.data
                    viz_right_lightsheet = channel_form.viz_right_lightsheet.data
                    
                    for lightsheet in ['left','right']:
                        if lightsheet == 'left':
                            if not viz_left_lightsheet:
                                continue
                        elif lightsheet == 'right':
                            if not viz_right_lightsheet:
                                continue
                        cv_number += 1 
                        cv_container_name = f'{session_name}_raw_{channel_name}_{lightsheet}_ls_container'
                        cv_name = f"{channel_name}_{lightsheet}_ls_raw"
                        cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                            sample_name,f'imaging_request_{imaging_request_number}','viz',
                            f'processing_request_{processing_request_number}','stitched_raw',
                            f'channel_{channel_name}',f'{lightsheet}_lightsheet',
                            f'channel{channel_name}_stitched_{lightsheet}_lightsheet')      
                        layer_type = "image"
                        """ send the data to the viewer-launcher
                        to launch the cloudvolume """                       
                        cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
                            cv_container_name=cv_container_name,
                            layer_type=layer_type,session_name=session_name)
                        requests.post('http://viewer-launcher:5005/cvlauncher',json=cv_dict)
                        logger.debug("Made post request to viewer-launcher to launch cloudvolume")

                        """ Enter the cv information into redis
                        so I can get it from within the neuroglancer container """
                        kv.hmset(session_name, {f"cv{cv_number}_container_name": cv_container_name,
                            f"cv{cv_number}_name": cv_name, f"layer{cv_number}_type":layer_type})
                        # increment the number of cloudvolumes so it is up to date
                        kv.hincrby(session_name,'cv_count',1)
                        # register with the confproxy so that it can be seen from outside the nglancer network
                        proxy_h = pp.progproxy(target_hname='confproxy')
                        proxypath = os.path.join('cloudvols',session_name,cv_name)
                        proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:1337")
                
                """ Now spawn a neuroglancer container which will make
                layers for each of the spawned cloudvolumes """
                ng_container_name = f'{session_name}_ng_container'
                ng_dict = {}
                ng_dict['hosturl'] = hosturl
                ng_dict['ng_container_name'] = ng_container_name
                ng_dict['session_name'] = session_name
                """ send the data to the viewer-launcher
                to launch the ng viewer """                       
                
                requests.post('http://viewer-launcher:5005/nglauncher',json=ng_dict)
                logger.debug("Made post request to viewer-launcher to launch ng viewer")
                
                # Add the ng container name to redis session key level
                kv.hmset(session_name, {"ng_container_name": ng_container_name})
                # Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network 
                proxy_h.addroute(proxypath=f'viewers/{session_name}', proxytarget=f"http://{ng_container_name}:8080/")
                logger.debug(f"Added {ng_container_name} to redis and confproxy")

                # Spin until the neuroglancer viewer token from redis becomes available 
                # (may be waiting on the neuroglancer container to finish writing to redis)
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
                logger.debug("Proxy contents:")
                response=proxy_h.getroutes()
                logger.debug(response.text)
                # logger.debug(proxy_contents)
                
                neuroglancerurl = f"https://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
                logger.debug("URL IS:")
                logger.debug(neuroglancerurl)
                return render_template('neuroglancer/viewer_link.html',neuroglancerurl=neuroglancerurl)
                

        else: # form not validated
            flash("There were errors below. Correct them in order to proceed.")
            logger.debug(form.errors)

    """Loop through all imaging resolutions and render a 
    a sub-form for each"""
    unique_image_resolutions = sorted(set(processing_channel_contents.fetch('image_resolution')))
    channel_contents_lists = []
    """ First clear out any existing subforms from previous http requests """
    while len(form.image_resolution_forms) > 0:
        form.image_resolution_forms.pop_entry()

    for ii in range(len(unique_image_resolutions)):
        image_resolution = unique_image_resolutions[ii]
        # logger.debug(f"image resolution: {image_resolution}")

        form.image_resolution_forms.append_entry()
        this_image_resolution_form = form.image_resolution_forms[ii]
        this_image_resolution_form.image_resolution.data = image_resolution
        """ Gather all imaging channels at this image resolution """
        imaging_channel_contents_this_resolution = (imaging_channel_contents & \
            f'image_resolution="{image_resolution}"')
        processing_channel_contents_this_resolution = (processing_channel_contents & \
            f'image_resolution="{image_resolution}"')
        imaging_channels_this_resolution = processing_channel_contents_this_resolution.fetch('channel_name')
        """ Loop through all channels at this resolution and render 
        a sub-sub-form for each """
        channel_contents_lists.append([])
        for jj in range(len(imaging_channels_this_resolution)):
            channel_name = imaging_channels_this_resolution[jj]
            # logger.debug(f"channel: {channel_name}")
            this_image_resolution_form.channel_forms.append_entry()
            this_channel_form = this_image_resolution_form.channel_forms[jj]
            this_channel_form.channel_name.data = channel_name
            """ Figure out which light sheets were imaged """
            this_channel_content_dict = (imaging_channel_contents_this_resolution & \
                f'channel_name="{channel_name}"').fetch1()
           
            channel_contents_lists[ii].append(this_channel_content_dict)
            # logger.debug(this_channel_content) 
        # logger.debug(imaging_channel_dict)

    return render_template('neuroglancer/stitched_data_setup.html',form=form,
        channel_contents_lists=channel_contents_lists,processing_request_table=processing_request_table)


@neuroglancer.route("/neuroglancer/blended_data_setup/"
                    "<username>/<request_name>/<sample_name>/"
                    "<imaging_request_number>/<processing_request_number>",
    methods=['GET','POST'])
@check_imaging_completed
@log_http_requests
def blended_data_setup(username,request_name,sample_name,
    imaging_request_number,processing_request_number): # don't change the url 
    """ A route for displaying a form for users to choose how
    they want their registered data (from a given processing request) 
    visualized in Neuroglancer.
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """

    form = BlendedDataSetupForm(request.form)
    imaging_restrict_dict = dict(username=username,request_name=request_name,
                sample_name=sample_name,imaging_request_number=imaging_request_number)
    imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & imaging_restrict_dict
    processing_restrict_dict = dict(username=username,request_name=request_name,
                sample_name=sample_name,imaging_request_number=imaging_request_number,
                processing_request_number=processing_request_number)

    processing_request_contents = db_lightsheet.Request.ProcessingRequest() & processing_restrict_dict
    processing_request_table = ProcessingRequestTable(processing_request_contents)
    processing_channel_contents = db_lightsheet.Request.ProcessingChannel() & processing_restrict_dict

    if request.method == 'POST':
        logger.debug('POST request')
        # Redis setup for this session
        
        hosturl = os.environ['HOSTURL'] # via dockerenv
        data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']

        if form.validate_on_submit():
            logger.debug("Form validated")
            """ loop through each image resolution sub-form 
            and make a neuroglancer viewer link for each one,
            spawning cloudvolumes for each channel/lightsheet combo """
            kv = redis.Redis(host="redis", decode_responses=True)

            for ii in range(len(form.image_resolution_forms)):
                session_name = secrets.token_hex(6)
                viewer_id = "viewer1" # for storing the viewer info in redis
                # kv.hmset(session_name,{"viewer_id":viewer_id})
                kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

                # Set up environment to be shared by all cloudvolumes
                
                cv_number = 0 # to keep track of how many cloudvolumes in this viewer
                image_resolution_form = form.image_resolution_forms[ii]
                """ Loop through channels and spawn a cloudvolume 
                within this session for each light sheet used """
                for jj in range(len(image_resolution_form.channel_forms)):
                    
                    channel_form = image_resolution_form.channel_forms[jj]
                    channel_name = channel_form.channel_name.data
                    visualize_this_channel = channel_form.viz.data
                    if not visualize_this_channel:
                        continue
                    cv_number += 1 
                    cv_container_name = f'{session_name}_blended_{channel_name}_container'
                    cv_name = f"{channel_name}_blended"
                    cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                        sample_name,f'imaging_request_{imaging_request_number}','viz',
                        f'processing_request_{processing_request_number}','blended',
                        f'channel_{channel_name}',      
                        f'channel{channel_name}_blended')      
                    layer_type = "image"
                    """ send the data to the viewer-launcher
                    to launch the cloudvolume """                       
                    cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
                        cv_container_name=cv_container_name,
                        layer_type=layer_type,session_name=session_name)
                    requests.post('http://viewer-launcher:5005/cvlauncher',json=cv_dict)
                    logger.debug("Made post request to viewer-launcher to launch cloudvolume")

                    """ Enter the cv information into redis
                    so I can get it from within the neuroglancer container """
                    kv.hmset(session_name, {f"cv{cv_number}_container_name": cv_container_name,
                        f"cv{cv_number}_name": cv_name, f"layer{cv_number}_type":layer_type})
                    # increment the number of cloudvolumes so it is up to date
                    kv.hincrby(session_name,'cv_count',1)
                    # register with the confproxy so that it can be seen from outside the nglancer network
                    proxy_h = pp.progproxy(target_hname='confproxy')
                    proxypath = os.path.join('cloudvols',session_name,cv_name)
                    proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:1337")
                
                """ Now spawn a neuroglancer container which will make
                layers for each of the spawned cloudvolumes """
                ng_container_name = f'{session_name}_ng_container'
                ng_dict = {}
                ng_dict['hosturl'] = hosturl
                ng_dict['ng_container_name'] = ng_container_name
                ng_dict['session_name'] = session_name
                """ send the data to the viewer-launcher
                to launch the ng viewer """                       
                
                requests.post('http://viewer-launcher:5005/nglauncher',json=ng_dict)
                logger.debug("Made post request to viewer-launcher to launch ng viewer")
                
                # Add the ng container name to redis session key level
                kv.hmset(session_name, {"ng_container_name": ng_container_name})
                # Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network 
                proxy_h.addroute(proxypath=f'viewers/{session_name}', proxytarget=f"http://{ng_container_name}:8080/")
                logger.debug(f"Added {ng_container_name} to redis and confproxy")

                # Spin until the neuroglancer viewer token from redis becomes available 
                # (may be waiting on the neuroglancer container to finish writing to redis)
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
                logger.debug("Proxy contents:")
                response=proxy_h.getroutes()
                logger.debug(response.text)
                # logger.debug(proxy_contents)
                
                neuroglancerurl = f"https://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
                logger.debug("URL IS:")
                logger.debug(neuroglancerurl)
                return render_template('neuroglancer/viewer_link.html',neuroglancerurl=neuroglancerurl)
                

        else: # form not validated
            flash("There were errors below. Correct them in order to proceed.")
            logger.debug(form.errors)

    """Loop through all imaging resolutions and render a 
    a sub-form for each"""
    unique_image_resolutions = sorted(set(processing_channel_contents.fetch('image_resolution')))
    channel_contents_lists = []
    """ First clear out any existing subforms from previous http requests """
    while len(form.image_resolution_forms) > 0:
        form.image_resolution_forms.pop_entry()

    for ii in range(len(unique_image_resolutions)):
        image_resolution = unique_image_resolutions[ii]
        # logger.debug(f"image resolution: {image_resolution}")

        form.image_resolution_forms.append_entry()
        this_image_resolution_form = form.image_resolution_forms[ii]
        this_image_resolution_form.image_resolution.data = image_resolution
        """ Gather all imaging channels at this image resolution """
        imaging_channel_contents_this_resolution = (imaging_channel_contents & \
            f'image_resolution="{image_resolution}"')
        processing_channel_contents_this_resolution = (processing_channel_contents & \
            f'image_resolution="{image_resolution}"')
        imaging_channels_this_resolution = processing_channel_contents_this_resolution.fetch('channel_name')
        """ Loop through all channels at this resolution and render 
        a sub-sub-form for each """
        channel_contents_lists.append([])
        for jj in range(len(imaging_channels_this_resolution)):
            channel_name = imaging_channels_this_resolution[jj]
            # logger.debug(f"channel: {channel_name}")
            this_image_resolution_form.channel_forms.append_entry()
            this_channel_form = this_image_resolution_form.channel_forms[jj]
            this_channel_form.channel_name.data = channel_name
            """ Figure out which light sheets were imaged """
            this_channel_content_dict = (imaging_channel_contents_this_resolution & \
                f'channel_name="{channel_name}"').fetch1()
           
            channel_contents_lists[ii].append(this_channel_content_dict)
            # logger.debug(this_channel_content) 
        # logger.debug(imaging_channel_dict)

    return render_template('neuroglancer/blended_data_setup.html',form=form,
        channel_contents_lists=channel_contents_lists,processing_request_table=processing_request_table)

@neuroglancer.route("/neuroglancer/registered_data_setup/"
                    "<username>/<request_name>/<sample_name>/"
                    "<imaging_request_number>/<processing_request_number>",
    methods=['GET','POST'])
@check_imaging_completed
@log_http_requests
def registered_data_setup(username,request_name,sample_name,
    imaging_request_number,processing_request_number): # don't change the url 
    """ A route for displaying a form for users to choose how
    they want their registered data (from a given processing request) 
    visualized in Neuroglancer.
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """

    form = RegisteredDataSetupForm(request.form)
    imaging_restrict_dict = dict(username=username,request_name=request_name,
                sample_name=sample_name,imaging_request_number=imaging_request_number)
    imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & imaging_restrict_dict
    processing_restrict_dict = dict(username=username,request_name=request_name,
                sample_name=sample_name,imaging_request_number=imaging_request_number,
                processing_request_number=processing_request_number)

    processing_request_contents = db_lightsheet.Request.ProcessingRequest() & processing_restrict_dict
    
    processing_resolution_request_contents = db_lightsheet.Request.ProcessingResolutionRequest() & \
        processing_restrict_dict
    
    processing_request_table = ProcessingRequestTable(processing_request_contents)
    
    processing_channel_contents = db_lightsheet.Request.ProcessingChannel() & processing_restrict_dict

    if request.method == 'POST':
        logger.debug('POST request')
        # Redis setup for this session
        
        hosturl = os.environ['HOSTURL'] # via dockerenv
        data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']

        if form.validate_on_submit():
            logger.debug("Form validated")
            """ loop through each image resolution sub-form 
            and make a neuroglancer viewer link for each one,
            spawning cloudvolumes for each channel/lightsheet combo """
            kv = redis.Redis(host="redis", decode_responses=True)

            for ii in range(len(form.image_resolution_forms)):
                session_name = secrets.token_hex(6)
                viewer_id = "viewer1" # for storing the viewer info in redis
                # kv.hmset(session_name,{"viewer_id":viewer_id})
                kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

                # Set up environment to be shared by all cloudvolumes
                
                cv_number = 0 # to keep track of how many cloudvolumes in this viewer
                image_resolution_form = form.image_resolution_forms[ii]
                image_resolution = image_resolution_form.image_resolution.data
                this_processing_resolution_request_contents = processing_resolution_request_contents & \
                    f'image_resolution="{image_resolution}"'
                atlas_name = this_processing_resolution_request_contents.fetch1('atlas_name')
                """ Loop through channels and spawn a cloudvolume 
                within this session for each light sheet used """
                for jj in range(len(image_resolution_form.channel_forms)):
                    
                    channel_form = image_resolution_form.channel_forms[jj]
                    channel_name = channel_form.channel_name.data
                    visualize_this_channel = channel_form.viz.data
                    if not visualize_this_channel:
                        continue
                   
                    """ Set up cloudvolume params"""

                    cv_number += 1 
                    cv_container_name = f'{session_name}_registered_{channel_name}_container'
                    cv_name = f"ch{channel_name}_registered" # what shows up as the layer name in neuroglancer
                    cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                        sample_name,f'imaging_request_{imaging_request_number}','viz',
                        f'processing_request_{processing_request_number}','registered',
                        f'channel_{channel_name}_regch',      
                        f'channel{channel_name}_registered')      
                    layer_type = "image"
                    
                    """ send the data to the viewer-launcher
                    to launch the cloudvolume """    

                    cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
                        cv_container_name=cv_container_name,
                        layer_type=layer_type,session_name=session_name)
                    requests.post('http://viewer-launcher:5005/cvlauncher',json=cv_dict)
                    logger.debug("Made post request to viewer-launcher to launch cloudvolume")

                    """ Enter the cv information into redis
                    so I can get it from within the neuroglancer container """

                    kv.hmset(session_name, {f"cv{cv_number}_container_name": cv_container_name,
                        f"cv{cv_number}_name": cv_name, f"layer{cv_number}_type":layer_type})                    
                    kv.hincrby(session_name,'cv_count',1)
                    
                    """ register with the confproxy so that the cloudvolume
                    can be seen from outside the docker network """
                    
                    proxy_h = pp.progproxy(target_hname='confproxy')
                    proxypath = os.path.join('cloudvols',session_name,cv_name)
                    proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:1337")
                    
                    """ Check if atlas was requested """
                    
                    visualize_atlas = channel_form.viz_atlas.data
                    if not visualize_atlas:
                        continue

                    """ Set up cloudvolume params for the atlas"""

                    cv_number += 1 
                    cv_container_name = f'{session_name}_atlas'
                    cv_name = f"ch{channel_name}_allen_atlas" # what shows up as the layer name in neuroglancer
                    # if 'allen' in atlas_name.lower():
                    #     cv_path = os.path.join('/jukebox','LightSheetData',
                    #         'atlas','neuroglancer','atlas','allenatlas_2017')
                    # elif 'princeton' in atlas_name.lower():
                    cv_path = os.path.join('/jukebox','LightSheetData',
                        'atlas','neuroglancer','atlas','allenatlas_2017')
                    layer_type = "segmentation"
                    
                    """ send the data to the viewer-launcher
                    to launch the cloudvolume """    

                    cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
                        cv_container_name=cv_container_name,
                        layer_type=layer_type,session_name=session_name)
                    requests.post('http://viewer-launcher:5005/cvlauncher',json=cv_dict)
                    logger.debug("Made post request to viewer-launcher to launch atlas cloudvolume")

                    """ Enter the cv information into redis
                    so I can get it from within the neuroglancer container """

                    kv.hmset(session_name, {f"cv{cv_number}_container_name": cv_container_name,
                        f"cv{cv_number}_name": cv_name, f"layer{cv_number}_type":layer_type})                    
                    kv.hincrby(session_name,'cv_count',1)
                    
                    """ register with the confproxy so that the cloudvolume
                    can be seen from outside the docker network """
                    
                    proxy_h = pp.progproxy(target_hname='confproxy')
                    proxypath = os.path.join('cloudvols',session_name,cv_name)
                    proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:1337")

                """ Now spawn a neuroglancer container which will make
                layers for each of the spawned cloudvolumes """
                ng_container_name = f'{session_name}_ng_container'
                ng_dict = {}
                ng_dict['hosturl'] = hosturl
                ng_dict['ng_container_name'] = ng_container_name
                ng_dict['session_name'] = session_name
                """ send the data to the viewer-launcher
                to launch the ng viewer """                       
                
                requests.post('http://viewer-launcher:5005/nglauncher',json=ng_dict)
                logger.debug("Made post request to viewer-launcher to launch ng viewer")
                
                # Add the ng container name to redis session key level
                kv.hmset(session_name, {"ng_container_name": ng_container_name})
                # Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network 
                proxy_h.addroute(proxypath=f'viewers/{session_name}', proxytarget=f"http://{ng_container_name}:8080/")
                logger.debug(f"Added {ng_container_name} to redis and confproxy")

                # Spin until the neuroglancer viewer token from redis becomes available 
                # (may be waiting on the neuroglancer container to finish writing to redis)
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
                logger.debug("Proxy contents:")
                response=proxy_h.getroutes()
                logger.debug(response.text)
                # logger.debug(proxy_contents)
                
                neuroglancerurl = f"https://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
                logger.debug("URL IS:")
                logger.debug(neuroglancerurl)
                return render_template('neuroglancer/viewer_link.html',neuroglancerurl=neuroglancerurl)
                

        else: # form not validated
            flash("There were errors below. Correct them in order to proceed.")
            logger.debug(form.errors)

    """Loop through all imaging resolutions and render a 
    a sub-form for each"""
    unique_image_resolutions = sorted(set(processing_channel_contents.fetch('image_resolution')))
    channel_contents_lists = []
    """ First clear out any existing subforms from previous http requests """
    while len(form.image_resolution_forms) > 0:
        form.image_resolution_forms.pop_entry()

    for ii in range(len(unique_image_resolutions)):
        image_resolution = unique_image_resolutions[ii]
        # logger.debug(f"image resolution: {image_resolution}")

        form.image_resolution_forms.append_entry()
        this_image_resolution_form = form.image_resolution_forms[ii]
        this_image_resolution_form.image_resolution.data = image_resolution
        """ Gather all imaging channels at this image resolution """
        imaging_channel_contents_this_resolution = (imaging_channel_contents & \
            f'image_resolution="{image_resolution}"')
        processing_channel_contents_this_resolution = (processing_channel_contents & \
            f'image_resolution="{image_resolution}"')
        imaging_channels_this_resolution = processing_channel_contents_this_resolution.fetch('channel_name')
        """ Loop through all channels at this resolution and render 
        a sub-sub-form for each """
        channel_contents_lists.append([])
        for jj in range(len(imaging_channels_this_resolution)):
            channel_name = imaging_channels_this_resolution[jj]
            # logger.debug(f"channel: {channel_name}")
            this_image_resolution_form.channel_forms.append_entry()
            this_channel_form = this_image_resolution_form.channel_forms[jj]
            this_channel_form.channel_name.data = channel_name
            """ Figure out which light sheets were imaged """
            this_channel_content_dict = (imaging_channel_contents_this_resolution & \
                f'channel_name="{channel_name}"').fetch1()
           
            channel_contents_lists[ii].append(this_channel_content_dict)
            # logger.debug(this_channel_content) 
        # logger.debug(imaging_channel_dict)

    return render_template('neuroglancer/registered_data_setup.html',form=form,
        channel_contents_lists=channel_contents_lists,processing_request_table=processing_request_table)

@neuroglancer.route("/neuroglancer/downsized_data_setup/"
                    "<username>/<request_name>/<sample_name>/"
                    "<imaging_request_number>/<processing_request_number>",
    methods=['GET','POST'])
@check_imaging_completed
@log_http_requests
def downsized_data_setup(username,request_name,sample_name,
    imaging_request_number,processing_request_number): # don't change the url 
    """ A route for displaying a form for users to choose how
    they want their downsized data (from a given processing request) 
    visualized in Neuroglancer.
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """

    form = DownsizedDataSetupForm(request.form)
    imaging_restrict_dict = dict(username=username,request_name=request_name,
                sample_name=sample_name,imaging_request_number=imaging_request_number)
    imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & imaging_restrict_dict
    processing_restrict_dict = dict(username=username,request_name=request_name,
                sample_name=sample_name,imaging_request_number=imaging_request_number,
                processing_request_number=processing_request_number)

    processing_request_contents = db_lightsheet.Request.ProcessingRequest() & processing_restrict_dict
    
    processing_resolution_request_contents = db_lightsheet.Request.ProcessingResolutionRequest() & \
        processing_restrict_dict
    
    processing_request_table = ProcessingRequestTable(processing_request_contents)
    
    processing_channel_contents = db_lightsheet.Request.ProcessingChannel() & processing_restrict_dict

    if request.method == 'POST':
        logger.debug('POST request')
        # Redis setup for this session
        
        hosturl = os.environ['HOSTURL'] # via dockerenv
        data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']

        if form.validate_on_submit():
            logger.debug("Form validated")
            """ loop through each image resolution sub-form 
            and make a neuroglancer viewer link for each one,
            spawning cloudvolumes for each channel/lightsheet combo """
            kv = redis.Redis(host="redis", decode_responses=True)

            for ii in range(len(form.image_resolution_forms)):
                session_name = secrets.token_hex(6)
                viewer_id = "viewer1" # for storing the viewer info in redis
                # kv.hmset(session_name,{"viewer_id":viewer_id})
                kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

                # Set up environment to be shared by all cloudvolumes
                
                cv_number = 0 # to keep track of how many cloudvolumes in this viewer
                image_resolution_form = form.image_resolution_forms[ii]
                image_resolution = image_resolution_form.image_resolution.data
                
                """ Loop through channels and spawn a cloudvolume 
                within this session for each channel used """
                for jj in range(len(image_resolution_form.channel_forms)):
                    channel_form = image_resolution_form.channel_forms[jj]
                    channel_name = channel_form.channel_name.data
                    visualize_this_channel = channel_form.viz.data
                    if not visualize_this_channel:
                        continue
                   
                    """ Set up cloudvolume params"""

                    cv_number += 1 
                    cv_container_name = f'{session_name}_downsized_{channel_name}_container'
                    cv_name = f"ch{channel_name}_downsized" # what shows up as the layer name in neuroglancer
                    cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                        sample_name,f'imaging_request_{imaging_request_number}','viz',
                        f'processing_request_{processing_request_number}','downsized',
                        f'channel_{channel_name}',      
                        f'channel{channel_name}_downsized')      
                    layer_type = "image"
                    
                    """ send the data to the viewer-launcher
                    to launch the cloudvolume """    

                    cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
                        cv_container_name=cv_container_name,
                        layer_type=layer_type,session_name=session_name)
                    requests.post('http://viewer-launcher:5005/cvlauncher',json=cv_dict)
                    logger.debug("Made post request to viewer-launcher to launch cloudvolume")

                    """ Enter the cv information into redis
                    so I can get it from within the neuroglancer container """

                    kv.hmset(session_name, {f"cv{cv_number}_container_name": cv_container_name,
                        f"cv{cv_number}_name": cv_name, f"layer{cv_number}_type":layer_type})                    
                    kv.hincrby(session_name,'cv_count',1)
                    
                    """ register with the confproxy so that the cloudvolume
                    can be seen from outside the docker network """
                    
                    proxy_h = pp.progproxy(target_hname='confproxy')
                    proxypath = os.path.join('cloudvols',session_name,cv_name)
                    proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:1337")

                """ Now spawn a neuroglancer container which will make
                layers for each of the spawned cloudvolumes """
                ng_container_name = f'{session_name}_ng_container'
                ng_dict = {}
                ng_dict['hosturl'] = hosturl
                ng_dict['ng_container_name'] = ng_container_name
                ng_dict['session_name'] = session_name
                """ send the data to the viewer-launcher
                to launch the ng viewer """                       
                
                requests.post('http://viewer-launcher:5005/nglauncher',json=ng_dict)
                logger.debug("Made post request to viewer-launcher to launch ng viewer")
                
                # Add the ng container name to redis session key level
                kv.hmset(session_name, {"ng_container_name": ng_container_name})
                # Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network 
                proxy_h.addroute(proxypath=f'viewers/{session_name}', proxytarget=f"http://{ng_container_name}:8080/")
                logger.debug(f"Added {ng_container_name} to redis and confproxy")

                # Spin until the neuroglancer viewer token from redis becomes available 
                # (may be waiting on the neuroglancer container to finish writing to redis)
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
                logger.debug("Proxy contents:")
                response=proxy_h.getroutes()
                logger.debug(response.text)
                # logger.debug(proxy_contents)
                
                neuroglancerurl = f"https://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
                logger.debug("URL IS:")
                logger.debug(neuroglancerurl)
                return render_template('neuroglancer/viewer_link.html',neuroglancerurl=neuroglancerurl)
                

        else: # form not validated
            flash("There were errors below. Correct them in order to proceed.")
            logger.debug(form.errors)

    """Loop through all imaging resolutions and render a 
    a sub-form for each"""
    unique_image_resolutions = sorted(set(processing_channel_contents.fetch('image_resolution')))
    channel_contents_lists = []
    """ First clear out any existing subforms from previous http requests """
    while len(form.image_resolution_forms) > 0:
        form.image_resolution_forms.pop_entry()

    for ii in range(len(unique_image_resolutions)):
        image_resolution = unique_image_resolutions[ii]
        # logger.debug(f"image resolution: {image_resolution}")

        form.image_resolution_forms.append_entry()
        this_image_resolution_form = form.image_resolution_forms[ii]
        this_image_resolution_form.image_resolution.data = image_resolution
        """ Gather all imaging channels at this image resolution """
        imaging_channel_contents_this_resolution = (imaging_channel_contents & \
            f'image_resolution="{image_resolution}"')
        processing_channel_contents_this_resolution = (processing_channel_contents & \
            f'image_resolution="{image_resolution}"')
        imaging_channels_this_resolution = processing_channel_contents_this_resolution.fetch('channel_name')
        """ Loop through all channels at this resolution and render 
        a sub-sub-form for each """
        channel_contents_lists.append([])
        for jj in range(len(imaging_channels_this_resolution)):
            channel_name = imaging_channels_this_resolution[jj]
            # logger.debug(f"channel: {channel_name}")
            this_image_resolution_form.channel_forms.append_entry()
            this_channel_form = this_image_resolution_form.channel_forms[jj]
            this_channel_form.channel_name.data = channel_name
            """ Figure out which light sheets were imaged """
            this_channel_content_dict = (imaging_channel_contents_this_resolution & \
                f'channel_name="{channel_name}"').fetch1()
           
            channel_contents_lists[ii].append(this_channel_content_dict)
            # logger.debug(this_channel_content) 
        # logger.debug(imaging_channel_dict)

    return render_template('neuroglancer/downsized_data_setup.html',form=form,
        channel_contents_lists=channel_contents_lists,processing_request_table=processing_request_table)



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
