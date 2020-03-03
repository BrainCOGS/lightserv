from flask import (render_template, request, redirect,
				   Blueprint, session, url_for, flash,
				   Markup, Request, Response,jsonify,
                   current_app)
from lightserv import db_lightsheet,db_admin, cel, mail
from lightserv.main.utils import logged_in, table_sorter, log_http_requests
from functools import partial, wraps

import datajoint as dj
import requests

import logging
import paramiko,time
import os
from flask_mail import Message
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/taskmanager_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

taskmanager = Blueprint('taskmanager',__name__)

@cel.task()
def status_checker():
    """ 
    Checks all outstanding job statuses on spock
    and updates their status in the SpockJobManager() in db_admin
    and ProcessingResolutionRequest() in db_lightsheet, 
    then finally figures out which ProcessingRequest() 
    entities are now complete based on the potentially multiple
    ProcessingResolutionRequest() entries they reference.

    A ProcessingRequest() can consist of several jobs because
    jobs are at the ProcessingResolutionRequest() level. 
    If any of the ProcessingResolutionRequest() jobs failed,
    set the processing_progress in the ProcessingRequest() 
    table to 'failed'. If all jobs completed, then set 
    processing_progress to 'complete'
    """
    processing_resolution_contents = db_lightsheet.Request.ProcessingResolutionRequest()
   
    """ First get all rows with latest timestamps """
    job_contents = db_admin.SpockJobManager()
    unique_contents = dj.U('jobid','username',).aggr(
        job_contents,timestamp='max(timestamp)')*job_contents
    
    """ Get a list of all jobs we need to check up on, i.e.
    those that could conceivably change. Also list the problematic_codes
    which will be used later for error reporting to the user.
    """

    problematic_codes = ("FAILED","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REVOKED")
    # static_codes = ('COMPLETED','FAILED','BOOT_FAIL','CANCELLED','DEADLINE','OUT_OF_MEMORY','REVOKED')
    ongoing_codes = ('SUBMITTED','RUNNING','PENDING','REQUEUED','RESIZING','SUSPENDED')
    incomplete_contents = unique_contents & f'status in {ongoing_codes}'
    jobids = list(incomplete_contents.fetch('jobid'))
    if jobids == []:
        return "No jobs to check"
    jobids_str = ','.join(str(jobid) for jobid in jobids)
    logger.debug(f"Outstanding job ids are: {jobids}")
    port = 22
    username = 'ahoag'
    hostname = 'spock.pni.princeton.edu'

    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)
        
        client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)
        logger.debug("connected to spock")
        command = """sacct -X -b -P -n -a  -j {} | cut -d "|" -f2""".format(jobids_str)
        stdin, stdout, stderr = client.exec_command(command)
        stdout_str = stdout.read().decode("utf-8")
        status_codes = stdout_str.strip('\n').split('\n')
        insert_list = []
        for ii in range(len(jobids)):
            jobid = jobids[ii]
            logger.debug(f"Updating entries for jobid={jobid}")
            status_code = status_codes[ii]
            """ Update the ProcessingResolutionRequest() entry """
            this_processing_resolution_content = processing_resolution_contents & f'spock_jobid="{jobid}"'
            dj.Table._update(this_processing_resolution_content,'spock_job_progress',status_code)
            """ Make the dict that will be batch replaced in SpockJobManager() """
            insert_dict = {'jobid':jobid,'username':username,'status':status_code}
            insert_list.append(insert_dict)

        db_admin.SpockJobManager.insert(insert_list,replace=True)
        client.close()
    except:
        logger.info("There was a problem getting the status of outstanding jobs from spock")
        client.close()
        return "Error"
        
    """ Now for each outstanding processing request, go through list of 
        jobids that are linked to that request and update the processing_progress
        accordingly """
    processing_request_contents = db_lightsheet.Request.ProcessingRequest()
    running_processing_requests_modified_contents = (processing_request_contents & \
        'processing_progress="running"').aggr(processing_resolution_contents,
                   number_of_jobs="count(*)",
                   number_of_pending_jobs='SUM(spock_job_progress="PENDING")',
                   number_of_completed_jobs='SUM(spock_job_progress="COMPLETED")',
                   number_of_problematic_jobs=f'SUM(spock_job_progress in {problematic_codes})',
                   spock_jobid ='spock_jobid') 
    """ For processing requests where all jobids have status=COMPLETE,
    then the processing_progress='complete' for the whole processing request """
    completed_processing_requests_modified_contents = (running_processing_requests_modified_contents & \
        'number_of_completed_jobs = number_of_jobs')

    completed_processing_primary_keys_dict_list = completed_processing_requests_modified_contents.fetch(
        'username',
        'request_name',
        'sample_name',
        'imaging_request_number',
        'processing_request_number',
        as_dict=True)

    for d in completed_processing_primary_keys_dict_list:
        logger.debug("Updating processing request table")
        username = d.get('username')
        request_name = d.get('request_name')
        sample_name = d.get('sample_name')
        imaging_request_number = d.get('imaging_request_number')
        processing_request_number = d.get('processing_request_number')
        dj.Table._update(processing_request_contents & \
            f'username="{username}"' & f'request_name="{request_name}"' & \
            f'sample_name="{sample_name}"' & f'imaging_request_number={imaging_request_number}' & \
            f'processing_request_number={processing_request_number}',
            'processing_progress','complete')
        
        """ Send email to user saying their entire processing request is complete """
        sample_basepath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
            request_name,sample_name,f'imaging_request_{imaging_request_number}')

        output_directory = os.path.join(sample_basepath,'output',
                f'processing_request_{processing_request_number}')
        
        msg = Message('Lightserv automated email: SUCCESSFUL processing request',
                        sender='lightservhelper@gmail.com',
                        recipients=['ahoag@princeton.edu']) # send it to me while in DEV phase
                    
        msg.body = ('Hello!\n\nThis is an automated email sent from lightserv, '
            'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
            'The processing for your request:\n\n'
            f'request_name: "{request_name}"\n'
            f'sample_name: "{sample_name}"\n'
            f'imaging_request_number: {imaging_request_number}\n'
            f'processing_request_number: {processing_request_number}\n\n'
            'was completed successfully.'
            'You can find your processed data here:'
            f'\n{output_directory}'
            '\n\nThanks,\nThe Histology and Brain Registration Core Facility.')
        mail.send(msg)
        logger.debug("Sent email that processing was completed")
    
    """ For processing requests where even just one jobid has a problematic status,
    then update the processing_progress='failed' for the whole processing request.
    Can provide more details in an email """
    problematic_processing_requests_modified_contents = (running_processing_requests_modified_contents & \
        'number_of_problematic_jobs > 0')
    problematic_processing_primary_keys_dict_list = problematic_processing_requests_modified_contents.fetch(
        'username',
        'request_name',
        'sample_name',
        'imaging_request_number',
        'processing_request_number',
        as_dict=True)

    for d in problematic_processing_primary_keys_dict_list:
        logger.debug("Updating processing request table")
        username = d.get('username')
        request_name = d.get('request_name')
        sample_name = d.get('sample_name')
        imaging_request_number = d.get('imaging_request_number')
        processing_request_number = d.get('processing_request_number')
        dj.Table._update(processing_request_contents & \
            f'username="{username}"' & f'request_name="{request_name}"' & \
            f'sample_name="{sample_name}"' & f'imaging_request_number={imaging_request_number}' & \
            f'processing_request_number={processing_request_number}',
            'processing_progress','failed')
        sample_basepath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
            request_name,sample_name,f'imaging_request_{imaging_request_number}')

        output_directory = os.path.join(sample_basepath,'output',
                f'processing_request_{processing_request_number}')
        
        msg_user = Message('Lightserv automated email: FAILED processing request',
                        sender='lightservhelper@gmail.com',
                        recipients=['ahoag@princeton.edu']) # send it to me while in DEV phase
                    
        msg_user.body = ('Hello!\n\nThis is an automated email sent from lightserv, '
            'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
            'The processing for your request:\n\n'
            f'request_name: "{request_name}"\n'
            f'sample_name: "{sample_name}"\n'
            f'imaging_request_number: {imaging_request_number}\n'
            f'processing_request_number: {processing_request_number}\n\n'
            'has failed. '
            '\n\nThank you for your patience while we look into why this happened. We will get back to you shortly. '
            '\n\nIf you have any questions or comments about this please reply to this message.'
            '\n\nThanks,\nThe Histology and Brain Registration Core Facility.')
        mail.send(msg_user)

        """ Now send a message to the admins to alert them that a processing request has failed """
        resolution_contents_this_request = db_lightsheet.Request.ProcessingResolutionRequest() & \
            f'username="{username}"' & \
            f'request_name="{request_name}"' & f'sample_name="{sample_name}"' & \
            f'imaging_request_number={imaging_request_number}' & \
            f'processing_request_number={processing_request_number}'
        job_dict_list = resolution_contents_this_request.fetch(
            'image_resolution','spock_jobid','spock_job_progress',as_dict=True)
        job_str_lines = '\n'.join(['{0} {1} {2}'.format(
            job_dict['image_resolution'],job_dict['spock_jobid'],
            job_dict['spock_job_progress']) for job_dict in job_dict_list])
        msg_admin = Message('Lightserv automated email: FAILED processing request',
                        sender='lightservhelper@gmail.com',
                        recipients=['lightservhelper@gmail.com']) # send it to 
                    
        msg_admin.body = ('Hello!\n\nThis is an automated email sent from lightserv, '
            'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
            'The processing for request:\n\n'
            f'request_name: "{request_name}"\n'
            f'sample_name: "{sample_name}"\n'
            f'imaging_request_number: {imaging_request_number}\n'
            f'processing_request_number: {processing_request_number}\n\n'
            'has failed.\n\n'
            'In particular, the statuses of all jobs in this processing request are:\n'
            '#image_resolution  jobid     status\n'
            '{}\n'.format(job_str_lines))

        mail.send(msg_admin)

    # for each running process, find all jobids in the processing resolution request tables
    return jsonify(jobids=jobids,status_codes=status_codes)

