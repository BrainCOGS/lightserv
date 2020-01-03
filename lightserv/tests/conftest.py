""" conftest.py 
pytest sees this file and loads all 
fixtures into memory so that they 
don't need to be imported for the 
tests in other test modules.
This file must have the name conftest.py
"""

import os, sys
if os.environ.get('FLASK_MODE') != 'TEST':
	raise KeyError("Must set environmental variable FLASK_MODE=TEST")
from flask import url_for,request
from lightserv import create_app, config
import secrets
import pytest
from flask import url_for
import datajoint as dj
user_agent_str = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36'

@pytest.fixture(scope='session') 
def test_client():
	""" Create the application and the test client.

	The way a fixture works is whaterver is yielded
	by this function will be passed to the tests that 
	take the name of the fixture function as an argument.

	We use scope='module' because we only want the test_client
	to last for tests in a single module. If we use scope='session',
	then the state of the test client will be altered by one test module,
	and then that is the state of the client when the next test module
	is executed. This will mean the test order will matter which is a 
	bad way to do things. It does mean we will have to reload the
	test client in each module in which we use it, so it is slightly slower this way."" 
	"""
	print('----------Setup test client----------')
	app = create_app(config_class=config.TestConfig)
	# testing_client = app.test_client()
	testing_client = app.test_client()

	testing_client.environ_base["HTTP_USER_AGENT"] = user_agent_str
	testing_client.environ_base["HTTP_X_REMOTE_USER"] = 'ahoag'

	ctx = app.test_request_context() # makes it so I can use the url_for() function in the tests
	ctx.push()
	yield testing_client # this is where the testing happens
	print('-------Teardown test client--------')
	ctx.pop()

@pytest.fixture(scope='function')
def test_login(test_client):
	""" Log the user in. Requires a test_client fixture to do this. """
	print('----------Setup login as ahoag response----------')
	with test_client.session_transaction() as sess:
		sess['user'] = 'ahoag'

	yield sess
	print('----------Teardown login as ahoag response----------')
	pass

@pytest.fixture(scope='function')
def test_login_ll3(test_client):
	""" Log Laura in. Requires a test_client fixture to do this. """
	print('----------Setup login_ll3 response----------')
	with test_client.session_transaction() as sess:
		sess['user'] = 'll3'

	yield sess
	print('----------Teardown login_ll3 response----------')
	pass

@pytest.fixture(scope='function')
def test_login_zmd(test_client):
	""" Log Zahra in. Requires a test_client fixture to do this. """
	print('----------Setup login_zmd response----------')
	with test_client.session_transaction() as sess:
		sess['user'] = 'zmd'

	yield sess
	print('----------Teardown login_zmd response----------')
	pass

@pytest.fixture(scope='function')
def test_login_nonadmin(test_client):
	""" Log the user in. Requires a test_client fixture to do this. """
	print('----------Setup login_nonadmin response----------')
	with test_client.session_transaction() as sess:
		sess['user'] = 'ms81'

	yield sess
	print('----------Teardown login_nonadmin response----------')
	pass	

@pytest.fixture(scope='function') 
def test_delete_request_db_contents(test_client):
	""" A fixture to simply delete the db contents 
	(starting at Request() as the root - does not delete User() contents)
	after each test runs
	"""
	print('----------Setup test_delete_request_db_contents fixture ----------')

	from lightserv import db_lightsheet

	yield # this is where the test is run
	print('-------Teardown test_delete_request_db_contents fixture --------')
	db_lightsheet.Request().delete()	

@pytest.fixture(scope='function') 
def test_single_request_ahoag(test_client,test_login,test_delete_request_db_contents):
	""" Submits a new request as 'ahoag' that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_single_request_ahoag fixture ----------')
	from lightserv import db_lightsheet
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_single_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_two_requests_ahoag(test_client,test_login,test_delete_request_db_contents):
	""" Submits two new requests as 'ahoag' that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_two_requests_ahoag fixture ----------')
	from lightserv import db_lightsheet
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response1 = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin request 1",
			'description':"This is a first demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	response2 = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin request 2",
			'description':"This is a second demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)

	yield test_client # this is where the testing happens
	print('-------Teardown test_two_requests_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_single_request_nonadmin(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits a new request as 'ms81' (a nonadmin) that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_single_request_nonadmin fixture ----------')
	from lightserv import db_lightsheet
	with test_client.session_transaction() as sess:
		current_user = sess['user']
		print(f"Current user is {current_user}")
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Tank/Brody",'correspondence_email':"ms81@princeton.edu",
			'request_name':"Nonadmin request",
			'description':"This is a request by ms81, a non admin",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_single_request_nonadmin fixture --------')
	