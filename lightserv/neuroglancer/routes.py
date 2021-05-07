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
    DownsizedDataSetupForm,GeneralDataSetupForm,
    CfosSetupForm,LightservCfosSetupForm)
from .tables import (ImagingRequestTable, ProcessingRequestTable,
    CloudVolumeLayerTable,MultiLightSheetCloudVolumeLayerTable,
    ConfproxyAdminTable)
from lightserv import cel, db_lightsheet
from lightserv.main.utils import (check_imaging_completed,
    check_imaging_request_precomputed,log_http_requests,
    check_some_precomputed_pipelines_completed,logged_in,
    table_sorter,logged_in_as_admin)
from .tasks import ng_viewer_checker
import progproxy as pp

from functools import partial
import humanize

datetimeformat='%Y-%m-%dT%H:%M:%S.%fZ'

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
        if os.environ['FLASK_MODE'] == 'TEST':
            logger.debug("Trying to connect to test redis container")
            kv = redis.Redis(host="testredis", decode_responses=True)
        else:
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
                    
                    channel_form = image_resolution_form.channel_forms[jj]
                    channel_name = channel_form.channel_name.data
                    viz_left_lightsheet = channel_form.viz_left_lightsheet.data
                    viz_right_lightsheet = channel_form.viz_right_lightsheet.data
                    ventral_up = int(channel_form.ventral_up.data)
                    this_restrict_dict = {
                            'channel_name':channel_name,
                            'ventral_up':ventral_up}
                    this_imaging_channel_contents =  imaging_channel_contents & \
                            this_restrict_dict

                    rawdata_subfolder = this_imaging_channel_contents.fetch1('rawdata_subfolder') 
                    logger.debug("Have channel:")
                    logger.debug(channel_name)
                    logger.debug("Ventral up?")
                    logger.debug(ventral_up)
                    for lightsheet in ['left','right']:
                        cv_contents_dict_this_lightsheet = {}
                        if lightsheet == 'left':
                            if not viz_left_lightsheet:
                                continue
                        elif lightsheet == 'right':
                            if not viz_right_lightsheet:
                                continue
                        
                        if ventral_up:
                            logger.debug("Using ventral up cloudvolume")
                            cv_container_name = f'{session_name}_raw_{channel_name}_{lightsheet}_ls_ventral_up_container'
                            cv_name = f"{channel_name}_{lightsheet}_ls_ventral_up_raw"
                            cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                sample_name,f'imaging_request_{imaging_request_number}','viz',
                                'raw',f'channel_{channel_name}_ventral_up',f'{lightsheet}_lightsheet',
                                f'channel{channel_name}_raw_{lightsheet}_lightsheet')
                            raw_data_path = os.path.join(data_bucket_rootpath,username,
                                request_name,sample_name,
                                f"imaging_request_{imaging_request_number}",
                                "rawdata",f"resolution_{image_resolution}_ventral_up",rawdata_subfolder)
                        else:
                            logger.debug("Using dorsal up cloudvolume")
                            cv_container_name = f'{session_name}_raw_{channel_name}_{lightsheet}_ls_container'
                            cv_name = f"{channel_name}_{lightsheet}_ls_raw"
                            cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                sample_name,f'imaging_request_{imaging_request_number}','viz',
                                'raw',f'channel_{channel_name}',f'{lightsheet}_lightsheet',
                                f'channel{channel_name}_raw_{lightsheet}_lightsheet')      
                            raw_data_path = os.path.join(data_bucket_rootpath,username,
                                request_name,sample_name,
                                f"imaging_request_{imaging_request_number}",
                                "rawdata",f"resolution_{image_resolution}",rawdata_subfolder)
                        cv_number += 1              
                        
                        cv_contents_dict_this_lightsheet['image_resolution'] = image_resolution
                        cv_contents_dict_this_lightsheet['lightsheet'] = lightsheet
                        cv_contents_dict_this_lightsheet['cv_name'] = cv_name
                        cv_contents_dict_this_lightsheet['cv_path'] = cv_path
                        cv_contents_dict_this_lightsheet['data_path'] = raw_data_path
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
                        cv_contents_dict_list_this_resolution.append(cv_contents_dict_this_lightsheet)
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
                
                requests.post('http://viewer-launcher:5005/ng_raw_launcher',json=ng_dict)
                logger.debug("Made post request to viewer-launcher to launch ng raw viewer")
                
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
                        logger.debug("Still spinning; waiting for redis entry for neuroglancer viewer")
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
            flash("There were errors below. Correct them in order to proceed.",'danger')
            for key in form.errors:
                for error in form.errors[key]:
                    flash(error,'danger')
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
        
        """ Gather all imaging channel at this image resolution """
        imaging_channel_contents_this_resolution = (imaging_channel_contents & \
            f'image_resolution="{image_resolution}"')
        imaging_channels_this_resolution,ventral_up_vals_this_resolution = imaging_channel_contents_this_resolution.fetch(
            'channel_name',
            'ventral_up')
        """ Loop through all channels at this resolution and render 
        a sub-sub-form for each """
        channel_contents_lists.append([])
        for jj in range(len(imaging_channels_this_resolution)):
            channel_name = imaging_channels_this_resolution[jj]
            ventral_up = ventral_up_vals_this_resolution[jj]
            # logger.debug(f"channel: {channel_name}")
            this_image_resolution_form.channel_forms.append_entry()
            this_channel_form = this_image_resolution_form.channel_forms[jj]
            this_channel_form.channel_name.data = channel_name
            this_channel_form.ventral_up.data = ventral_up
            """ Figure out which light sheets were imaged """
            restrict_dict = {'channel_name':channel_name,'ventral_up':ventral_up}
            this_channel_content_dict = (imaging_channel_contents_this_resolution & restrict_dict).fetch1()
            # logger.debug(channel_name)           # logger.debug(this_channel_content_dict)
           
            channel_contents_lists[ii].append(this_channel_content_dict)
            # logger.debug(this_channel_content) 
        # logger.debug(imaging_channel_dict)

    return render_template('neuroglancer/raw_data_setup.html',form=form,
        channel_contents_lists=channel_contents_lists,imaging_request_table=imaging_request_table)

@neuroglancer.route("/neuroglancer/blended_data_setup/"
                    "<username>/<request_name>/<sample_name>/"
                    "<imaging_request_number>/<processing_request_number>",
    methods=['GET','POST'])
def blended_data_setup(username,request_name,sample_name,
    imaging_request_number,processing_request_number): # don't change the url 
    """ An old deprecated route that I now just redirect to general_data_setup()
    route """
    return redirect(url_for('neuroglancer.general_data_setup',
        username=username,request_name=request_name,
        sample_name=sample_name,imaging_request_number=imaging_request_number,
        processing_request_number=processing_request_number))
    
@neuroglancer.route("/neuroglancer/stitched_data_setup/"
                    "<username>/<request_name>/<sample_name>/"
                    "<imaging_request_number>/<processing_request_number>",
    methods=['GET','POST'])
def stitched_data_setup(username,request_name,sample_name,
    imaging_request_number,processing_request_number): # don't change the url 
    """ An old deprecated route that I now just redirect to general_data_setup()
    route """
    return redirect(url_for('neuroglancer.general_data_setup',
        username=username,request_name=request_name,
        sample_name=sample_name,imaging_request_number=imaging_request_number,
        processing_request_number=processing_request_number))
    
@neuroglancer.route("/neuroglancer/downsized_data_setup/"
                    "<username>/<request_name>/<sample_name>/"
                    "<imaging_request_number>/<processing_request_number>",
    methods=['GET','POST'])
def downsized_data_setup(username,request_name,sample_name,
    imaging_request_number,processing_request_number): # don't change the url 
    """ An old deprecated route that I now just redirect to general_data_setup()
    route """
    return redirect(url_for('neuroglancer.general_data_setup',
        username=username,request_name=request_name,
        sample_name=sample_name,imaging_request_number=imaging_request_number,
        processing_request_number=processing_request_number))
    
@neuroglancer.route("/neuroglancer/registered_data_setup/"
                    "<username>/<request_name>/<sample_name>/"
                    "<imaging_request_number>/<processing_request_number>",
    methods=['GET','POST'])
def registered_data_setup(username,request_name,sample_name,
    imaging_request_number,processing_request_number): # don't change the url 
    """ An old deprecated route that I now just redirect to general_data_setup()
    route """
    return redirect(url_for('neuroglancer.general_data_setup',
        username=username,request_name=request_name,
        sample_name=sample_name,imaging_request_number=imaging_request_number,
        processing_request_number=processing_request_number))
    
@neuroglancer.route("/neuroglancer/general_data_setup/"
                    "<username>/<request_name>/<sample_name>/"
                    "<imaging_request_number>/<processing_request_number>",
    methods=['GET','POST'])
