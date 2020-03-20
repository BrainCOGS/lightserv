from flask import (render_template, request, redirect,
				   Blueprint, session, url_for, flash,
				   Markup, Request, Response,jsonify,
                   current_app)
from lightserv import db_lightsheet, db_admin, cel, smtp_connect
from lightserv.main.utils import logged_in, table_sorter, log_http_requests
from functools import partial, wraps
from . import tasks
import datajoint as dj
import requests

import logging
import paramiko,time
import os
from datetime import datetime, timedelta
from email.message import EmailMessage


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

@taskmanager.route("/check_all_statuses") 
def check_all_statuses():
    tasks.status_checker.delay()
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
    tasks.hello.delay()
    return "Said hello"

@taskmanager.route("/say_goodbye") 
def say_goodbye():
    tasks.goodbye.delay()
    return "Said goodbye"

@taskmanager.route("/send_feedback_email") 
def send_feedback_email():
    eta = datetime.utcnow() + timedelta(seconds=1)
    tasks.send_email.apply_async(kwargs={'request_name':'test'},eta=eta)
    return "Email sent"
