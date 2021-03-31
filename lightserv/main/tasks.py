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
logger.propagate = False

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/main_tasks.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

def connect_to_spock():
	hostname = 'spock.pni.princeton.edu'
	
	spock_username = current_app.config['SPOCK_LSADMIN_USERNAME']
	port = 22

	client = paramiko.SSHClient()
	client.load_system_host_keys()
	client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
	client.connect(hostname, port=port, username=spock_username, allow_agent=False,look_for_keys=True)
	return client

@cel.task()
def send_email(subject,body,sender_email='lightservhelper@gmail.com',recipients=['ahoag@princeton.edu']):
	""" Send an automated email to one or more email addresses.
	---INPUT---
	subject        string
	body		   string
	sender_email   email string
	recipients     list of email address strings
	"""
	if os.environ['FLASK_MODE'] == 'DEV':
		logger.debug("Sending email only to ahoag@princeton.edu since we are in DEV mode")
		recipients = ['ahoag@princeton.edu']
	""" Asynchronous task to send an email """
	msg = EmailMessage()
	msg['Subject'] = subject
	msg['From'] = sender_email
	msg['To'] = ','.join(recipients) 
	msg.set_content(body)                    
	smtp_server = smtp_connect()
	smtp_server.send_message(msg)
	return "Email sent!"

@cel.task()
def send_admin_email(subject,body,sender_email='lightservhelper@gmail.com'):
	""" Send an automated email to the admins (see config.py for admin list)
	---INPUT---
	subject        string
	body		   string
	sender_email   email string
	"""

	""" Asynchronous task to send an email """
	msg = EmailMessage()
	msg['Subject'] = subject
	msg['From'] = sender_email
	admin_usernames = current_app.config['ADMINS_TO_EMAIL']
	admins_to_email = [s+'@princeton.edu' for s in admin_usernames]
	msg['To'] = ','.join(admins_to_email)
	msg.set_content(body)                    
	smtp_server = smtp_connect()
	smtp_server.send_message(msg)
	return "Email sent!"

@cel.task()
def hello():
	print("in celery task")
	return "hello world"