from flask import (render_template, request, redirect,
				   Blueprint, session, url_for, flash,
				   Markup, Request, Response,jsonify,
                   current_app)
from lightserv import db_lightsheet, db_admin, cel, smtp_connect
from lightserv.main.utils import logged_in, table_sorter, log_http_requests
from functools import partial, wraps

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
file_handler = logging.FileHandler('logs/taskmanager_tasks.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)


@cel.task()
def hello():
    return "hello world"

@cel.task()
def goodbye():
    return "goodbye world"    

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
    return "Test email sent!"
