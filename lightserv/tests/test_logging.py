from flask import url_for, session, request
import json
import tempfile,webbrowser
from lightserv import db_lightsheet
from datetime import datetime

def test_GET_log_entry(test_client,test_login):
	""" Ensure that when the user issues a GET request
	to the home page a log entry is inserted into the user action log table """
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)
	log_event = db_lightsheet.UserActionLog().fetch()[-1]['event']
	assert log_event == '''ahoag GET request to route: "all_requests()" in lightserv.requests.routes'''
	# assert b'Background Info' in response.data and b"Clearing setup" not in response.data

def test_GET_log_entry_nonadmin_user(test_client,test_login_nonadmin):
	""" Ensure that when a user other than ahoag issues a GET request
	to the home page a log entry is inserted into the user action log table
	under their name. """
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)
	log_event = db_lightsheet.UserActionLog().fetch()[-1]['event']
	assert log_event == '''ms81 GET request to route: "all_requests()" in lightserv.requests.routes'''