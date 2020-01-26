from flask import url_for, session, request
import json
import tempfile,webbrowser
from lightserv import db_admin
from datetime import datetime

def test_GET_log_entry_admin_user(test_client,test_login):
	""" Ensure that when the user issues a GET request
	to the home page a log entry is inserted into the user action log table """
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)
	log_event = db_admin.UserActionLog().fetch()[-1]['event']
	assert log_event == '''ahoag GET request to route: "all_requests()" in lightserv.requests.routes'''
	# assert b'Background Info' in response.data and b"Clearing setup" not in response.data

def test_GET_log_entry_nonadmin_user(test_client,test_login_nonadmin):
	""" Ensure that when a user other than ahoag issues a GET request
	to the home page a log entry is inserted into the user action log table
	under their name. """
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)
	log_event = db_admin.UserActionLog().fetch()[-1]['event']
	assert log_event == '''lightserv-test GET request to route: "all_requests()" in lightserv.requests.routes'''

def test_POST_log_entry_admin_user(test_client,test_login,):
	""" Ensure that when the user issues a POST request
	to the new_request page a log entry is inserted into the user action log table
	with the correct log event """

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="Demo request",
			description="This is a demo request",
			species="mouse",number_of_samples=2,
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True,
		)	

	log_event = db_admin.UserActionLog().fetch()[-1]['event']
	assert log_event == '''ahoag POST request to route: "new_request()" in lightserv.requests.routes'''
	# assert b'Background Info' in response.data and b"Clearing setup" not in response.data

def test_POST_log_entry_nonadmin_user(test_client,test_login_nonadmin):
	""" Ensure that when a nonadmin user issues a POST request
	to the new_request page a log entry is inserted into the user action log table
	with the correct log event """

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="lightserv-test@princeton.edu",
			request_name="Demo request",
			description="This is a demo request",
			species="mouse",number_of_samples=2,
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True,
		)	

	log_event = db_admin.UserActionLog().fetch()[-1]['event']
	assert log_event == '''lightserv-test POST request to route: "new_request()" in lightserv.requests.routes'''