# @check_imaging_completed
@check_some_precomputed_pipelines_completed
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
    joined_processing_channel_contents = imaging_channel_contents * processing_channel_contents

    if request.method == 'POST':
        logger.debug('POST request')
        # Redis setup for this session
        
        hosturl = os.environ['HOSTURL'] # via .dockerenv
        data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']

        if form.validate_on_submit():
            logger.debug("Form validated")
            
            """ loop through each image resolution sub-form 
            and make a neuroglancer viewer link for each data type,
            spawning cloudvolumes where necessary"""
            
            kv = redis.Redis(host="redis", decode_responses=True)
            neuroglancer_url_dict = OrderedDict({
                'Raw':{},
                'Stitched':{},
                'Blended':{},
                'Downsized':{},
                'Registered':{}
                })
            cv_table_dict = {
                'Raw':{},
                'Stitched':{},
                'Blended':{},
                'Downsized':{},
                'Registered':{}
                } # will hold the flask tables for all datatypes and image resolutions
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
                    cv_table_dict['Raw'][image_resolution] = {}
                    cv_contents_dict_list_this_resolution = []
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
                        ventral_up = int(channel_form.ventral_up.data)
                        this_restrict_dict = {
                            'channel_name':channel_name,
                            'ventral_up':ventral_up}
                        this_imaging_channel_contents =  imaging_channel_contents & \
                                this_restrict_dict

                        rawdata_subfolder = this_imaging_channel_contents.fetch1('rawdata_subfolder') 
                        
                        for lightsheet in ['left','right']:
                            cv_contents_dict_this_lightsheet = {}
                            if lightsheet == 'left':
                                if not viz_left_lightsheet:
                                    continue
                            elif lightsheet == 'right':
                                if not viz_right_lightsheet:
                                    continue

                            if ventral_up:
                                logger.debug("Using ventral up cloudvolume")
                                cv_container_name = f'{session_name}_raw_{channel_name}_{lightsheet}_ls_ventral_up_container'
                                cv_name = f"{channel_name}_{lightsheet}_ls_ventral_up_raw"
                                cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                    sample_name,f'imaging_request_{imaging_request_number}','viz',
                                    'raw',f'channel_{channel_name}_ventral_up',f'{lightsheet}_lightsheet',
                                    f'channel{channel_name}_raw_{lightsheet}_lightsheet')
                                raw_data_path = os.path.join(data_bucket_rootpath,username,
                                    request_name,sample_name,
                                    f"imaging_request_{imaging_request_number}",
                                    "rawdata",f"resolution_{image_resolution}_ventral_up",rawdata_subfolder)
                            else:
                                logger.debug("Using dorsal up cloudvolume")
                                cv_container_name = f'{session_name}_raw_{channel_name}_{lightsheet}_ls_container'
                                cv_name = f"{channel_name}_{lightsheet}_ls_raw"
                                cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                    sample_name,f'imaging_request_{imaging_request_number}','viz',
                                    'raw',f'channel_{channel_name}',f'{lightsheet}_lightsheet',
                                    f'channel{channel_name}_raw_{lightsheet}_lightsheet')      
                                raw_data_path = os.path.join(data_bucket_rootpath,username,
                                    request_name,sample_name,
                                    f"imaging_request_{imaging_request_number}",
                                    "rawdata",f"resolution_{image_resolution}",rawdata_subfolder)

                            layer_type = 'image'
                            cv_number += 1            

                            cv_contents_dict_this_lightsheet['image_resolution'] = image_resolution
                            cv_contents_dict_this_lightsheet['lightsheet'] = lightsheet
                            cv_contents_dict_this_lightsheet['cv_name'] = cv_name
                            cv_contents_dict_this_lightsheet['cv_path'] = cv_path
                            cv_contents_dict_this_lightsheet['data_path'] = raw_data_path            
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
                            cv_contents_dict_list_this_resolution.append(cv_contents_dict_this_lightsheet)
                    cv_table = MultiLightSheetCloudVolumeLayerTable(cv_contents_dict_list_this_resolution)
                    cv_table_dict['Raw'][image_resolution] = cv_table
                    """ Raw data neuroglancer container """
                    ng_container_name = f'{session_name}_ng_container'
                    ng_dict = {}
                    ng_dict['hosturl'] = hosturl
                    ng_dict['ng_container_name'] = ng_container_name
                    ng_dict['session_name'] = session_name
                    """ send the data to the viewer-launcher
                    to launch the ng viewer """                       
                    requests.post('http://viewer-launcher:5005/ng_raw_launcher',json=ng_dict)                    
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
                        ventral_up = int(channel_form.ventral_up.data)
                        
                        for lightsheet in ['left','right']:
                            if lightsheet == 'left':
                                if not viz_left_lightsheet:
                                    continue
                            elif lightsheet == 'right':
                                if not viz_right_lightsheet:
                                    continue

                            if ventral_up:
                                logger.debug("Using ventral up cloudvolume")
                                cv_container_name = f'{session_name}_stitched_{channel_name}_{lightsheet}_ls_ventral_up_container'
                                cv_name = f"{channel_name}_{lightsheet}_ls_ventral_up_stitched"
                                cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                    sample_name,f'imaging_request_{imaging_request_number}','viz',
                                    f'processing_request_{processing_request_number}','stitched_raw',
                                    f'channel_{channel_name}_ventral_up',f'{lightsheet}_lightsheet',
                                    f'channel{channel_name}_stitched_{lightsheet}_lightsheet')      
                            else:
                                logger.debug("Using dorsal up cloudvolume")
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
                    requests.post('http://viewer-launcher:5005/ng_raw_launcher',json=ng_dict)                    
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
                    cv_table_dict['Blended'][image_resolution] = {}
                    cv_contents_dict_list_this_resolution = []
                    logger.debug("Have blended data!")
                    session_name = secrets.token_hex(6)
                    viewer_id = "viewer1" # for storing the viewer info in redis. Only ever one per session
                    # initialize this redis session key
                    kv.hmset(session_name,{"cv_count":0,"cvs_need_atlas":""}) 
                    cv_number = 0 # to keep track of how many cloudvolumes in this viewer/session
                    """ Loop through channels and spawn a cloudvolume 
                    within this session for each light sheet used """
                    for jj in range(len(blended_channel_forms)):
                        cv_contents_dict_this_channel = {}
                        channel_form = blended_channel_forms[jj]
                        channel_name = channel_form.channel_name.data
                        visualize_this_channel = channel_form.viz.data
                        ventral_up = int(channel_form.ventral_up.data)

                        if not visualize_this_channel:
                            continue
                       
                        """ Set up cloudvolume params"""

                        cv_number += 1 

                        if ventral_up:
                            cv_container_name = f'{session_name}_blended_{channel_name}_ventral_up_container'
                            cv_name = f"ch{channel_name}_ventral_up_blended" # what shows up as the layer name in neuroglancer
                            cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                sample_name,f'imaging_request_{imaging_request_number}','viz',
                                f'processing_request_{processing_request_number}','blended',
                                f'channel_{channel_name}_ventral_up',      
                                f'channel{channel_name}_blended')   
                        else:
                            cv_container_name = f'{session_name}_blended_{channel_name}_container'
                            cv_name = f"ch{channel_name}_blended" # what shows up as the layer name in neuroglancer
                            cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                sample_name,f'imaging_request_{imaging_request_number}','viz',
                                f'processing_request_{processing_request_number}','blended',
                                f'channel_{channel_name}',      
                                f'channel{channel_name}_blended')    
                        layer_type = "image"
                        this_restrict_dict = {
                            'channel_name':channel_name,
                            'ventral_up':ventral_up
                            }
                        this_processing_channel_contents =  joined_processing_channel_contents & \
                            this_restrict_dict

                        rawdata_subfolder = this_processing_channel_contents.fetch1('rawdata_subfolder')
                        channel_index = this_processing_channel_contents.fetch1('imspector_channel_index')
                        channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
                        if ventral_up:
                            blended_data_path = os.path.join(data_bucket_rootpath,username,
                                 request_name,sample_name,
                                 f"imaging_request_{imaging_request_number}",
                                 "output",
                                 f"processing_request_{processing_request_number}",
                                 f"resolution_{image_resolution}_ventral_up",
                                 "full_sizedatafld",
                                 f"{rawdata_subfolder}_ch{channel_index_padded}")
                        else: 
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
                    cv_table_dict['Blended'][image_resolution] = cv_table
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
                    cv_table_dict['Downsized'][image_resolution] = {}
                    cv_contents_dict_list_this_resolution = []
                    logger.debug("Have downsized data!")
                    session_name = secrets.token_hex(6)
                    viewer_id = "viewer1" # for storing the viewer info in redis. Only ever one per session
                    # initialize this redis session key
                    kv.hmset(session_name,{"cv_count":0,"cvs_need_atlas":""}) 
                    cv_number = 0 # to keep track of how many cloudvolumes in this viewer/session
                    """ Loop through channels and spawn a cloudvolume 
                    within this session for each light sheet used """
                    for jj in range(len(downsized_channel_forms)):
                        cv_contents_dict_this_channel = {}
                        channel_form = downsized_channel_forms[jj]
                        channel_name = channel_form.channel_name.data
                        visualize_this_channel = channel_form.viz.data
                        ventral_up = int(channel_form.ventral_up.data)
                        if not visualize_this_channel:
                            continue
                       
                        """ Set up cloudvolume params"""

                        cv_number += 1 
                        if ventral_up:
                            cv_container_name = f'{session_name}_downsized_{channel_name}_ventral_up_container'
                            cv_name = f"ch{channel_name}_ventral_up_downsized" # what shows up as the layer name in neuroglancer
                            cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                sample_name,f'imaging_request_{imaging_request_number}','viz',
                                f'processing_request_{processing_request_number}','downsized',
                                f'channel_{channel_name}_ventral_up',      
                                f'channel{channel_name}_downsized') 
                        else:
                            cv_container_name = f'{session_name}_downsized_{channel_name}_container'
                            cv_name = f"ch{channel_name}_downsized" # what shows up as the layer name in neuroglancer
                            cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                sample_name,f'imaging_request_{imaging_request_number}','viz',
                                f'processing_request_{processing_request_number}','downsized',
                                f'channel_{channel_name}',      
                                f'channel{channel_name}_downsized')      
                        layer_type = "image"
                        this_restrict_dict = {
                            'channel_name':channel_name,
                            'ventral_up':ventral_up}
                        this_processing_channel_contents =  joined_processing_channel_contents & \
                            this_restrict_dict

                        rawdata_subfolder = this_processing_channel_contents.fetch1('rawdata_subfolder')
                        channel_index = this_processing_channel_contents.fetch1('imspector_channel_index')
                        channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
                        if ventral_up:
                            downsized_data_path = os.path.join(data_bucket_rootpath,username,
                                 request_name,sample_name,
                                 f"imaging_request_{imaging_request_number}",
                                 "output",
                                 f"processing_request_{processing_request_number}",
                                 f"resolution_{image_resolution}_ventral_up",
                                 f'{rawdata_subfolder}_resized_ch{channel_index_padded}_resampledforelastix.tif')
                        else:
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
                    cv_table_dict['Downsized'][image_resolution] = cv_table
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
                    cv_table_dict['Registered'][image_resolution] = {}
                    cv_contents_dict_list_this_resolution = []
                    logger.debug("Have registered data!")
                    restrict_dict = {'image_resolution':image_resolution}
                    this_processing_resolution_request_contents = processing_resolution_request_contents & \
                        restrict_dict
                    atlas_name = this_processing_resolution_request_contents.fetch('atlas_name',limit=1)[0]
                    session_name = secrets.token_hex(6)
                    viewer_id = "viewer1" # for storing the viewer info in redis. Only ever one per session
                    # initialize this redis session key
                    kv.hmset(session_name,{"cv_count":0,"cvs_need_atlas":""}) 
                    cv_number = 0 # to keep track of how many cloudvolumes in this viewer/session
                    """ Loop through channels and spawn a cloudvolume 
                    within this session for each light sheet used """

                    """ Just generate 1 atlas cloudvolume
                    since it is the same atlas for each channel that requests
                    it as an overlay and the fewer total cloudvolumes the better performance
                    we will have. In the loop over channels, set this flag to True
                    if any of the channels request an atlas overlay. """
                    atlas_requested = False
                    for jj in range(len(registered_channel_forms)):
                        cv_contents_dict_this_channel = {}
                        channel_form = registered_channel_forms[jj]
                        channel_name = channel_form.channel_name.data
                        ventral_up = int(channel_form.ventral_up.data)
                        visualize_this_channel = channel_form.viz.data
                        channel_restrict_dict = dict(channel_name=channel_name,
                            ventral_up=ventral_up)
                        this_processing_channel_contents = processing_channel_contents & channel_restrict_dict
                        lightsheet_channel_str = this_processing_channel_contents.fetch1('lightsheet_channel_str')
                        
                        """ Set up cloudvolume params"""
                        if not visualize_this_channel:
                            continue
                       
                        """ Set up cloudvolume params"""

                        cv_number += 1 
                        if ventral_up:
                            cv_container_name = f'{session_name}_registered_{channel_name}_ventral_up_container'
                            cv_name = f"ch{channel_name}_ventral_up_registered" # what shows up as the layer name in neuroglancer
                            cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                sample_name,f'imaging_request_{imaging_request_number}','viz',
                                f'processing_request_{processing_request_number}','registered',
                                f'channel_{channel_name}_{lightsheet_channel_str}_ventral_up',      
                                f'channel{channel_name}_registered_ventral_up')        
                        else:
                            cv_container_name = f'{session_name}_registered_{channel_name}_container'
                            cv_name = f"ch{channel_name}_registered" # what shows up as the layer name in neuroglancer
                            cv_path = os.path.join(data_bucket_rootpath,username,request_name,
                                sample_name,f'imaging_request_{imaging_request_number}','viz',
                                f'processing_request_{processing_request_number}','registered',
                                f'channel_{channel_name}_{lightsheet_channel_str}',      
                                f'channel{channel_name}_registered')
                        layer_type = "image"
                        this_restrict_dict = {
                            'channel_name':channel_name,
                            'ventral_up':ventral_up}
                        this_processing_channel_contents =  joined_processing_channel_contents & \
                            this_restrict_dict

                        (rawdata_subfolder,channel_index,
                            lightsheet_channel_str) = this_processing_channel_contents.fetch1(
                            'rawdata_subfolder','imspector_channel_index','lightsheet_channel_str')
                        channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
                        if ventral_up:
                            registered_data_base_path = os.path.join(data_bucket_rootpath,username,
                                 request_name,sample_name,
                                 f"imaging_request_{imaging_request_number}",
                                 "output",
                                 f"processing_request_{processing_request_number}",
                                 f"resolution_{image_resolution}_ventral_up",
                                 "elastix")      
                        else:
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
                        cv_contents_dict_list_this_resolution.append(cv_contents_dict_this_channel)
                    
                    """ If atlas was requested for any of the channels,
                    then only need to generate it once. Do that here  """
                    if atlas_requested:    
                        cv_contents_dict_this_channel = {}
                        """ Set up cloudvolume params for the atlas"""

                        cv_number += 1 
                        cv_container_name = f'{session_name}_atlas'
                        cv_name = atlas_name # what shows up as the layer name in neuroglancer
                        logger.debug("Cloudvolume name is:")
                        logger.debug(cv_name)
                        if 'allen' in atlas_name.lower():
                            cv_path = os.path.join('/jukebox','LightSheetData',
                                'atlas','neuroglancer','atlas','allenatlas_2017')
                            data_path = os.path.join('/jukebox','LightSheetData',
                                'atlas','allen_atlas','average_template_25_sagittal.tif')
                        elif 'princeton' in atlas_name.lower():
                            cv_path = os.path.join('/jukebox','LightSheetData',
                                'atlas','neuroglancer','atlas','princetonmouse')
                            data_path = os.path.join('/jukebox','LightSheetData',
                                'atlas','sagittal_atlas_20um_iso.tif')
                        elif atlas_name == 'paxinos':
                            cv_path = os.path.join('/jukebox','LightSheetData',
                                'atlas','neuroglancer','atlas','kimatlas')
                            data_path = os.path.join('/jukebox','LightSheetData',
                                'atlas','sagittal_atlas_20um_iso.tif')
                        layer_type = "segmentation"
                        cv_contents_dict_this_channel['image_resolution'] = image_resolution
                        cv_contents_dict_this_channel['cv_name'] = cv_name
                        cv_contents_dict_this_channel['cv_path'] = cv_path
                        cv_contents_dict_this_channel['data_path'] = data_path
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
                        cv_contents_dict_list_this_resolution.append(cv_contents_dict_this_channel)
                    cv_table = CloudVolumeLayerTable(cv_contents_dict_list_this_resolution)
                    cv_table_dict['Registered'][image_resolution] = cv_table  
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
       
            logger.debug(cv_table_dict)
            return render_template('neuroglancer/general_viewer_links.html',
                url_dict=neuroglancer_url_dict,cv_table_dict=cv_table_dict)

        else: # form not validated
            flash("There were errors below. Correct them in order to proceed.","danger")
            for key in form.errors:
                for error in form.errors[key]:
                    flash(error,'danger')
            logger.debug(form.errors)

    """Loop through all imaging resolutions and render a 
    a sub-form for each, where appropriate"""
    unique_image_resolutions = sorted(set(imaging_channel_contents.fetch('image_resolution')))

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
        imaging_channels_this_resolution,ventral_up_vals_this_resolution = imaging_channel_contents_this_resolution.fetch(
            'channel_name',
            'ventral_up')
        processing_channel_contents_this_resolution = (processing_channel_contents & \
            f'image_resolution="{image_resolution}"')
        imaging_channels_this_resolution = imaging_channel_contents_this_resolution.fetch('channel_name')
        """ Loop through all channels at this resolution and render 
        a sub-sub-form for each """
        channel_contents_lists.append([])
        for jj in range(len(imaging_channels_this_resolution)):
            channel_name = imaging_channels_this_resolution[jj]
            ventral_up = ventral_up_vals_this_resolution[jj]
            logger.debug(f"channel: {channel_name}")
            logger.debug(f"ventral up?: {ventral_up}")
            logger.debug(f"jj index = {jj}")
            """ Figure out if data was stitched or not """
            restrict_dict = {'channel_name':channel_name,'ventral_up':ventral_up}
            this_imaging_channel_content_dict = (imaging_channel_contents_this_resolution & \
                restrict_dict).fetch1()
            this_processing_channel_content = (processing_channel_contents_this_resolution & \
                    restrict_dict)
            if len(this_processing_channel_content) > 0:
                this_processing_channel_content_dict = this_processing_channel_content.fetch1()
            else:
                this_processing_channel_content_dict = {}
            tiling_scheme = this_imaging_channel_content_dict['tiling_scheme']

            if tiling_scheme == "1x1":
                # there is raw data and it is not stitched 
                """ Check to see if either light sheet has precomputed data yet """
                left_lightsheet_precomputed_spock_job_progress = this_imaging_channel_content_dict[
                    'left_lightsheet_precomputed_spock_job_progress']
                right_lightsheet_precomputed_spock_job_progress = this_imaging_channel_content_dict[
                    'right_lightsheet_precomputed_spock_job_progress']
                logger.debug(left_lightsheet_precomputed_spock_job_progress)
                logger.debug(right_lightsheet_precomputed_spock_job_progress)
                if (left_lightsheet_precomputed_spock_job_progress == 'COMPLETED' 
                    or right_lightsheet_precomputed_spock_job_progress == 'COMPLETED'):
                    this_image_resolution_form.raw_channel_forms.append_entry()
                    this_raw_channel_form = this_image_resolution_form.raw_channel_forms[-1]
                    this_raw_channel_form.channel_name.data = channel_name
                    this_raw_channel_form.ventral_up.data = ventral_up
            else:
                # stitched raw data
                
                left_lightsheet_stitched_precomputed_spock_job_progress = \
                    this_processing_channel_content_dict.get(
                        'left_lightsheet_stitched_precomputed_spock_job_progress')
                right_lightsheet_stitched_precomputed_spock_job_progress = \
                    this_processing_channel_content_dict.get(
                        'right_lightsheet_stitched_precomputed_spock_job_progress')
                if (left_lightsheet_stitched_precomputed_spock_job_progress == 'COMPLETED' 
                    or right_lightsheet_stitched_precomputed_spock_job_progress == 'COMPLETED'):
                    this_image_resolution_form.stitched_channel_forms.append_entry()
                    this_stitched_channel_form = this_image_resolution_form.stitched_channel_forms[jj]
                    this_stitched_channel_form.channel_name.data = channel_name           
                    this_stitched_channel_form.ventral_up.data = ventral_up           

            """ Figure out if we have blended data """
            
            blended_precomputed_spock_job_progress = this_processing_channel_content_dict.get(
                'blended_precomputed_spock_job_progress')
            if blended_precomputed_spock_job_progress == 'COMPLETED':
                this_image_resolution_form.blended_channel_forms.append_entry()
                this_blended_channel_form = this_image_resolution_form.blended_channel_forms[-1]
                this_blended_channel_form.channel_name.data = channel_name
                this_blended_channel_form.ventral_up.data = ventral_up
            channel_contents_lists[ii].append(this_imaging_channel_content_dict)
            
            """ Figure out if we have downsized data """
            
            downsized_precomputed_spock_job_progress = this_processing_channel_content_dict.get(
                'downsized_precomputed_spock_job_progress')
            if downsized_precomputed_spock_job_progress == 'COMPLETED':
                this_image_resolution_form.downsized_channel_forms.append_entry()
                this_downsized_channel_form = this_image_resolution_form.downsized_channel_forms[-1]
                this_downsized_channel_form.channel_name.data = channel_name
                this_downsized_channel_form.ventral_up.data = ventral_up

            """ Figure out if we have registered data """
            
            registered_precomputed_spock_job_progress = this_processing_channel_content_dict.get(
                'registered_precomputed_spock_job_progress')
            if registered_precomputed_spock_job_progress == 'COMPLETED':
                this_image_resolution_form.registered_channel_forms.append_entry()
                n_registered_channel_forms = len(this_image_resolution_form.registered_channel_forms)
                logger.debug(f"Have {n_registered_channel_forms} registered channel forms for this resolution")
                this_registered_channel_form = this_image_resolution_form.registered_channel_forms[-1]
                this_registered_channel_form.channel_name.data = channel_name
                this_registered_channel_form.ventral_up.data = ventral_up

            channel_contents_lists[ii].append(this_imaging_channel_content_dict)

    return render_template('neuroglancer/general_data_setup.html',form=form,
        channel_contents_lists=channel_contents_lists,processing_request_table=processing_request_table)