@taskmanager.route("/check_all_statuses") 
def check_all_statuses():
    status_checker.delay()
    return "Checked all statuses"

@taskmanager.route("/submit_job")
def submit_job(): 
    """ A useful route for launching a test job on spock 
    Helpful for debugging the status_checker() route 
    and the celery scheduler to monitor spock job progress
    """
    command = """sbatch --parsable test_slurm_scripts/submit.sh """ 
    port = 22
    username = 'ahoag'
    hostname = 'spock.pni.princeton.edu'
    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)
        
        client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)

        stdin, stdout, stderr = client.exec_command(command)
        jobid = str(stdout.read().decode("utf-8").strip('\n'))
        status = 'SUBMITTED'
        entry_dict = {'jobid':jobid,'username':username,'status':status}
        db_admin.SpockJobManager.insert1(entry_dict)    
    finally:
        client.close()

    return "Job submitted"
    # return redirect(url_for('main.home'))

@taskmanager.route("/submit_failed_job")
def submit_failed_job(): 
    """ A useful route for launching a test job on spock 
    that will intentionally result in a FAILED status code
    Helpful for debugging the status_checker() route 
    and the celery scheduler to monitor spock job progress
    """
    command = """sbatch --parsable test_slurm_scripts/submit_failed.sh """ 
    port = 22
    username = 'ahoag'
    hostname = 'spock.pni.princeton.edu'
    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)
        
        client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)

        stdin, stdout, stderr = client.exec_command(command)
        jobid = str(stdout.read().decode("utf-8").strip('\n'))
        # jobid = 16046124
        status = 'SUBMITTED'
        entry_dict = {'jobid':jobid,'username':username,'status':status}
        db_admin.SpockJobManager.insert1(entry_dict)    
    finally:
        client.close()

    return "Job submitted"
    # return redirect(url_for('main.home'))

@taskmanager.route("/say_hello") 
def say_hello():
    hello.delay()
    return "Said hello"

@cel.task()
def hello():
    return "hello world"

@taskmanager.route("/say_goodbye") 
def say_goodbye():
    goodbye.delay()
    return "Said goodbye"

@cel.task()
def goodbye():
    return "goodbye world"    


@taskmanager.route("/send_feedback_email") 
def send_feedback_email():
    eta = datetime.utcnow() + timedelta(seconds=1)
    send_email.apply_async(kwargs={'request_name':'test'},eta=eta)
    return "Email sent"

@cel.task()
def send_email(request_name):
    msg_user = Message('Lightserv automated email: Your feedback (test)',
                        sender='lightservhelper@gmail.com',
                        recipients=['ahoag@princeton.edu']) # send it to me while in DEV phase
                    
    msg_user.body = ('Hello!\n\nThis is an automated email sent from lightserv, '
        'the Light Sheet Microscopy portal at the Histology and Brain Registration Core Facility. '
        'We would love your feedback on your request:\n\n'
        f'request_name: {request_name}\n\n'        
        'Thanks,\nThe Histology and Brain Registration Core Facility.')
    mail.send(msg_user)
    return "Test Email sent!"
