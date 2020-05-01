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
def send_email(subject,body,sender_email='lightservhelper@gmail.com'):
	if os.environ['FLASK_MODE'] == 'TEST':
		print("Not sending email since this is a test.")
		return "Email not sent because are in TEST mode"
	""" Asynchronous task to send an email """
	msg = EmailMessage()
	msg['Subject'] = subject
	msg['From'] = sender_email
	msg['To'] = 'ahoag@princeton.edu' # to me while in DEV phase
	msg.set_content(body)                    
	smtp_server = smtp_connect()
	smtp_server.send_message(msg)
	return "Email sent!"