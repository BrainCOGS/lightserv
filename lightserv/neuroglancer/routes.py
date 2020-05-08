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
from collections import OrderedDict
from datetime import datetime, timedelta
from .forms import (RawDataSetupForm,StitchedDataSetupForm,
    BlendedDataSetupForm, RegisteredDataSetupForm,
    DownsizedDataSetupForm,GeneralDataSetupForm)
from .tables import (ImagingRequestTable, ProcessingRequestTable,
    CloudVolumeLayerTable,MultiLightSheetCloudVolumeLayerTable)
from lightserv import cel, db_lightsheet
from lightserv.main.utils import (check_imaging_completed,
    check_imaging_request_precomputed,log_http_requests)
from .tasks import ng_viewer_checker
import progproxy as pp

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate=False

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
        neuroglancer_url_dict = {}
        cv_table_dict = {}
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
                image_resolution = image_resolution_form.image_resolution.data
                neuroglancer_url_dict[image_resolution] = {}
                cv_contents_dict_list_this_resolution = []
                """ Loop through channels and spawn a cloudvolume 
                within this session for each light sheet used """
                for jj in range(len(image_resolution_form.channel_forms)):
                    cv_contents_dict_this_channel = {}
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
                        this_restrict_dict = {
                            f'channel_name="{channel_name}"'}
                        this_imaging_channel_contents =  imaging_channel_contents & \
                            this_restrict_dict

                        rawdata_subfolder = this_imaging_channel_contents.fetch1('rawdata_subfolder')          
                        raw_data_path = os.path.join(data_bucket_rootpath,username,
                             request_name,sample_name,
                             f"imaging_request_{imaging_request_number}",
                             "raw",rawdata_subfolder)
                        cv_contents_dict_this_channel['image_resolution'] = image_resolution
                        cv_contents_dict_this_channel['lightsheet'] = lightsheet
                        cv_contents_dict_this_channel['cv_name'] = cv_name
                        cv_contents_dict_this_channel['cv_path'] = cv_path
                        cv_contents_dict_this_channel['data_path'] = raw_data_path
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
                        cv_contents_dict_list_this_resolution.append(cv_contents_dict_this_channel)
                cv_table = MultiLightSheetCloudVolumeLayerTable(cv_contents_dict_list_this_resolution)
                cv_table_dict[image_resolution] = cv_table
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
                neuroglancer_url_dict[image_resolution] = neuroglancerurl
                logger.debug(neuroglancerurl)
            return render_template('neuroglancer/viewer_links.html',
                datatype='raw',
                url_dict=neuroglancer_url_dict,cv_table_dict=cv_table_dict)

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
    joined_processing_channel_contents = imaging_channel_contents * processing_channel_contents

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
            neuroglancer_url_dict = {} # keys are image resolution, values are urls
            cv_table_dict = {}

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
                within this session for each light sheet used """
                cv_contents_dict_list_this_resolution = []

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
                        this_restrict_dict = {
                            f'channel_name="{channel_name}"'}
                        this_processing_channel_contents =  joined_processing_channel_contents & \
                            this_restrict_dict
                        rawdata_subfolder = this_processing_channel_contents.fetch1('rawdata_subfolder')
                        channel_index = this_processing_channel_contents.fetch1('imspector_channel_index')
                        channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
                        stitched_data_path = os.path.join(rawdata_path,
                            f'{rawdata_subfolder}_ch{channel_index_padded}_{lightsheet}_lightsheet_ts_out')
                        cv_contents_dict_this_channel['image_resolution'] = image_resolution
                        cv_contents_dict_this_channel['lightsheet'] = lightsheet
                        cv_contents_dict_this_channel['cv_name'] = cv_name
                        cv_contents_dict_this_channel['cv_path'] = cv_path
                        cv_contents_dict_this_channel['data_path'] = blended_data_path
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
                        cv_contents_dict_list_this_resolution.append(cv_contents_dict_this_channel)
                cv_table = MultiLightSheetCloudVolumeLayerTable(cv_contents_dict_list_this_resolution)
                cv_table_dict[image_resolution] = cv_table
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
                neuroglancer_url_dict[image_resolution] = neuroglancerurl

                logger.debug("URL IS:")
                logger.debug(neuroglancerurl)
            return render_template('neuroglancer/viewer_links.html',
                datatype='stitched',
                url_dict=neuroglancer_url_dict,cv_table_dict=cv_table_dict)
                

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
    joined_processing_channel_contents = imaging_channel_contents * processing_channel_contents
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
            neuroglancer_url_dict = {}
            cv_table_dict = {}
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
                within this session for each light sheet used """
                cv_contents_dict_list_this_resolution = []
                for jj in range(len(image_resolution_form.channel_forms)):
                    cv_contents_dict_this_channel = {}

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
                    this_restrict_dict = {
                        f'channel_name="{channel_name}"'}
                    this_processing_channel_contents =  joined_processing_channel_contents & \
                        this_restrict_dict

                    rawdata_subfolder = this_processing_channel_contents.fetch1('rawdata_subfolder')
                    channel_index = this_processing_channel_contents.fetch1('imspector_channel_index')
                    channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
                    blended_data_path = os.path.join(data_bucket_rootpath,username,
                             request_name,sample_name,
                             f"imaging_request_{imaging_request_number}",
                             "output",
                             f"processing_request_{processing_request_number}",
                             f"resolution_{image_resolution}",
                             "full_sizedatafld",
                             f"{rawdata_subfolder}_ch{channel_index_padded}")
                    cv_contents_dict_this_channel['image_resolution'] = image_resolution
                    cv_contents_dict_this_channel['cv_name'] = cv_name
                    cv_contents_dict_this_channel['cv_path'] = cv_path
                    cv_contents_dict_this_channel['data_path'] = blended_data_path
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
                    cv_contents_dict_list_this_resolution.append(cv_contents_dict_this_channel)
                cv_table = CloudVolumeLayerTable(cv_contents_dict_list_this_resolution)
                cv_table_dict[image_resolution] = cv_table
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
                neuroglancer_url_dict[image_resolution] = neuroglancerurl
                logger.debug("URL IS:")
                logger.debug(neuroglancerurl)
            return render_template('neuroglancer/viewer_links.html',
                datatype='blended',
                url_dict=neuroglancer_url_dict,cv_table_dict=cv_table_dict)
                

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
    joined_processing_channel_contents = imaging_channel_contents * processing_channel_contents
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
            neuroglancer_url_dict = {}
            cv_table_dict = {}
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
                cv_contents_dict_list_this_resolution = []

                for jj in range(len(image_resolution_form.channel_forms)):
                    cv_contents_dict_this_channel = {}

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
                    this_restrict_dict = {
                        f'channel_name="{channel_name}"'}
                    this_processing_channel_contents =  joined_processing_channel_contents & \
                        this_restrict_dict

                    rawdata_subfolder = this_processing_channel_contents.fetch1('rawdata_subfolder')
                    channel_index = this_processing_channel_contents.fetch1('imspector_channel_index')
                    channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
                    downsized_data_path = os.path.join(data_bucket_rootpath,username,
                             request_name,sample_name,
                             f"imaging_request_{imaging_request_number}",
                             "output",
                             f"processing_request_{processing_request_number}",
                             f"resolution_{image_resolution}",
                             f'{rawdata_subfolder}_resized_ch{channel_index_padded}_resampledforelastix.tif')
                    cv_contents_dict_this_channel['image_resolution'] = image_resolution
                    cv_contents_dict_this_channel['cv_name'] = cv_name
                    cv_contents_dict_this_channel['cv_path'] = cv_path
                    cv_contents_dict_this_channel['data_path'] = downsized_data_path


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
                    cv_contents_dict_list_this_resolution.append(cv_contents_dict_this_channel)
                cv_table = CloudVolumeLayerTable(cv_contents_dict_list_this_resolution)
                cv_table_dict[image_resolution] = cv_table
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
                neuroglancer_url_dict[image_resolution] = neuroglancerurl
                logger.debug("URL IS:")
                logger.debug(neuroglancerurl)
            return render_template('neuroglancer/viewer_links.html',
                datatype='downsized',
                url_dict=neuroglancer_url_dict,cv_table_dict=cv_table_dict)
                

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
    joined_processing_channel_contents = imaging_channel_contents * processing_channel_contents
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
            neuroglancer_url_dict = {}
            cv_table_dict = {}
            for ii in range(len(form.image_resolution_forms)):
                """ Establish the viewer session variables """
                session_name = secrets.token_hex(6)
                viewer_id = "viewer1" # for storing the viewer info in redis. Only ever one per session
                # initialize the number of cloudvolumes in this ng session
                # as well as the key that I will store which cvs need an atlas overlay
                # based on user input
                kv.hmset(session_name,{"cv_count":0,"cvs_need_atlas":""}) 
                cv_number = 0 # to keep track of how many cloudvolumes in this viewer/session

                image_resolution_form = form.image_resolution_forms[ii]
                image_resolution = image_resolution_form.image_resolution.data
                this_processing_resolution_request_contents = processing_resolution_request_contents & \
                    f'image_resolution="{image_resolution}"'
                atlas_name = this_processing_resolution_request_contents.fetch1('atlas_name')
                logger.debug("Atlas being used here is:")
                logger.debug(atlas_name)
                """ Only want to generate a single cloudvolume container for the 
                atlas since it is the same atlas for each channel that requests
                it as an overlay. In the loop over channels, set this flag to True
                if any of the channels request an atlas overlay. """
                atlas_requested = False
                """ Loop through channels and spawn a cloudvolume 
                within this session for each light sheet used """
                cv_contents_dict_list_this_resolution = []
                for jj in range(len(image_resolution_form.channel_forms)): 
                    cv_contents_dict_this_channel = {}
                    channel_form = image_resolution_form.channel_forms[jj]
                    channel_name = channel_form.channel_name.data
                    visualize_this_channel = channel_form.viz.data
                    channel_restrict_dict = dict(channel_name=channel_name)
                    this_processing_channel_contents = processing_channel_contents & channel_restrict_dict
                    lightsheet_channel_str = this_processing_channel_contents.fetch1('lightsheet_channel_str')
                    """ Set up cloudvolume params"""

                    cv_number += 1 
                    cv_container_name = f'{session_name}_registered_{channel_name}_container'
                    cv_name = f"ch{channel_name}_registered" # what shows up as the layer name in neuroglancer
                    cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                        sample_name,f'imaging_request_{imaging_request_number}','viz',
                        f'processing_request_{processing_request_number}','registered',
                        f'channel_{channel_name}_{lightsheet_channel_str}',      
                        f'channel{channel_name}_registered')
                    this_restrict_dict = {
                        f'channel_name="{channel_name}"'}
                    this_processing_channel_contents =  joined_processing_channel_contents & \
                        this_restrict_dict

                    (rawdata_subfolder,channel_index,
                        lightsheet_channel_str) = this_processing_channel_contents.fetch1(
                        'rawdata_subfolder','imspector_channel_index','lightsheet_channel_str')
                    channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
                    registered_data_base_path = os.path.join(data_bucket_rootpath,username,
                             request_name,sample_name,
                             f"imaging_request_{imaging_request_number}",
                             "output",
                             f"processing_request_{processing_request_number}",
                             f"resolution_{image_resolution}",
                             "elastix")      
                    if lightsheet_channel_str == 'regch':
                        registered_data_path = os.path.join(
                            registered_data_base_path,'result.1.tif')
                    else:
                        registered_data_path = os.path.join(
                            registered_data_base_path,
                            rawdata_subfolder+f'_resized_ch{channel_index_padded}','result.tif')
                    cv_contents_dict_this_channel['image_resolution'] = image_resolution
                    cv_contents_dict_this_channel['cv_name'] = cv_name
                    cv_contents_dict_this_channel['cv_path'] = cv_path
                    cv_contents_dict_this_channel['data_path'] = registered_data_path
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
                    
                    """ Check if atlas overlay was requested """
                    overlay_atlas_this_channel = channel_form.viz_atlas.data
                    if overlay_atlas_this_channel:
                        atlas_requested=True
                        cvs_need_atlas = kv.hgetall(session_name)['cvs_need_atlas']
                        cvs_need_atlas+= f'{cv_name},'
                        kv.hmset(session_name,{'cvs_need_atlas':cvs_need_atlas})

                    """ register with the confproxy so that the cloudvolume
                    can be seen from outside the docker network """
                    
                    proxy_h = pp.progproxy(target_hname='confproxy')
                    proxypath = os.path.join('cloudvols',session_name,cv_name)
                    proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:1337")
                    cv_contents_dict_list_this_resolution.append(cv_contents_dict_this_channel)
                cv_table = CloudVolumeLayerTable(cv_contents_dict_list_this_resolution)
                cv_table_dict[image_resolution] = cv_table
                   
                """ If atlas was requested for any of the channels,
                then only need to generate it once. Do that here  """
                if atlas_requested:    
                    """ Set up cloudvolume params for the atlas"""

                    cv_number += 1 
                    cv_container_name = f'{session_name}_atlas'
                    cv_name = atlas_name # what shows up as the layer name in neuroglancer
                    logger.debug("Cloudvolume name is:")
                    logger.debug(cv_name)
                    if 'allen' in atlas_name.lower():
                        cv_path = os.path.join('/jukebox','LightSheetData',
                            'atlas','neuroglancer','atlas','allenatlas_2017')
                    elif 'princeton' in atlas_name.lower():
                        cv_path = os.path.join('/jukebox','LightSheetData',
                            'atlas','neuroglancer','atlas','princetonmouse')
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
                
                requests.post('http://viewer-launcher:5005/ng_reg_launcher',json=ng_dict)
                logger.debug("Made post request to viewer-launcher to launch ng reg viewer")
                
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
                neuroglancer_url_dict[image_resolution] = neuroglancerurl
                logger.debug("URL IS:")
                logger.debug(neuroglancerurl)
            return render_template('neuroglancer/viewer_links.html',
                datatype='registered',
                url_dict=neuroglancer_url_dict,cv_table_dict=cv_table_dict)
                

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


