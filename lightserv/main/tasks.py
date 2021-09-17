from flask import (render_template, request, redirect,
				   Blueprint, session, url_for, flash,
				   Markup, Request, Response,jsonify,
                   current_app)
from lightserv import db_lightsheet, db_admin, db_spockadmin, cel, smtp_connect
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
	logger.info("in celery task")
	return "hello world"

@cel.task()
def check_lightsheetdata_storage():
	logger.info("Checking LightSheetData available storage capacity")
	import subprocess
	# Get the available storage using the "df -BG" command which reports the space always in GB so it is easy to parse
	result = subprocess.run('df -BG | grep LightSheetData | grep cup',shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
	error = False
	try:
		size_str = result.split()[1]
		size_GB = float(size_str[:-1])
		size_TB = round(size_GB/1000.,3)
		avail_str = result.split()[3]
		avail_GB = int(avail_str[:-1])
		avail_TB = round(avail_GB/1000.,3)
		error=False
	except:
		error = True 
	if error == True:
		logger.debug("There was an error")
		subject = "Lightserv: (ERROR) daily LightSheetData health check"
		body = "There was an error checking the storage capacity of LightSheetData on bucket. "
	else:
		if avail_GB < 5000:
			subject = "Lightserv: WARNING! LightSheetData almost full"
			body = (f"LightSheetData has {avail_GB} GB remaining. This is less than the 5 TB threshold that you set."
					 " LightSheetData could get full very soon. Free up space before disaster strikes. ")
		else:
			subject = "Lightserv: (ALL CLEAR) LightSheetData has plenty of free space"
			body = (f"LightSheetData has {avail_GB} GB remaining. This is above the 5 TB threshold that you set."
					 " No action is needed at this time. ")
		# Store row in datajoint table
		now = datetime.now()
		timestamp = now.strftime('%Y-%m-%d') + ' 08:30:00'
		insert_dict = dict(timestamp=timestamp,
			size_tb=size_TB,
			avail_tb=avail_TB)
		logger.debug("Inserting into BucketStorage() table:")
		logger.debug(insert_dict)
		db_spockadmin.BucketStorage().insert1(insert_dict,skip_duplicates=True)
	master_admin_netids = current_app.config['MASTER_ADMINS']
	recipients = [x + "@princeton.edu" for x in master_admin_netids]
	send_email.delay(subject=subject,
		body=body,recipients=recipients)
	return "Checked LightSheetData storage capacity"