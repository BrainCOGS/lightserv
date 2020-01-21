from flask import (render_template, request, redirect,
				   Blueprint, session, url_for, flash,
				   Markup, Request, Response,jsonify)
from lightserv import db_lightsheet,db_admin, cel
from lightserv.main.utils import logged_in, table_sorter, log_http_requests
from functools import partial, wraps

import datajoint as dj
import requests

import logging
import paramiko,time

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
        # jobid = 16046124
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


@cel.task()
def status_checker():
    """ Checks all outstanding job statuses on spock
    and updates their status in the SpockJobManager() in db_admin
    and ProcessingResolutionRequest() in db_lightsheet, 
    then finally figures out which ProcessingRequest() 
    entities are now complete based on the potentially multiple
    ProcessingResolutionRequest() entries they reference. """
    processing_resolution_contents = db_lightsheet.Request.ProcessingResolutionRequest()
    """ First get all rows with latest timestamps """
    job_contents = db_admin.SpockJobManager()
    unique_contents = dj.U('jobid','username',).aggr(job_contents,timestamp='max(timestamp)')*job_contents
    incomplete_contents = unique_contents & 'status!="COMPLETED"' & 'status!="FAILED"'
    jobids = list(incomplete_contents.fetch('jobid'))
    if jobids == []:
        return "No jobs to check"
    jobids_str = ','.join(str(jobid) for jobid in jobids)

    port = 22
    username = 'ahoag'
    hostname = 'spock.pni.princeton.edu'
    # time_start = time.time()

    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)
        
        client.connect(hostname, port=port, username=username, allow_agent=False,look_for_keys=True)
        # jobids_str = ','.join(str(jobid) for jobid in jobids)
        # for jobid in jobids:
            # command += """sacct -b -P -n -a  -j {} | head -1 | cut -d "|" -f2; """.format(jobid)
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
        logger.info("There was a problem connecting to spock to get the status of outstanding jobs")
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
                   number_of_failed_jobs='SUM(spock_job_progress="FAILED")',
                   spock_jobid ='spock_jobid') 
    """ For processing requests where all jobids have status=COMPLETE,
    then the processing_progress='complete' for the whole processing request """
    completed_processing_requests_modified_contents = (running_processing_requests_modified_contents & \
        'number_of_completed_jobs = number_of_jobs')

    completed_procesing_primary_keys_dict_list = completed_processing_requests_modified_contents.fetch(
        'username',
        'request_name',
        'sample_name',
        'imaging_request_number',
        'processing_request_number',
        as_dict=True)

    for d in completed_procesing_primary_keys_dict_list:
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
    
    """ For processing requests where even just one jobid has status=FAILED,
    then update the processing_progress='failed' for the whole processing request.
    Can provide more details in an email """
    failed_processing_requests_modified_contents = (running_processing_requests_modified_contents & \
        'number_of_failed_jobs > 0')
    failed_procesing_primary_keys_dict_list = failed_processing_requests_modified_contents.fetch(
        'username',
        'request_name',
        'sample_name',
        'imaging_request_number',
        'processing_request_number',
        as_dict=True)

    for d in failed_procesing_primary_keys_dict_list:
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

    

    # for each running process, find all jobids in the processing resolution request tables
    return jsonify(jobids=jobids,status_codes=status_codes)

@taskmanager.route("/check_all_statuses") 
def check_all_statuses():
    status_checker.delay()
    return "Checked all statuses"

@taskmanager.route("/say_hello") 
def say_hello():
    hello.delay()
    return "Said hello"

@cel.task()
def hello():
    return "hello world"