@neuroglancer.route("/neuroglancer/allen_atlas",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def allen_atlas():
    """ A route for generating a link to Neuroglancer
    showing the Allen Brain Atlas with 3D mesh and segment properties
    """
    from .utils import generate_neuroglancer_url
    session_name = secrets.token_hex(6)

    """ CV 1: Allen Mouse Brain Atlas """
    layer_type = "segmentation"
               
    cv_number = 1 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_allenatlas_2017'
    cv_name = f"allen_mouse_brain_atlas_2017"
    cv_path = '/jukebox/LightSheetData/atlas/neuroglancer/atlas/allenatlas_2017'  
    cv_dict = dict(cv_number=cv_number,cv_path=cv_path,cv_name=cv_name,
        cv_container_name=cv_container_name,
        layer_type=layer_type,session_name=session_name)
    cv_dict_list = [cv_dict]
    payload = {'session_name':session_name,'cv_dict_list':cv_dict_list}
    neuroglancerurl = generate_neuroglancer_url(payload)
    
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/princeton_mouse_atlas",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def princeton_mouse_atlas():
    """ A route for generating a link to Neuroglancer
    showing the Allen Brain Atlas with 3D mesh and segment properties
    """
    from .utils import generate_neuroglancer_url
    session_name = secrets.token_hex(6)

    """ CV 1: Princeton Mouse Brain Atlas """
    layer_type = "segmentation"
               
    cv_number = 1 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_princeton_mouse_atlas'
    cv_name = f"princeton_mouse_brain_atlas_v1.0"
    cv_path = '/jukebox/LightSheetData/atlas/neuroglancer/atlas/princetonmouse'  
    cv_dict = dict(cv_number=cv_number,cv_path=cv_path,cv_name=cv_name,
        cv_container_name=cv_container_name,
        layer_type=layer_type,session_name=session_name)
    cv_dict_list = [cv_dict]
    payload = {'session_name':session_name,'cv_dict_list':cv_dict_list}
    neuroglancerurl = generate_neuroglancer_url(payload)
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/merge_ontology_demo",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def merge_ontology_demo():
    """ A route for generating a link to Neuroglancer
    showing the Allen Brain Atlas merge-ontology demo
    """
    from .utils import generate_neuroglancer_url
    session_name = secrets.token_hex(6)

    """ CV 1: Allen Mouse Brain Atlas """
    layer_type = "segmentation"
               
    cv_dict_list = []
    payload = {'session_name':session_name,'cv_dict_list':cv_dict_list}
    neuroglancerurl = generate_neuroglancer_url(payload,ng_image='ontology')
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/jess_cfos_example",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def jess_cfos_example():
    """ A route for generating a link to Neuroglancer to show Jess'
    brains she requested on 6/10/2020
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """

    layer_rootdir = '/jukebox/LightSheetData/lightserv_testing/neuroglancer/jess_cfos/201904_ymaze_cfos'
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
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

    """ CV 1: Raw data an21 """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_rawdata_an21'
    cv_name = f"rawdata_an21"
    cv_path = os.path.join(layer_rootdir,'rawdata_an21')      
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

    """ CV 2: Raw atlas an21 """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawatlas_an21'
    cv_name = f"rawatlas_an21"
    cv_path = os.path.join(layer_rootdir,'rawatlas_an21')      
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

    """ CV 3: Raw cells an21 """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawcells_an21_dilated'
    cv_name = f"rawcells_an21_dilated"
    cv_path = os.path.join(layer_rootdir,'rawcells_an21_dilated')      
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

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_custom_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/jess_cfos_50micron_zres_example",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def jess_cfos_50micron_zres_example():
    """ A route for generating a link to Neuroglancer to show Jess'
    brains she requested on 6/10/2020
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """

    layer_rootdir = '/jukebox/LightSheetData/lightserv_testing/neuroglancer/201904_ymaze_cfos'
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
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

    """ CV 1: Raw data an21 """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_rawdata_an21_50micron_zres'
    cv_name = f"rawdata_an21_50micron_zres"
    cv_path = os.path.join(layer_rootdir,'rawdata_an21_50micron_zres')      
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

    """ CV 2: Raw atlas an21 """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawatlas_an21_50micron_zres'
    cv_name = f"rawatlas_an21_50micron_zres"
    cv_path = os.path.join(layer_rootdir,'rawatlas_an21_50micron_zres')      
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

    # """ CV 3: Raw cells an21 """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawcells_an21_50micron_zres_dilated'
    cv_name = f"rawcells_an21_50micron_zres_dilated"
    cv_path = os.path.join(layer_rootdir,'rawcells_an21_50micron_zres_dilated')      
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

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_custom_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/jess_cfos_spherecell_example",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def jess_cfos_spherecell_example():
    """ A route for generating a link to Neuroglancer to show Jess'
    brains she requested on 6/10/2020
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """

    layer_rootdir = '/jukebox/LightSheetData/lightserv_testing/neuroglancer/201904_ymaze_cfos'
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
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

    """ CV 1: Raw data an21 """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_rawdata_an21_iso'
    cv_name = f"rawdata_an21_iso"
    cv_path = os.path.join(layer_rootdir,'rawdata_an21_iso')      
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

    # """ CV 2: Raw atlas an21 """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawatlas_an21_iso'
    cv_name = f"rawatlas_an21_iso"
    cv_path = os.path.join(layer_rootdir,'rawatlas_an21_iso')      
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

    # """ CV 3: Raw cells an21 """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawcells_an21_dilated_iso'
    cv_name = f"rawcells_an21_dilated_iso"
    cv_path = os.path.join(layer_rootdir,'rawcells_an21_dilated_iso')      
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

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_custom_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/jess_cfos_precomp_annotations",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def jess_cfos_precomp_annotations():
    """ A route for generating a link to Neuroglancer to show one 
    of Jess' c-fos brains using a precomputed layer for annotations
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """

    layer_rootdir = '/jukebox/LightSheetData/lightserv_testing/neuroglancer/jess_cfos/201904_ymaze_cfos'
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
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

    """ CV 1: Raw data an21 """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_rawdata_an21'
    cv_name = f"rawdata_an21"
    cv_path = os.path.join(layer_rootdir,'rawdata_an21')      
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

    """ CV 2: Raw atlas an21 """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawatlas_an21'
    cv_name = f"rawatlas_an21"
    cv_path = os.path.join(layer_rootdir,'rawatlas_an21')      
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

    """ CV 3: Raw cells an21 """
    layer_type = "annotation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawcells_an21'
    cv_name = f"rawcells_an21"
    cv_path = os.path.join(layer_rootdir,'rawannotations_an21')      
    """ send the data to the viewer-launcher
    to launch the cloudvolume """                       
    cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
        cv_container_name=cv_container_name,
        layer_type=layer_type,session_name=session_name)
    requests.post('http://viewer-launcher:5005/corslauncher',json=cv_dict)
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
    proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:8080")

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_custom_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/jess_cfos_precomp_annotations_iso",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def jess_cfos_precomp_annotations_iso():
    """ A route for generating a link to Neuroglancer to show one 
    of Jess' c-fos brains in the isotropic contrived space
    using a precomputed layer for annotations
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """

    layer_rootdir = '/jukebox/LightSheetData/lightserv_testing/neuroglancer/jess_cfos/201904_ymaze_cfos'
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
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

    """ CV 1: Raw data an4 """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_rawdata_an4_iso'
    cv_name = f"rawdata_an4_iso"
    cv_path = os.path.join(layer_rootdir,'rawdata_an4_iso')      
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

    """ CV 2: Raw atlas an4 """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawatlas_an4_iso'
    cv_name = f"rawatlas_an4_iso"
    cv_path = os.path.join(layer_rootdir,'rawatlas_an4_iso')      
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

    """ CV 3: Raw cells an4 """
    layer_type = "annotation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawcells_an4_iso'
    cv_name = f"rawcells_an4_iso"
    cv_path = os.path.join(layer_rootdir,'rawcells_annotation_an4_iso')      
    """ send the data to the viewer-launcher
    to launch the cloudvolume """                       
    cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
        cv_container_name=cv_container_name,
        layer_type=layer_type,session_name=session_name)
    requests.post('http://viewer-launcher:5005/corslauncher',json=cv_dict)
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
    proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:8080")

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_custom_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/jess_cfos_201810dataset",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def jess_cfos_201810dataset():
    """ A route for generating a link to Neuroglancer to show Jess'
    brains she requested on 6/10/2020
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """

    layer_rootdir = '/jukebox/LightSheetData/lightserv_testing/neuroglancer/201904_ymaze_cfos/201810_adultacutePC_ymaze_cfos'
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
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

    """ CV 1: Raw data """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_rawdata_dadult_pc_crus1_1_iso'
    cv_name = f"rawdata_an20_iso"
    cv_path = os.path.join(layer_rootdir,'rawdata_dadult_pc_crus1_1_iso')      
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

    # """ CV 2: Raw atlas dadult_pc_crus1_1 """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawatlas_dadult_pc_crus1_1_iso'
    cv_name = f"rawatlas_dadult_pc_crus1_1_iso"
    cv_path = os.path.join(layer_rootdir,'rawatlas_dadult_pc_crus1_1_iso')      
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

    # """ CV 3: Raw cells  """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawcells_dadult_pc_crus1_1_iso_dilated_iso'
    cv_name = f"rawcells_dadult_pc_crus1_1_iso_dilated_iso"
    cv_path = os.path.join(layer_rootdir,'rawcells_dadult_pc_crus1_1_dilated_iso')      
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

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_custom_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/jess_cfos_eroded_cell_demo",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def jess_cfos_eroded_cell_demo():
    """ A route for generating a link to Neuroglancer to show one 
    of Jess' c-fos brains in the isotropic contrived space
    using a precomputed layer for annotations
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """

    layer_rootdir = '/jukebox/LightSheetData/lightserv_testing/neuroglancer/jess_cfos/202002_cfos'
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
    session_name = secrets.token_hex(6)
    viewer_id = "viewer1" # for storing the viewer info in redis
    kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

    # Set up environment to be shared by all cloudvolumes
    cv_environment = {
    'PYTHONPATH':'/opt/libraries',
    'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
    'SESSION_NAME':session_name
    }

    """ CV 1: Raw data an4 """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_rawdata_an4_saline_iso'
    cv_name = f"rawdata_an4_saline_iso"
    cv_path = os.path.join(layer_rootdir,'rawdata_an4_saline_iso')      
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

    """ CV 2: Raw atlas an4_saline """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawatlas_an4_saline_iso'
    cv_name = f"rawatlas_an4_saline_iso"
    cv_path = os.path.join(layer_rootdir,'rawatlas_an4_saline_iso')      
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

    """ CV 3: Raw cells an4_saline """
    layer_type = "annotation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawcells_an4_saline_iso'
    cv_name = f"rawcells_an4_saline_iso"
    cv_path = os.path.join(layer_rootdir,'rawcells_annotation_an4_saline_eroded_iso')      
    """ send the data to the viewer-launcher
    to launch the cloudvolume """                       
    cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
        cv_container_name=cv_container_name,
        layer_type=layer_type,session_name=session_name)
    requests.post('http://viewer-launcher:5005/corslauncher',json=cv_dict)
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
    proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:8080")

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_custom_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/jess_tracing_example",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def jess_tracing_example():
    """ A route for generating a link to Neuroglancer to show Jess'
    tracing brains she requested on 9/18/2020
    The route spawns cloudvolumes for each layer and then 
    makes a neuroglancer viewer and provides the link to the user. """
    dataset = '20170115_tp_bl6_lob6a_1000r_02'
    
    layer_rootdir = os.path.join('/jukebox/LightSheetData/lightserv_testing/neuroglancer',
        'jess_tracing',dataset)
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
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

    """ CV 1: Raw data """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_rawdata_{dataset}'
    cv_name = dataset
    cv_path = os.path.join(layer_rootdir,f'rawdata_{dataset}')      
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
    """ CV 2: Raw atlas """
    layer_type = "segmentation"
               
    cv_container_name = f'{session_name}_rawatlas_{dataset}'
    cv_name = f"rawatlas_{dataset}"
    cv_path = os.path.join(layer_rootdir,f'rawatlas_{dataset}')      
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

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_ontology_pma_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_custom_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/jess_cfos_merge_ontology_demo",
    methods=['GET'])
