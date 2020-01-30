from flask import (render_template, request, redirect,
				   Blueprint, session, url_for, flash,
				   Markup, Request, Response)
from lightserv import db_lightsheet, db_admin
import pandas as pd
from lightserv.main.utils import logged_in, table_sorter, log_http_requests
from lightserv.main.forms import SpockConnectionTesterForm
from functools import partial, wraps

import datajoint as dj
import socket
import requests
import numpy as np

import logging
from time import sleep
import paramiko


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/main_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

main = Blueprint('main',__name__)

@main.route("/") 
@main.route("/welcome")
@logged_in
@log_http_requests
def welcome(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed welcome page")
	return render_template('main/welcome.html',)

@main.route("/gallery")
@logged_in
@log_http_requests
def gallery(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed gallery page")
	return render_template('main/gallery.html',)


@main.route("/FAQ")
@logged_in
@log_http_requests
def FAQ(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed FAQ")
	return render_template('main/FAQ.html')

@main.route("/spock_connection_test",methods=['GET','POST'])
@logged_in
@log_http_requests
def spock_connection_test(): 
	
	form = SpockConnectionTesterForm()
	if request.method == 'POST':
		hostname = 'spock.pni.princeton.edu'
		current_user = session['user']	
		port = 22
		client = paramiko.SSHClient()
		client.load_system_host_keys()
		client.set_missing_host_key_policy(paramiko.WarningPolicy)
		try:
			client.connect(hostname, port=port, username=current_user, allow_agent=False,look_for_keys=True)
			flash("Successfully connected to spock.","success")
		except:
			flash("Connection unsuccessful. Please refer to the FAQ and try again.","danger")
		finally:
			client.close()

	return render_template('main/spock_connection_test.html',form=form)

@main.route('/login', methods=['GET', 'POST'])
def login():
	next_url = request.args.get("next")
	logger.info("Logging you in first!")
	user_agent = request.user_agent
	logger.debug(user_agent)
	browser_name = user_agent.browser # e.g. chrome
	browser_version = user_agent.version # e.g. '78.0.3904.108'
	platform = user_agent.platform # e.g. linux
	
	if browser_name.lower() != 'chrome':
		logger.info(f"User is using browser {browser_name}")
		flash(f"Warning: parts of this web portal were not completely tested on your browser: {browser_name}. "
		 "Firefox users will experience some known issues. We recommend switching to Google Chrome for a better experience.",'danger')
	hostname = socket.gethostname()
	if hostname == 'braincogs00.pni.princeton.edu':
		username = request.headers['X-Remote-User']
	else:
		username = 'ahoag' # pragma: no cover - used to exclude this line from testing

	session['user'] = username
	''' If user not already in User() table, then add them '''
	all_usernames = db_lightsheet.User().fetch('username') 
	if username not in all_usernames:
		email = username + '@princeton.edu'
		user_dict = {'username':username,'princeton_email':email}
		db_lightsheet.User().insert1(user_dict)
		logger.info(f"Added {username} to User table in database")
	logstr = f'{username} logged in via "login()" route in lightserv.main.routes'
	insert_dict = {'browser_name':browser_name,'browser_version':browser_version,
				   'event':logstr,'platform':platform}
	db_admin.UserActionLog().insert1(insert_dict)
	return redirect(next_url)

@main.route("/pre_handoff_instructions")
@logged_in
@log_http_requests
def pre_handoff(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed pre_handoff route")
	return render_template('main/pre_handoff.html')

