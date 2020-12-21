from flask import (render_template, request, redirect,
				   Blueprint, session, url_for, flash,
				   Markup, Request, Response,abort)
from lightserv import db_lightsheet, db_admin
from lightserv.main.utils import (logged_in, table_sorter,
	 log_http_requests, logged_in_as_admin)
from lightserv.main.forms import SpockConnectionTesterForm, FeedbackForm
from lightserv.main.tables import RequestTable, AdminTable
from functools import partial, wraps

import datajoint as dj
import socket
import requests
import numpy as np

import logging
from time import sleep
import paramiko

# for testing ng viewer links
import os, time, json
import secrets
import redis
import progproxy as pp

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
	if hostname == 'docker_lightserv':
		username = request.headers['X-Remote-User']
	else:
		username = 'testuser' # pragma: no cover - used to exclude this line from testing

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

@main.route("/feedback_form/<username>/<request_name>",methods=['GET','POST'])
@logged_in
@log_http_requests
def feedback(username,request_name): 
	current_user = session['user']
	logger.info(f"{current_user} accessed feedback route")
	request_contents = db_lightsheet.Request() & {'username':username,'request_name':request_name}
	if len(request_contents) == 0:
		flash("No request with those parameters exists","danger")
		abort(404)
	# if current_user != username:
	# 	flash("You do not have permission to view the feedback form","danger")
	# 	logger.info(f"{current_user} accessed feedback form for {username}/{request_name} -"
	# 		         "they do not have permission and are being redirected")
	# 	return redirect(url_for('main.welcome'))
	feedback_table_contents = db_admin.RequestFeedback() & f'username="{username}"' & \
		f'request_name="{request_name}"'
	# if len(feedback_table_contents) > 0:
	# 	flash("Feedback already received for this request. Thank you.","warning")
	# 	logger.info(f"Feedback form for {username}/{request_name} "
	# 		         "already submitted.")
	# 	return redirect(url_for('main.welcome'))

	
	form = FeedbackForm()
	table = RequestTable(request_contents)

	if request.method == 'POST':
		logger.debug("POST request")
		if form.validate_on_submit():
			logger.debug("Form validated")
			feedback_insert_dict = {}
			feedback_insert_dict['username'] = username
			feedback_insert_dict['request_name'] = request_name
			feedback_insert_dict['clearing_rating'] = form.clearing_rating.data
			feedback_insert_dict['clearing_notes'] = form.clearing_notes.data
			feedback_insert_dict['imaging_rating'] = form.imaging_rating.data
			feedback_insert_dict['imaging_notes'] = form.imaging_notes.data
			feedback_insert_dict['processing_rating'] = form.processing_rating.data
			feedback_insert_dict['processing_notes'] = form.processing_notes.data
			feedback_insert_dict['other_notes'] = form.other_notes.data
			db_admin.RequestFeedback().insert1(feedback_insert_dict,skip_duplicates=True)
			flash("Feedback received. Thank you.","success")
			return redirect(url_for("main.welcome"))
		else:
			logger.debug("Form NOT validated") # pragma: no cover - used to exclude this line from testing
			logger.debug(form.errors) # pragma: no cover - used to exclude this line from testing
	return render_template('main/feedback_form.html',
		form=form,table=table)

@main.route("/admin") 
@logged_in_as_admin
@log_http_requests
def admin(): 
	""" Show last 20 entries to the user action log in an
	html table """
	current_user = session['user']
	user_action_contents = db_admin.UserActionLog() 
	""" First get last 20 """
	result=user_action_contents.fetch(limit=20,order_by='timestamp DESC',as_dict=True) 
	""" Then reverse order so they are in chronological order """
	# df_chron = df.iloc[::-1]
	admin_table = AdminTable(result[::-1])
	logger.info(f"{current_user} accessed admin page")
	return render_template('main/admin.html',admin_table=admin_table)

@main.route("/test_cel")
def test_cel(): 
	from . import tasks as maintasks
	from datetime import datetime, timedelta
	future_time = datetime.utcnow() + timedelta(seconds=1)
	print("sending hello task")
	maintasks.hello.apply_async(eta=future_time) 
	print("sent hello task")
	return "sent task"