@logged_in
@log_http_requests
def jess_cfos_merge_ontology_demo():
    """ A route for Jess to select which of her available brains
    she wants to make links for in Neuroglancer """
    
    selected_animal_id = 'an4'
    dataset = '201904_ymaze_cfos'
    eroded_cells='no'
    layer_rootdir = os.path.join('/jukebox/LightSheetData/lightserv_testing/neuroglancer',
        'jess_cfos',dataset)
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
    session_name = secrets.token_hex(6)
    kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

    # Set up environment to be shared by all cloudvolumes
    cv_environment = {
    'PYTHONPATH':'/opt/libraries',
    'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
    'SESSION_NAME':session_name
    }

    """ CV 1: Raw data  """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_rawdata_{selected_animal_id}_iso'
    cv_name = f"rawdata_{selected_animal_id}_iso"
    cv_path = os.path.join(layer_rootdir,f'rawdata_{selected_animal_id}_iso')      
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

    # """ CV 2: Raw atlas  """
    layer_type = "segmentation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawatlas_{selected_animal_id}_iso'
    cv_name = f"rawatlas_{selected_animal_id}_iso"
    cv_path = os.path.join(layer_rootdir,f'rawatlas_hierarch_{selected_animal_id}_iso')      
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

    # # """ CV 3: Raw cells  """
    layer_type = "annotation"
               
    cv_number += 1              
    
    if eroded_cells == 'yes':
        cv_container_name = f'{session_name}_rawcells_{selected_animal_id}_eroded_iso'
        cv_name = f"rawcells_{selected_animal_id}_eroded_iso"
        cv_path = os.path.join(layer_rootdir,f'rawcells_annotation_{selected_animal_id}_eroded_iso')      
    else:    
        cv_container_name = f'{session_name}_rawcells_{selected_animal_id}_iso'
        cv_name = f"rawcells_{selected_animal_id}_iso"
        cv_path = os.path.join(layer_rootdir,f'rawcells_annotation_{selected_animal_id}_iso')      
    """ send the data to the viewer-launcher
    to launch the cors webserver """                       
    cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
        cv_container_name=cv_container_name,
        layer_type=layer_type,session_name=session_name)
    requests.post('http://viewer-launcher:5005/corslauncher',json=cv_dict)
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
    proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:8080")

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_ontology_pma_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
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
    
    neuroglancerurl = f"http://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
    logger.debug(neuroglancerurl)
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/willmore_fiber_placement_demo",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def willmore_fiber_placement_demo():
    """ A route for generating a link to Neuroglancer
    showing the Allen Brain Atlas merge-ontology demo
    """
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    session_name = secrets.token_hex(6)

    layer_rootdir = '/jukebox/LightSheetData/lightserv_testing/neuroglancer/willmore_fiber_placement'
    dataset = '20190510_fiber_placement'
    animal_id = 'm364_dorsal_up'
    """ CV 1: Registered data """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_data_{animal_id}'
    cv_name = f"registered_data_{animal_id}"
    cv_path = os.path.join(layer_rootdir,dataset,f'registered_kimatlas_data_{animal_id}')      
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

    """ CV 2: Kim et al. group Mouse Brain Atlas """
    cv_number += 1              

    layer_type = "segmentation"
               
    cv_container_name = f'{session_name}_paxinos_atlas'
    cv_name = f"Paxinos_mouse_brain_atlas"
    cv_path = '/jukebox/LightSheetData/atlas/neuroglancer/atlas/kimatlas'  
    cv_dict = dict(cv_number=cv_number,cv_path=cv_path,cv_name=cv_name,
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

    """ CV 3: Kim et al. group Mouse Brain Atlas segment boundaries """
    cv_number += 1              
    layer_type = "segmentation"
               
    cv_container_name = f'{session_name}_paxinos_atlas_boundaries'
    cv_name = f"Paxinos_mouse_brain_atlas_boundaries"
    cv_path = '/jukebox/LightSheetData/atlas/neuroglancer/atlas/kimatlas_segment_boundaries_indiv'  
    cv_dict = dict(cv_number=cv_number,cv_path=cv_path,cv_name=cv_name,
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
    
    """ Neuroglancer viewer """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_fiber_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
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
    
    neuroglancerurl = f"http://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
    logger.debug(neuroglancerurl)

    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/joey_aldolase_example",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def joey_aldolase_example():
    """ A route for generating a link to Neuroglancer to show Joey's
    3.6x SmartSPIM brains from his Aldolase C clearing antibody experiment
    """
    sample_name = 'Aldolase_C_Titration-1_100'
    
    layer_rootdir = os.path.join('/jukebox/LightSheetData/lightserv_testing/neuroglancer',
        'joey_aldolase',sample_name)
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
    session_name = secrets.token_hex(6)
    viewer_id = "viewer1" # for storing the viewer info in redis
    # kv.hmset(session_name,{"viewer_id":viewer_id})
    kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

    # Set up environment to be shared by all cloudvolumes
    cv_environment = {
    'PYTHONPATH':'/opt/libraries',
    'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
    'SESSION_NAME':session_name
    }

    """ CV 1: Raw data """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_stitcheddata_{sample_name}'
    cv_name = sample_name
    cv_path = os.path.join(layer_rootdir,f'stitched_data_{sample_name}')      
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
    
    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_custom_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
    
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/cz15_cfos_lavision_demo",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def cz15_cfos_lavision_demo():
    """ A route for generating a link to Neuroglancer to show Chris
    his c-Fos LaVision data for a single brain

    """
    brain = 'zimmerman_01'
    username = 'aichen'
    request_name = 'zimmerman_01_LaVision'
    sample_name = 'zimmerman_01_LaVision-001'
    
    layer_rootdir = os.path.join('/jukebox/LightSheetData/lightserv/',
        username,request_name,sample_name,'imaging_request_1',
        'viz','raw_atlas')
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
    session_name = secrets.token_hex(6)
    # viewer_id = "viewer1" # for storing the viewer info in redis
    kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

    # Set up environment to be shared by all cloudvolumes
    cv_environment = {
    'PYTHONPATH':'/opt/libraries',
    'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
    'SESSION_NAME':session_name
    }

    """ CV 1: Raw data """
    layer_type = "image"
               
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer
    cv_container_name = f'{session_name}_blendeddata_{brain}'
    cv_name = f'blendeddata_{brain}'
    cv_path = os.path.join(layer_rootdir,f'blendeddata_{brain}')      
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
    
    """ CV 2: Raw atlas """
    layer_type = "segmentation"
               
    cv_container_name = f'{session_name}_rawatlas_{brain}'
    cv_name = f"rawatlas_{brain}"
    cv_path = os.path.join(layer_rootdir,f'rawatlas_{brain}')      
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

    # """ CV 3: Raw cells """
    layer_type = "annotation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawcells_{brain}'
    cv_name = f"rawcells_{brain}"
    cv_path = os.path.join(layer_rootdir,f'rawcells_annotation_{brain}')      
    """ send the data to the viewer-launcher
    to launch the cloudvolume """                       
    cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
        cv_container_name=cv_container_name,
        layer_type=layer_type,session_name=session_name)
    requests.post('http://viewer-launcher:5005/corslauncher',json=cv_dict)
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
    proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:8080")

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_cfos_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng cfos viewer")
   
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/cz15_cfos_smartspim_demo",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def cz15_cfos_smartspim_demo():
    """ A route for generating a link to Neuroglancer to show Chris
    his c-Fos LaVision data for a single brain

    """
    brain = 'zimmerman_01-001'
    username = 'cz15'
    request_name = 'zimmerman_01'
    sample_name = 'zimmerman_01-001'
    
    layer_rootdir = os.path.join('/jukebox/LightSheetData/lightserv/',
        username,request_name,sample_name,'imaging_request_1',
        'viz')
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
    session_name = secrets.token_hex(6)
    # viewer_id = "viewer1" # for storing the viewer info in redis
    kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

    # Set up environment to be shared by all cloudvolumes
    cv_environment = {
    'PYTHONPATH':'/opt/libraries',
    'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
    'SESSION_NAME':session_name
    }
    
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer

    # """ CV 1: Raw data """
    layer_type = "image"
               
    cv_container_name = f'{session_name}_blendeddata_{brain}'
    cv_name = f'blendeddata_{brain}'
    cv_path = os.path.join(layer_rootdir,'rawdata',f'blendeddata_{brain}')      
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
    
    """ CV 2: Raw atlas """
    layer_type = "segmentation"
               
    cv_container_name = f'{session_name}_rawatlas_{brain}'
    cv_name = f"rawatlas_{brain}"
    cv_path = os.path.join(layer_rootdir,'raw_atlas',f'rawatlas_{brain}')      
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

    # """ CV 3: Raw cells """
    layer_type = "annotation"
               
    cv_number += 1              
    cv_container_name = f'{session_name}_rawcells_{brain}'
    cv_name = f"rawcells_{brain}"
    cv_path = os.path.join(layer_rootdir,'raw_cells',f'rawcells_annotation_{brain}')      
    """ send the data to the viewer-launcher
    to launch the cloudvolume """                       
    cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
        cv_container_name=cv_container_name,
        layer_type=layer_type,session_name=session_name)
    requests.post('http://viewer-launcher:5005/corslauncher',json=cv_dict)
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
    proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:8080")

    """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_cfos_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng cfos viewer")
   
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/diamanti_SynGCaMP7_12_001_smartspim_demo",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def diamanti_SynGCaMP7_12_001_smartspim_demo():
    """ A route for generating a link to Neuroglancer to show Mika
    her c-Fos LaVision data for a single brain

    """
    brain = 'SynGCaMP7_12-001'
    username = 'diamanti'
    request_name = 'SynGCaMP7_12'
    sample_name = 'SynGCaMP7_12-001'
    
    layer_rootdir = os.path.join('/jukebox/LightSheetData/lightserv/',
        username,request_name,sample_name,'imaging_request_2',
        'viz')
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
    session_name = secrets.token_hex(6)
    # viewer_id = "viewer1" # for storing the viewer info in redis
    kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

    # Set up environment to be shared by all cloudvolumes
    cv_environment = {
    'PYTHONPATH':'/opt/libraries',
    'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
    'SESSION_NAME':session_name
    }
    
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer

    # """ CV 1: Raw data """
    layer_type = "image"
               
    cv_container_name = f'{session_name}_blendeddata_{brain}'
    cv_name = f'blendeddata_{brain}_rechunked'
    cv_path = os.path.join(layer_rootdir,'rawdata',f'blendeddata_{brain}_rechunked')      
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
    
    """ CV 2: Raw atlas """
    layer_type = "segmentation"
               
    cv_container_name = f'{session_name}_rawatlas_{brain}'
    cv_name = f"rawatlas_{brain}_rechunked"
    cv_path = os.path.join(layer_rootdir,'raw_atlas',f'rawatlas_{brain}_rechunked')      
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

    # """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_cfos_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng cfos viewer")
   
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/soline_20201005_2357_819-001_smartspim_demo",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def soline_20201005_2357_819_sample001_smartspim_demo():
    """ A route for generating a link to Neuroglancer to show Mika
    her c-Fos LaVision data for a single brain

    """
    brain = '2020.10.05_2357_819-001'
    username = 'soline'
    request_name = '2020.10.05_2357_819'
    sample_name = '2020.10.05_2357_819-001'
    
    layer_rootdir = os.path.join('/jukebox/LightSheetData/lightserv/',
        username,request_name,sample_name,'imaging_request_1',
        'viz')
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
    session_name = secrets.token_hex(6)
    # viewer_id = "viewer1" # for storing the viewer info in redis
    kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

    # Set up environment to be shared by all cloudvolumes
    cv_environment = {
    'PYTHONPATH':'/opt/libraries',
    'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
    'SESSION_NAME':session_name
    }
    
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer

    # """ CV 1: Raw data """
    layer_type = "image"
               
    cv_container_name = f'{session_name}_blendeddata_{brain}'
    cv_name = f'blendeddata_{brain}'
    cv_path = os.path.join(layer_rootdir,'rawdata',f'blendeddata_{brain}')      
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
    
    """ CV 2: Raw atlas """
    layer_type = "segmentation"
               
    cv_container_name = f'{session_name}_rawatlas_{brain}'
    cv_name = f"rawatlas_{brain}"
    cv_path = os.path.join(layer_rootdir,'raw_atlas_aligned_to_561',f'rawatlas_{brain}')      
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


    # """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_raw_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng cfos viewer")
   
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)