@neuroglancer.route("/neuroglancer/general_data_setup/"
                    "<username>/<request_name>/<sample_name>/"
                    "<imaging_request_number>/<processing_request_number>",
    methods=['GET','POST'])
@check_imaging_completed
@log_http_requests
def general_data_setup(username,request_name,sample_name,
    imaging_request_number,processing_request_number): # don't change the url 
    """ A route for displaying a form for users to choose how
    they want to view any of their precomputed data products
    (ranging from raw to registered) for a given processing request. 

    The route spawns cloudvolumes for each layer and then 
    makes neuroglancer viewers for each data type/image resolution combo
    and provides the links to the user. """

    form = GeneralDataSetupForm(request.form)
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
            
            """ loop through each data type image resolution sub-form 
            and make a neuroglancer viewer link for each one,
            spawning cloudvolumes """
            
            kv = redis.Redis(host="redis", decode_responses=True)
            neuroglancer_url_dict = OrderedDict({
                'Raw':{},
                'Stitched':{},
                'Blended':{},
                'Downsized':{},
                'Registered':{}
                })
            for ii in range(len(form.image_resolution_forms)):
                image_resolution_form = form.image_resolution_forms[ii]
                image_resolution = image_resolution_form.image_resolution.data

                raw_channel_forms = image_resolution_form.raw_channel_forms
                stitched_channel_forms = image_resolution_form.stitched_channel_forms
                blended_channel_forms = image_resolution_form.blended_channel_forms
                downsized_channel_forms = image_resolution_form.downsized_channel_forms
                registered_channel_forms = image_resolution_form.registered_channel_forms

                any_raw_channels = [(ch_form['viz_left_lightsheet'].data 
                    or ch_form['viz_right_lightsheet'].data) for ch_form in raw_channel_forms]

                any_stitched_channels = [(ch_form['viz_left_lightsheet'].data 
                    or ch_form['viz_right_lightsheet'].data) for ch_form in stitched_channel_forms]

                any_blended_channels = [ch_form['viz'].data for ch_form in blended_channel_forms]
                
                any_downsized_channels = [ch_form['viz'].data for ch_form in downsized_channel_forms]

                any_registered_channels = [(ch_form['viz'].data 
                    or ch_form['viz_atlas'].data) for ch_form in registered_channel_forms]

                """ Raw data """
                if any(any_raw_channels):
                    logger.debug("have raw data!")
                    session_name = secrets.token_hex(6)
                    viewer_id = "viewer1" # for storing the viewer info in redis. Only ever one per session
                    # initialize this redis session key
                    kv.hmset(session_name,{"cv_count":0,"cvs_need_atlas":""}) 
                    cv_number = 0 # to keep track of how many cloudvolumes in this viewer/session
                    """ Loop through channels and spawn a cloudvolume 
                    within this session for each light sheet used """
                    for jj in range(len(raw_channel_forms)):
                        channel_form = raw_channel_forms[jj]
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
                            layer_type = 'image'
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
                
                    """ Raw data neuroglancer container """
                    ng_container_name = f'{session_name}_ng_container'
                    ng_dict = {}
                    ng_dict['hosturl'] = hosturl
                    ng_dict['ng_container_name'] = ng_container_name
                    ng_dict['session_name'] = session_name
                    """ send the data to the viewer-launcher
                    to launch the ng viewer """                       
                    requests.post('http://viewer-launcher:5005/nglauncher',json=ng_dict)                    
                    """ Add the ng container name to redis session key level """
                    kv.hmset(session_name, {"ng_container_name": ng_container_name})
                    """ Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network """
                    proxy_h.addroute(proxypath=f'viewers/{session_name}', proxytarget=f"http://{ng_container_name}:8080/")

                    """ Spin until the neuroglancer viewer token from redis becomes available 
                    (may be waiting on the neuroglancer container to finish writing to redis) """
                    while True:
                        session_dict = kv.hgetall(session_name)
                        if 'viewer' in session_dict.keys():
                            break
                        else:
                            logger.debug("Still spinning; waiting for redis entry for neuroglancer viewer")
                            time.sleep(0.25)
                    viewer_json_str = kv.hgetall(session_name)['viewer']
                    viewer_dict = json.loads(viewer_json_str)
                    response=proxy_h.getroutes()
                    
                    neuroglancerurl = f"https://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
                    neuroglancer_url_dict['Raw'][image_resolution] = neuroglancerurl
                    logger.debug("URL IS:")
                    logger.debug(neuroglancerurl)

                """ Stitched data """
                if any(any_stitched_channels):
                    session_name = secrets.token_hex(6)
                    viewer_id = "viewer1" # for storing the viewer info in redis. Only ever one per session
                    # initialize this redis session key
                    kv.hmset(session_name,{"cv_count":0,"cvs_need_atlas":""}) 
                    cv_number = 0 # to keep track of how many cloudvolumes in this viewer/session
                    """ Loop through channels and spawn a cloudvolume 
                    within this session for each light sheet used """
                    for jj in range(len(stitched_channel_forms)):
                        channel_form = stitched_channel_forms[jj]
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
                            cv_container_name = f'{session_name}_stitched_{channel_name}_{lightsheet}_ls_container'
                            cv_name = f"{channel_name}_{lightsheet}_ls_stitched"
                            cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                sample_name,f'imaging_request_{imaging_request_number}','viz',
                                f'processing_request_{processing_request_number}','stitched_raw',
                                f'channel_{channel_name}',f'{lightsheet}_lightsheet',
                                f'channel{channel_name}_stitched_{lightsheet}_lightsheet')      
                            layer_type = 'image'
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
                
                    """ Stitched data neuroglancer container """
                    ng_container_name = f'{session_name}_ng_container'
                    ng_dict = {}
                    ng_dict['hosturl'] = hosturl
                    ng_dict['ng_container_name'] = ng_container_name
                    ng_dict['session_name'] = session_name
                    """ send the data to the viewer-launcher
                    to launch the ng viewer """                       
                    requests.post('http://viewer-launcher:5005/nglauncher',json=ng_dict)                    
                    """ Add the ng container name to redis session key level """
                    kv.hmset(session_name, {"ng_container_name": ng_container_name})
                    """ Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network """
                    proxy_h.addroute(proxypath=f'viewers/{session_name}', proxytarget=f"http://{ng_container_name}:8080/")

                    """ Spin until the neuroglancer viewer token from redis becomes available 
                    (may be waiting on the neuroglancer container to finish writing to redis) """
                    while True:
                        session_dict = kv.hgetall(session_name)
                        if 'viewer' in session_dict.keys():
                            break
                        else:
                            logger.debug("Still spinning; waiting for redis entry for neuroglancer viewer")
                            time.sleep(0.25)
                    viewer_json_str = kv.hgetall(session_name)['viewer']
                    viewer_dict = json.loads(viewer_json_str)
                    response=proxy_h.getroutes()
                    
                    neuroglancerurl = f"https://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
                    neuroglancer_url_dict['Stitched'][image_resolution] = neuroglancerurl
                    logger.debug("URL IS:")
                    logger.debug(neuroglancerurl)

                """ Blended data """
                if any(any_blended_channels):
                    logger.debug("Have blended data!")
                    session_name = secrets.token_hex(6)
                    viewer_id = "viewer1" # for storing the viewer info in redis. Only ever one per session
                    # initialize this redis session key
                    kv.hmset(session_name,{"cv_count":0,"cvs_need_atlas":""}) 
                    cv_number = 0 # to keep track of how many cloudvolumes in this viewer/session
                    """ Loop through channels and spawn a cloudvolume 
                    within this session for each light sheet used """
                    for jj in range(len(blended_channel_forms)):
                        channel_form = blended_channel_forms[jj]
                        channel_name = channel_form.channel_name.data
                        visualize_this_channel = channel_form.viz.data
                        if not visualize_this_channel:
                            continue
                       
                        """ Set up cloudvolume params"""

                        cv_number += 1 
                        cv_container_name = f'{session_name}_blended_{channel_name}_container'
                        cv_name = f"ch{channel_name}_blended" # what shows up as the layer name in neuroglancer
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
                        kv.hincrby(session_name,'cv_count',1)
                        
                        """ register with the confproxy so that the cloudvolume
                        can be seen from outside the docker network """
                        
                        proxy_h = pp.progproxy(target_hname='confproxy')
                        proxypath = os.path.join('cloudvols',session_name,cv_name)
                        proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:1337")

                    """ Blended data neuroglancer container """
                    ng_container_name = f'{session_name}_ng_container'
                    ng_dict = {}
                    ng_dict['hosturl'] = hosturl
                    ng_dict['ng_container_name'] = ng_container_name
                    ng_dict['session_name'] = session_name
                    """ send the data to the viewer-launcher
                    to launch the ng viewer """                       
                    requests.post('http://viewer-launcher:5005/nglauncher',json=ng_dict)                    
                    """ Add the ng container name to redis session key level """
                    kv.hmset(session_name, {"ng_container_name": ng_container_name})
                    """ Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network """
                    proxy_h.addroute(proxypath=f'viewers/{session_name}', proxytarget=f"http://{ng_container_name}:8080/")

                    """ Spin until the neuroglancer viewer token from redis becomes available 
                    (may be waiting on the neuroglancer container to finish writing to redis) """
                    while True:
                        session_dict = kv.hgetall(session_name)
                        if 'viewer' in session_dict.keys():
                            break
                        else:
                            logger.debug("Still spinning; waiting for redis entry for neuroglancer viewer")
                            time.sleep(0.25)
                    viewer_json_str = kv.hgetall(session_name)['viewer']
                    viewer_dict = json.loads(viewer_json_str)
                    response=proxy_h.getroutes()
                    
                    neuroglancerurl = f"https://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
                    neuroglancer_url_dict['Blended'][image_resolution] = neuroglancerurl

                """ Downsized data """
                if any(any_downsized_channels):
                    logger.debug("Have downsized data!")
                    session_name = secrets.token_hex(6)
                    viewer_id = "viewer1" # for storing the viewer info in redis. Only ever one per session
                    # initialize this redis session key
                    kv.hmset(session_name,{"cv_count":0,"cvs_need_atlas":""}) 
                    cv_number = 0 # to keep track of how many cloudvolumes in this viewer/session
                    """ Loop through channels and spawn a cloudvolume 
                    within this session for each light sheet used """
                    for jj in range(len(downsized_channel_forms)):
                        channel_form = downsized_channel_forms[jj]
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

                    """ Downsized data neuroglancer container """
                    ng_container_name = f'{session_name}_ng_container'
                    ng_dict = {}
                    ng_dict['hosturl'] = hosturl
                    ng_dict['ng_container_name'] = ng_container_name
                    ng_dict['session_name'] = session_name
                    """ send the data to the viewer-launcher
                    to launch the ng viewer """                       
                    requests.post('http://viewer-launcher:5005/nglauncher',json=ng_dict)                    
                    """ Add the ng container name to redis session key level """
                    kv.hmset(session_name, {"ng_container_name": ng_container_name})
                    """ Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network """
                    proxy_h.addroute(proxypath=f'viewers/{session_name}', proxytarget=f"http://{ng_container_name}:8080/")

                    """ Spin until the neuroglancer viewer token from redis becomes available 
                    (may be waiting on the neuroglancer container to finish writing to redis) """
                    while True:
                        session_dict = kv.hgetall(session_name)
                        if 'viewer' in session_dict.keys():
                            break
                        else:
                            logger.debug("Still spinning; waiting for redis entry for neuroglancer viewer")
                            time.sleep(0.25)
                    viewer_json_str = kv.hgetall(session_name)['viewer']
                    viewer_dict = json.loads(viewer_json_str)
                    response=proxy_h.getroutes()
                    
                    neuroglancerurl = f"https://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
                    neuroglancer_url_dict['Downsized'][image_resolution] = neuroglancerurl
                    logger.debug("URL IS:")
                    logger.debug(neuroglancerurl)

                """ Registered data """
                if any(any_registered_channels):
                    logger.debug("Have registered data!")
                    this_processing_resolution_request_contents = processing_resolution_request_contents & \
                        f'image_resolution="{image_resolution}"'
                    atlas_name = this_processing_resolution_request_contents.fetch1('atlas_name')
                    session_name = secrets.token_hex(6)
                    viewer_id = "viewer1" # for storing the viewer info in redis. Only ever one per session
                    # initialize this redis session key
                    kv.hmset(session_name,{"cv_count":0,"cvs_need_atlas":""}) 
                    cv_number = 0 # to keep track of how many cloudvolumes in this viewer/session
                    """ Loop through channels and spawn a cloudvolume 
                    within this session for each light sheet used """

                    """ Only want to generate a single cloudvolume container for the 
                    atlas since it is the same atlas for each channel that requests
                    it as an overlay and the fewer total cloudvolumes the better performance
                    we will have. In the loop over channels, set this flag to True
                    if any of the channels request an atlas overlay. """
                    atlas_requested = False
                    for jj in range(len(registered_channel_forms)):
                        channel_form = registered_channel_forms[jj]
                        channel_name = channel_form.channel_name.data
                        visualize_this_channel = channel_form.viz.data
                        channel_restrict_dict = dict(channel_name=channel_name)
                        this_processing_channel_contents = processing_channel_contents & channel_restrict_dict
                        lightsheet_channel_str = this_processing_channel_contents.fetch1('lightsheet_channel_str')
                        
                        """ Set up cloudvolume params"""
                        if not visualize_this_channel:
                            continue
                       
                        """ Set up cloudvolume params"""

                        cv_number += 1 
                        cv_container_name = f'{session_name}_registered_{channel_name}_container'
                        cv_name = f"ch{channel_name}_registered" # what shows up as the layer name in neuroglancer
                        cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                            sample_name,f'imaging_request_{imaging_request_number}','viz',
                            f'processing_request_{processing_request_number}','registered',
                            f'channel_{channel_name}_{lightsheet_channel_str}',      
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

                        """ Check if atlas overlay was requested """
                        overlay_atlas_this_channel = channel_form.viz_atlas.data
                        if overlay_atlas_this_channel:
                            atlas_requested=True
                            cvs_need_atlas = kv.hgetall(session_name)['cvs_need_atlas']
                            cvs_need_atlas+= f'{cv_name},'
                            kv.hmset(session_name,{'cvs_need_atlas':cvs_need_atlas})

                    """ If atlas was requested for any of the channels,
                    then only need to generate it once. Do that here  """
                    if atlas_requested:    
                        """ Set up cloudvolume params for the atlas"""

                        cv_number += 1 
                        cv_container_name = f'{session_name}_atlas'
                        cv_name = atlas_name # what shows up as the layer name in neuroglancer
                        logger.debug("Cloudvolume name is:")
                        logger.debug(cv_name)
                        if 'allen' in atlas_name.lower():
                            cv_path = os.path.join('/jukebox','LightSheetData',
                                'atlas','neuroglancer','atlas','allenatlas_2017')
                        elif 'princeton' in atlas_name.lower():
                            cv_path = os.path.join('/jukebox','LightSheetData',
                                'atlas','neuroglancer','atlas','princetonmouse')
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
                       
                    """ Registered data neuroglancer container """
                    ng_container_name = f'{session_name}_ng_container'
                    ng_dict = {}
                    ng_dict['hosturl'] = hosturl
                    ng_dict['ng_container_name'] = ng_container_name
                    ng_dict['session_name'] = session_name
                    """ send the data to the viewer-launcher
                    to launch the ng viewer """                       
                    requests.post('http://viewer-launcher:5005/ng_reg_launcher',json=ng_dict)                    
                    """ Add the ng container name to redis session key level """
                    kv.hmset(session_name, {"ng_container_name": ng_container_name})
                    """ Add ng viewer url to config proxy so it can be seen from outside of the lightserv docker network """
                    proxy_h.addroute(proxypath=f'viewers/{session_name}', proxytarget=f"http://{ng_container_name}:8080/")

                    """ Spin until the neuroglancer viewer token from redis becomes available 
                    (may be waiting on the neuroglancer container to finish writing to redis) """
                    while True:
                        session_dict = kv.hgetall(session_name)
                        if 'viewer' in session_dict.keys():
                            break
                        else:
                            logger.debug("Still spinning; waiting for redis entry for neuroglancer viewer")
                            time.sleep(0.25)
                    viewer_json_str = kv.hgetall(session_name)['viewer']
                    viewer_dict = json.loads(viewer_json_str)
                    response=proxy_h.getroutes()
                    
                    neuroglancerurl = f"https://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
                    neuroglancer_url_dict['Registered'][image_resolution] = neuroglancerurl
       

            return render_template('neuroglancer/general_viewer_links.html',url_dict=neuroglancer_url_dict)

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
        logger.debug("Image resolution: ")
        logger.debug(image_resolution)

        form.image_resolution_forms.append_entry()
        this_image_resolution_form = form.image_resolution_forms[ii]
        this_image_resolution_form.image_resolution.data = image_resolution
        """ Gather all imaging channels at this image resolution """
        imaging_channel_contents_this_resolution = (imaging_channel_contents & \
            f'image_resolution="{image_resolution}"')
        # logger.debug(imaging_channel_contents_this_resolution)
        processing_channel_contents_this_resolution = (processing_channel_contents & \
            f'image_resolution="{image_resolution}"')
        imaging_channels_this_resolution = processing_channel_contents_this_resolution.fetch('channel_name')
        """ Loop through all channels at this resolution and render 
        a sub-sub-form for each """
        channel_contents_lists.append([])
        for jj in range(len(imaging_channels_this_resolution)):
            channel_name = imaging_channels_this_resolution[jj]
            logger.debug(f"channel: {channel_name}")
            """ Figure out if data was stitched or not """
            this_imaging_channel_content_dict = (imaging_channel_contents_this_resolution & \
                f'channel_name="{channel_name}"').fetch1()
            tiling_scheme = this_imaging_channel_content_dict['tiling_scheme']
            if tiling_scheme == "1x1":
                # there is raw data and it is not stitched            
                this_image_resolution_form.raw_channel_forms.append_entry()
                this_raw_channel_form = this_image_resolution_form.raw_channel_forms[jj]
                this_raw_channel_form.channel_name.data = channel_name
            else:
                this_image_resolution_form.stitched_channel_forms.append_entry()
                this_stitched_channel_form = this_image_resolution_form.stitched_channel_forms[jj]
                this_stitched_channel_form.channel_name.data = channel_name           
           
            """ Figure out if we have blended data """
            
            this_processing_channel_content_dict = (processing_channel_contents_this_resolution & \
                f'channel_name="{channel_name}"').fetch1()
            blended_precomputed_spock_job_progress = this_processing_channel_content_dict['blended_precomputed_spock_job_progress']
            if blended_precomputed_spock_job_progress == 'COMPLETED':
                this_image_resolution_form.blended_channel_forms.append_entry()
                this_blended_channel_form = this_image_resolution_form.blended_channel_forms[jj]
                this_blended_channel_form.channel_name.data = channel_name
            channel_contents_lists[ii].append(this_imaging_channel_content_dict)
            
            """ Figure out if we have downsized data """
            
            downsized_precomputed_spock_job_progress = this_processing_channel_content_dict['downsized_precomputed_spock_job_progress']
            if downsized_precomputed_spock_job_progress == 'COMPLETED':
                this_image_resolution_form.downsized_channel_forms.append_entry()
                this_downsized_channel_form = this_image_resolution_form.downsized_channel_forms[jj]
                this_downsized_channel_form.channel_name.data = channel_name

            """ Figure out if we have registered data """
            
            registered_precomputed_spock_job_progress = this_processing_channel_content_dict['registered_precomputed_spock_job_progress']
            if registered_precomputed_spock_job_progress == 'COMPLETED':
                this_image_resolution_form.registered_channel_forms.append_entry()
                this_registered_channel_form = this_image_resolution_form.registered_channel_forms[jj]
                this_registered_channel_form.channel_name.data = channel_name

            channel_contents_lists[ii].append(this_imaging_channel_content_dict)
            # logger.debug(this_channel_content) 
        # logger.debug(imaging_channel_dict)

    return render_template('neuroglancer/general_data_setup.html',form=form,
        channel_contents_lists=channel_contents_lists,processing_request_table=processing_request_table)

@neuroglancer.route("/nglancer_viewer")
def blank_viewer():
    """ A route for a routing someone to a blank viewer
    in the BRAIN CoGS neuroglancer client.
    This is a temporary fix while we work on getting 
    a static version of the neuroglancer client running on braincogs00
    """
    hosturl = os.environ['HOSTURL'] # via dockerenv

    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)

    session_name = secrets.token_hex(6)
    
    proxy_h = pp.progproxy(target_hname='confproxy')

    # Run the ng container which adds the viewer info to redis

    ng_container_name = '{}_ng_container'.format(session_name)

    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    requests.post('http://viewer-launcher:5005/nglauncher',json=ng_dict)

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
    return redirect(neuroglancerurl)