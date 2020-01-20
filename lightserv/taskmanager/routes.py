from flask import (render_template, request, redirect,
				   Blueprint, session, url_for, flash,
				   Markup, Request, Response,jsonify)
from lightserv import db_admin, cel
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

@cel.task()
def status_checker():
    """ Checks all outstanding job statuses on spock
    and updates their status in the db """

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
    time_start = time.time()
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
            status_code = status_codes[ii]
            insert_dict = {'jobid':jobid,'username':username,'status':status_code}
            insert_list.append(insert_dict)
       
        db_admin.SpockJobManager.insert(insert_list,replace=True)
    finally:
        client.close()
    time_end = time.time()
    # print(f"Took {time_end-time_start} seconds" )
    return jsonify(jobids=jobids,status_codes=status_codes)

@taskmanager.route("/check_all_statuses") 
def check_all_statuses():
    # query = db_admin.SpockJobManager() & 'status!="COMPLETED"' & 'status!="FAILED"'
    job_contents = db_admin.SpockJobManager()
    unique_contents = dj.U('jobid','username',).aggr(job_contents,timestamp='max(timestamp)')*job_contents
    incomplete_contents = unique_contents & 'status!="COMPLETED"' & 'status!="FAILED"'
    jobids = list(incomplete_contents.fetch('jobid'))
    if jobids == []:
        return "No jobs to check"
    jobids_str = ','.join(str(jobid) for jobid in jobids)
    # jobids_str = '16046124,16046126,16046129'
    port = 22
    username = 'ahoag'
    hostname = 'spock.pni.princeton.edu'
    time_start = time.time()
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
            status_code = status_codes[ii]
            insert_dict = {'jobid':jobid,'username':username,'status':status_code}
            insert_list.append(insert_dict)
       
        db_admin.SpockJobManager.insert(insert_list)
    finally:
        client.close()
    time_end = time.time()
    # print(f"Took {time_end-time_start} seconds" )
    return jsonify(jobids=jobids,status_codes=status_codes)

@taskmanager.route("/say_hello") 
def say_hello():
    hello.delay()
    return "Said hello"

@cel.task()
def hello():
    return "hello world"