@neuroglancer.route("/neuroglancer/soline_20201005_2357_819-002_smartspim_demo",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def soline_20201005_2357_819_sample002_smartspim_demo():
    """ A route for generating a link to Neuroglancer to show Mika
    her c-Fos LaVision data for a single brain

    """
    brain = '2020.10.05_2357_819-002'
    username = 'soline'
    request_name = '2020.10.05_2357_819'
    sample_name = '2020.10.05_2357_819-002'
    
    layer_rootdir = os.path.join('/jukebox/LightSheetData/lightserv/',
        username,request_name,sample_name,'imaging_request_1',
        'viz')
    config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    # Redis setup for this session
    kv = redis.Redis(host="redis", decode_responses=True)
    hosturl = os.environ['HOSTURL'] # via dockerenv
    
    session_name = secrets.token_hex(6)
    # viewer_id = "viewer1" # for storing the viewer info in redis
    kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

    # Set up environment to be shared by all cloudvolumes
    cv_environment = {
    'PYTHONPATH':'/opt/libraries',
    'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
    'SESSION_NAME':session_name
    }
    
    cv_number = 0 # to keep track of how many cloudvolumes in this viewer

    # """ CV 1: Raw data """
    layer_type = "image"
               
    cv_container_name = f'{session_name}_blendeddata_{brain}'
    cv_name = f'blendeddata_{brain}'
    cv_path = os.path.join(layer_rootdir,'rawdata',f'blendeddata_{brain}')      
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
    
    """ CV 2: Raw atlas """
    layer_type = "segmentation"
               
    cv_container_name = f'{session_name}_rawatlas_{brain}'
    cv_name = f"rawatlas_{brain}"
    cv_path = os.path.join(layer_rootdir,'raw_atlas_aligned_to_561',f'rawatlas_{brain}')      
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


    # """ Neuroglancer viewer container """
    ng_container_name = f'{session_name}_ng_container'
    ng_dict = {}
    ng_dict['hosturl'] = hosturl
    ng_dict['ng_container_name'] = ng_container_name
    ng_dict['session_name'] = session_name
    """ send the data to the viewer-launcher
    to launch the ng viewer """                       
    
    requests.post('http://viewer-launcher:5005/ng_raw_launcher',json=ng_dict)
    logger.debug("Made post request to viewer-launcher to launch ng cfos viewer")
   
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
    
    return render_template('neuroglancer/single_link.html',
        neuroglancerurl=neuroglancerurl)


@neuroglancer.route("/neuroglancer/jess_cfos_setup",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def jess_cfos_setup():
    """ A route for Jess to select which of her available brains
    she wants to make links for in Neuroglancer """
    form = CfosSetupForm(request.form)
    animal_dataset_dict = {
        '201904_ymaze_cfos':
            ['an4','an5','an6','an7','an8','an11',
            'an12','an15','an16','an18','an19','an20',
            'an22','an23','an24','an25','an26','an27'],
        '201810_adultacutePC_ymaze_cfos':
            ['dadult_pc_crus1_1','dadult_pc_crus1_2',
            'dadult_pc_crus1_3','dadult_pc_crus1_4',
            'dadult_pc_crus1_5'],
        '202002_cfos':
            ['an2_vecctrl_ymaze','an3_vecctrl_ymaze',
             'an4_vecctrl_ymaze','an9_vecctrl_ymaze',
             'an10_vecctrl_ymaze','an1_crus1_lat','an2_crus1_lat',
             'an4_crus1_lat','an5_crus1_lat','an6_crus1_lat',
             'an7_crus1_lat','an10_crus1_lat','an11_crus1_lat',
             'an13_crus1_lat','an19_crus1_lat','an4_saline','an5_cno']
    }

    # I made eroded cell precomputed layers for a subset of these
    eroded_dataset_dict = {
        '201904_ymaze_cfos':
            ['an11','an12','an25'],
        '201810_adultacutePC_ymaze_cfos':
            ['dadult_pc_crus1_1'],
        '202002_cfos':
            ['an2_vecctrl_ymaze','an7_crus1_lat','an11_crus1_lat',
             'an4_saline','an5_cno']
    }

    if request.method == 'POST':
        logger.debug("POST request")
        if form.validate_on_submit():
            logger.debug("form validated")
            animal_forms = form.animal_forms
            for animal_form in animal_forms:
                viz = animal_form.viz.data
                animal_id = animal_form.animal_id.data
                dataset = animal_form.dataset.data
                eroded_cells = animal_form.eroded_cells.data
                logger.debug(animal_id)
                logger.debug(dataset)
                logger.debug(eroded_cells)
                if viz:
                    selected_animal_id = animal_id
                    break
            layer_rootdir = os.path.join('/jukebox/LightSheetData/lightserv_testing/neuroglancer',
                'jess_cfos',dataset)
            config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
            # Redis setup for this session
            kv = redis.Redis(host="redis", decode_responses=True)
            hosturl = os.environ['HOSTURL'] # via dockerenv
            
            session_name = secrets.token_hex(6)
            kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

            # Set up environment to be shared by all cloudvolumes
            cv_environment = {
            'PYTHONPATH':'/opt/libraries',
            'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
            'SESSION_NAME':session_name
            }

            """ CV 1: Raw data  """
            layer_type = "image"
                       
            cv_number = 0 # to keep track of how many cloudvolumes in this viewer
            cv_container_name = f'{session_name}_rawdata_{selected_animal_id}_iso'
            cv_name = f"rawdata_{selected_animal_id}_iso"
            cv_path = os.path.join(layer_rootdir,f'rawdata_{selected_animal_id}_iso')      
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

            # """ CV 2: Raw atlas  """
            layer_type = "segmentation"
                       
            cv_number += 1              
            cv_container_name = f'{session_name}_rawatlas_{selected_animal_id}_iso'
            cv_name = f"rawatlas_{selected_animal_id}_iso"
            cv_path = os.path.join(layer_rootdir,f'rawatlas_{selected_animal_id}_iso')      
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

            # # """ CV 3: Raw cells  """
            layer_type = "annotation"
                       
            cv_number += 1              
            
            if eroded_cells == 'yes':
                cv_container_name = f'{session_name}_rawcells_{selected_animal_id}_eroded_iso'
                cv_name = f"rawcells_{selected_animal_id}_eroded_iso"
                cv_path = os.path.join(layer_rootdir,f'rawcells_annotation_{selected_animal_id}_eroded_iso')      
            else:    
                cv_container_name = f'{session_name}_rawcells_{selected_animal_id}_iso'
                cv_name = f"rawcells_{selected_animal_id}_iso"
                cv_path = os.path.join(layer_rootdir,f'rawcells_annotation_{selected_animal_id}_iso')      
            """ send the data to the viewer-launcher
            to launch the cors webserver """                       
            cv_dict = dict(cv_path=cv_path,cv_name=cv_name,
                cv_container_name=cv_container_name,
                layer_type=layer_type,session_name=session_name)
            requests.post('http://viewer-launcher:5005/corslauncher',json=cv_dict)
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
            proxy_h.addroute(proxypath=proxypath,proxytarget=f"http://{cv_container_name}:8080")

            """ Neuroglancer viewer container """
            ng_container_name = f'{session_name}_ng_container'
            ng_dict = {}
            ng_dict['hosturl'] = hosturl
            ng_dict['ng_container_name'] = ng_container_name
            ng_dict['session_name'] = session_name
            """ send the data to the viewer-launcher
            to launch the ng viewer """                       
            
            requests.post('http://viewer-launcher:5005/ng_custom_launcher',json=ng_dict)
            logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
            
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
            
            neuroglancerurl = f"http://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
            logger.debug(neuroglancerurl)
            
            return render_template('neuroglancer/single_link.html',
                neuroglancerurl=neuroglancerurl)
        else: # not validated
            logger.debug("Form not validated")
            flash("There were errors below. Correct them in order to proceed.",'danger')
            logger.debug(form.errors)
            for key in form.errors:
                for error in form.errors[key]:
                    flash(error,'danger')
    """ First clear out any existing subforms from previous http requests """
    while len(form.animal_forms) > 0:
        form.animal_forms.pop_entry()
    
    animal_forms = form.animal_forms
    for dataset in animal_dataset_dict:
        for an_index in range(len(animal_dataset_dict[dataset])):
            an_list = animal_dataset_dict[dataset]
            animal_id = an_list[an_index]
            animal_forms.append_entry()
            this_animal_form = animal_forms[-1]
            this_animal_form.dataset.data = dataset
            this_animal_form.animal_id.data = animal_id
            if animal_id in eroded_dataset_dict[dataset]:
                this_animal_form.eroded_cells.data = 'yes'
            else:
                this_animal_form.eroded_cells.data = 'no'

    return render_template('neuroglancer/jess_cfos_setup.html',form=form)

@neuroglancer.route("/neuroglancer/jess_tracing_setup",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def jess_tracing_setup():
    """ A route for Jess to select which of her available tracing brains
    she wants to make links for in Neuroglancer """
    form = CfosSetupForm(request.form)
    animal_dataset_list = ['20170115_tp_bl6_lob6a_1000r_02','20170115_tp_bl6_lob6a_500r_01',
        '20170204_tp_bl6_cri_1000r_02','20180417_jg60_bl6_cri_04'] 
    if request.method == 'POST':
        logger.debug("POST request")
        if form.validate_on_submit():
            logger.debug("form validated")
            animal_forms = form.animal_forms
            for animal_form in animal_forms:
                viz = animal_form.viz.data
                dataset = animal_form.dataset.data
                logger.debug(dataset)
                if viz:
                    selected_dataset = dataset
                    break
            layer_rootdir = os.path.join('/jukebox/LightSheetData/lightserv_testing/neuroglancer',
                'jess_tracing',selected_dataset)
            config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
            # Redis setup for this session
            kv = redis.Redis(host="redis", decode_responses=True)
            hosturl = os.environ['HOSTURL'] # via dockerenv
            
            session_name = secrets.token_hex(6)
            kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

            # Set up environment to be shared by all cloudvolumes
            cv_environment = {
            'PYTHONPATH':'/opt/libraries',
            'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
            'SESSION_NAME':session_name
            }

            """ CV 1: Raw data  """
            layer_type = "image"
                       
            cv_number = 0 # to keep track of how many cloudvolumes in this viewer
            cv_container_name = f'{session_name}_rawdata_{selected_dataset}'
            cv_name = f"rawdata_{selected_dataset}"
            cv_path = os.path.join(layer_rootdir,f'rawdata_{selected_dataset}')      
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

            """ CV 2: Raw atlas  """
            layer_type = "segmentation"
                       
            cv_number += 1              
            cv_container_name = f'{session_name}_rawatlas_{selected_dataset}'
            cv_name = f"rawatlas_{selected_dataset}"
            cv_path = os.path.join(layer_rootdir,f'rawatlas_{selected_dataset}')      
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

            """ Neuroglancer viewer container """
            ng_container_name = f'{session_name}_ng_container'
            ng_dict = {}
            ng_dict['hosturl'] = hosturl
            ng_dict['ng_container_name'] = ng_container_name
            ng_dict['session_name'] = session_name
            """ send the data to the viewer-launcher
            to launch the ng viewer """                       
            
            requests.post('http://viewer-launcher:5005/ng_ontology_pma_launcher',json=ng_dict)
            logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
            
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
            
            neuroglancerurl = f"http://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
            logger.debug(neuroglancerurl)
            
            return render_template('neuroglancer/single_link.html',
                neuroglancerurl=neuroglancerurl)
        else: # not validated
            logger.debug("Form not validated")
            flash("There were errors below. Correct them in order to proceed.",'danger')
            logger.debug(form.errors)
            for key in form.errors:
                for error in form.errors[key]:
                    flash(error,'danger')
    """ First clear out any existing subforms from previous http requests """
    while len(form.animal_forms) > 0:
        form.animal_forms.pop_entry()
    
    animal_forms = form.animal_forms
    for dataset in animal_dataset_list:
        animal_forms.append_entry()
        this_animal_form = animal_forms[-1]
        this_animal_form.dataset.data = dataset

    return render_template('neuroglancer/jess_tracing_setup.html',form=form)

@neuroglancer.route("/neuroglancer/zimmerman_02_cfos_setup",
    methods=['GET','POST'])
@logged_in
@log_http_requests
def zimmerman_02_cfos_setup():
    """ A route for Chris to select which of his available brains
    he wants to make links for in Neuroglancer """
    form = LightservCfosSetupForm(request.form)
    username = 'cz15'
    request_name = 'zimmerman_02'
    imaging_request_number = 1
    image_resolution = '3.6x'
    restrict_dict = dict(username=username,request_name=request_name)
    sample_contents = db_lightsheet.Request.Sample() & restrict_dict
    sample_names = sample_contents.fetch('sample_name')

    if request.method == 'POST':
        logger.debug("POST request")
        if form.validate_on_submit():
            logger.debug("form validated")
            sample_forms = form.sample_forms
            for sample_form in sample_forms:
                viz = sample_form.viz.data
                sample_name = sample_form.sample_name.data
                if viz:
                    selected_sample_name = sample_name
                    break
            layer_rootdir = os.path.join('/jukebox/LightSheetData/lightserv',
                username,request_name,selected_sample_name,
                f'imaging_request_{imaging_request_number}',
                'viz',)
            config_proxy_auth_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
            # Redis setup for this session
            kv = redis.Redis(host="redis", decode_responses=True)
            hosturl = os.environ['HOSTURL'] # via dockerenv
            
            session_name = secrets.token_hex(6)
            kv.hmset(session_name,{"cv_count":0}) # initialize the number of cloudvolumes in this ng session

            # Set up environment to be shared by all cloudvolumes
            cv_environment = {
            'PYTHONPATH':'/opt/libraries',
            'CONFIGPROXY_AUTH_TOKEN':f"{config_proxy_auth_token}",
            'SESSION_NAME':session_name
            }

            """ CV 1: 642 Channel """
            layer_type = "image"
                       
            cv_number = 0 # to keep track of how many cloudvolumes in this viewer
            cv_container_name = f'{session_name}_{selected_sample_name}_channel_642'
            cv_name = f'corrected_data_{selected_sample_name}_channel_642'
            cv_path = os.path.join(layer_rootdir,'rawdata',f'channel_642_corrected')      
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
            

            """ CV 2: 488 Channel (first check that it exists) """

            layer_type = "image"
                       
            cv_container_name = f'{session_name}_{selected_sample_name}_channel_488'
            cv_name = f'corrected_data_{selected_sample_name}_channel_488'
            cv_path = os.path.join(layer_rootdir,'rawdata',f'channel_488_corrected')      
            if os.path.exists(cv_path):
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

            """ CV 3: Raw space atlas (first check that it exists) """

            layer_type = "segmentation"
                       
            cv_container_name = f'{session_name}_{selected_sample_name}_raw_atlas'
            cv_name = f'{selected_sample_name}_raw_atlas'
            cv_path = os.path.join(layer_rootdir,'raw_atlas',f'{selected_sample_name}_raw_atlas')      
            if os.path.exists(cv_path):
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

            """ Neuroglancer viewer container """
            ng_container_name = f'{session_name}_ng_container'
            ng_dict = {}
            ng_dict['hosturl'] = hosturl
            ng_dict['ng_container_name'] = ng_container_name
            ng_dict['session_name'] = session_name
            
            """ send the data to the viewer-launcher
            to launch the ng viewer """                       
            
            requests.post('http://viewer-launcher:5005/ng_cfos_launcher',json=ng_dict)
            logger.debug("Made post request to viewer-launcher to launch ng custom viewer")
            
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
            
            neuroglancerurl = f"http://{hosturl}/nglancer/{session_name}/v/{viewer_dict['token']}/" # localhost/nglancer is reverse proxied to 8080 inside the ng container
            logger.debug(neuroglancerurl)
            
            return render_template('neuroglancer/single_link.html',
                neuroglancerurl=neuroglancerurl)
        else: # not validated
            logger.debug("Form not validated")
            flash("There were errors below. Correct them in order to proceed.",'danger')
            logger.debug(form.errors)
            for key in form.errors:
                for error in form.errors[key]:
                    flash(error,'danger')
    """ First clear out any existing subforms from previous http requests """
    while len(form.sample_forms) > 0:
        form.sample_forms.pop_entry()
    
    sample_forms = form.sample_forms
    for sample_name in sample_names:
        sample_forms.append_entry()
        this_sample_form = sample_forms[-1]
        this_sample_form.sample_name.data = sample_name

    return render_template('neuroglancer/lightserv_cfos_setup.html',
        request_name=request_name,form=form)


@neuroglancer.route("/admin/confproxy_table",methods=['GET'])
@logged_in_as_admin
def confproxy_table():
    """ A route to visualize the entries in the confproxy table
    and their associated docker container names """
    logger.debug("In confproxy_table route")
    sort = request.args.get('sort', 'session_name') # first is the variable name, second is default value
    reverse = (request.args.get('direction', 'asc') == 'desc')
    kv = redis.Redis(host="redis", decode_responses=True)
    proxy_h = pp.progproxy(target_hname='confproxy')
    """ Grab all of the confproxy routes from the proxy table """
    response_all = proxy_h.getroutes()
    proxy_dict = json.loads(response_all.text)
    logger.debug("All current confproxy routes:")
    logger.debug(proxy_dict)
    table_contents = []
    """ Figure out session name and
    whether there are other containers associated """
    session_names = [key.split('/')[-1] for key in proxy_dict.keys() if 'viewer' in key]
    viewer_dict = {}
    for session_name in session_names:
        # first ng viewer
        ng_table_entry = {}
        ng_proxypath = f'/viewers/{session_name}'
        ng_table_entry['session_name'] = session_name
        ng_table_entry['proxy_path'] =  ng_proxypath
        # Figure out last activity
        ng_last_activity = proxy_dict[f'/viewers/{session_name}']['last_activity']
        ng_last_activity_dt = datetime.strptime(ng_last_activity,datetimeformat)
        # ng_last_activity_dt_
        ng_td = datetime.utcnow() - ng_last_activity_dt
        ng_td_str = humanize.naturaltime(ng_td)

        ng_table_entry['last_activity'] = ng_td_str
        # now find any cloudvolumes with this session name
        cv_proxypaths = [key for key in proxy_dict.keys() if f'cloudvols/{session_name}' in key]
        viewer_dict[session_name] = cv_proxypaths
        """ Now figure out container IDs """
        session_dict = kv.hgetall(session_name)
        # logger.debug(session_dict)
        cv_count = len(cv_proxypaths)
        cv_container_names = [session_dict[f'cv{x+1}_container_name'] for x in range(cv_count)]
        ng_container_name = session_dict['ng_container_name']
        ng_table_entry['container_name'] = ng_container_name
        container_names = cv_container_names + [ng_container_name]
        container_dict = {'list_of_container_names':container_names}
        response = requests.post('http://viewer-launcher:5005/get_container_info',json=container_dict)
        container_info_dict = json.loads(response.text)
        ng_container_info_dict = container_info_dict[ng_container_name]
        ng_container_id = ng_container_info_dict['container_id']
        ng_container_image = ng_container_info_dict['container_image']
        """ If the container was manually killed then ng_container_id and cv_container_name
        will be set to None here """
        if ng_container_id:
            ng_table_entry['container_id'] = ng_container_id
            ng_table_entry['image'] = ng_container_image
            table_contents.append(ng_table_entry)
        else:
            # this container needs to be removed from the confproxy since it is no longer running
            proxy_h.deleteroute(ng_proxypath)
            logger.debug("After removing ng proxypath current confproxy routes are:")
            updated_response = proxy_h.getroutes()
            updated_proxy_dict = json.loads(updated_response.text)
            logger.debug(updated_proxy_dict)
        for ii in range(cv_count):
            cv_table_entry = {
                'session_name':session_name,
                'proxy_path':cv_proxypaths[ii],
            }
            cv_container_name = cv_container_names[ii]
            this_container_info_dict = container_info_dict[cv_container_name]
            cv_proxy_key = next(x for x in proxy_dict.keys() if f'/cloudvols/{session_name}' in x)
            cv_last_activity = proxy_dict[cv_proxy_key]['last_activity']
            logger.debug(cv_last_activity)
            cv_last_activity_dt = datetime.strptime(cv_last_activity,datetimeformat)
            cv_td = datetime.utcnow() - cv_last_activity_dt
            cv_td_str = humanize.naturaltime(cv_td)

            cv_table_entry['last_activity'] = cv_td_str
            cv_container_id = this_container_info_dict['container_id']
            cv_container_image = this_container_info_dict['container_image']
            """ If the container was manually killed then cv_container_id and cv_container_image
            will be set to None here """
            if cv_container_id:
                cv_table_entry['container_name'] = cv_container_name
                cv_table_entry['container_id'] = cv_container_id
                cv_table_entry['image'] = cv_container_image
                table_contents.append(cv_table_entry)
            else:
                # Then this container needs to be removed from the confproxy since it is no longer running
                proxy_h.deleteroute(cv_proxypaths[ii])
                logger.debug("deleted cv proxypath")
    sorted_table_contents = sorted(table_contents,
        key=partial(table_sorter,sort_key=sort),reverse=reverse) # partial allows you to pass in a parameter to the function
    table = ConfproxyAdminTable(sorted_table_contents,
        sort_by=sort,sort_reverse=reverse)

    return render_template('neuroglancer/confproxy_admin_panel.html',table=table)
   
