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
from lightserv import (create_app, config, db_admin,
	db_lightsheet,db_microscope,db_subject, db_spockadmin)
import secrets
import pytest
from flask import url_for
import datajoint as dj
from datetime import datetime, date

user_agent_str = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36'
user_agent_str_firefox = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:72.0) Gecko/20100101 Firefox/72.0'

""" Fixtures for different test clients (different browsers) """

@pytest.fixture(scope='module') 
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
	""" Drop all schemas """
	db_admin.schema.drop(force=True)
	db_spockadmin.schema.drop(force=True)
	db_lightsheet.schema.drop(force=True)
	db_microscope.schema.drop(force=True)
	db_subject.schema.drop(force=True)

	ctx.pop()

@pytest.fixture(scope='function') 
def test_client_firefox():
	""" Create the application and the test firefox client.

	We use scope='function' because we only want this test client
	to last for tests in a single function. If we use scope='session'
	or scope='module' then the context set up in this fixture tends to collide
	with the test_client context that I use module wide. I only need to use this 
	fixture for a few tests so we don't lose much in performance by making this 
	restriction to scope='function'.
	"""
	print('----------Setup test firefox client----------')
	app = create_app(config_class=config.TestConfig)
	# testing_client = app.test_client()
	testing_client = app.test_client()

	testing_client.environ_base["HTTP_USER_AGENT"] = user_agent_str_firefox
	testing_client.environ_base["HTTP_X_REMOTE_USER"] = 'ahoag'

	ctx = app.test_request_context() # makes it so I can use the url_for() function in the tests
	ctx.push()
	yield testing_client # this is where the testing happens
	print('-------Teardown test firefox client--------')
	ctx.pop()

""" Fixtures for logging in as different users (admins, non admins) """

@pytest.fixture(scope='function')
def test_login(test_client):

	""" Log ahoag in. Requires a test_client fixture to do this. """
	print('----------Setup login as ahoag ---------')
	username = 'ahoag'
	with test_client.session_transaction() as sess:
		sess['user'] = username
	all_usernames = db_lightsheet.User().fetch('username') 
	if username not in all_usernames:
		email = username + '@princeton.edu'
		user_dict = {'username':username,'princeton_email':email}
		db_lightsheet.User().insert1(user_dict)
	yield sess
	print('----------Teardown login as ahoag ----------')
	pass

@pytest.fixture(scope='function')
def test_login_ll3(test_client):
	""" Log Laura in. Requires a test_client fixture to do this. """
	print('----------Setup login_ll3 response----------')
	username = 'll3'
	with test_client.session_transaction() as sess:
		sess['user'] = username
	all_usernames = db_lightsheet.User().fetch('username') 
	if username not in all_usernames:
		email = username + '@princeton.edu'
		user_dict = {'username':username,'princeton_email':email}
		db_lightsheet.User().insert1(user_dict)
	yield sess
	print('----------Teardown login_ll3 response----------')
	pass

@pytest.fixture(scope='function')
def test_login_zmd(test_client):
	""" Log Zahra in. Requires a test_client fixture to do this. """
	print('----------Setup login_zmd response----------')
	username = 'zmd'
	with test_client.session_transaction() as sess:
		sess['user'] = username
	all_usernames = db_lightsheet.User().fetch('username') 
	if username not in all_usernames:
		email = username + '@princeton.edu'
		user_dict = {'username':username,'princeton_email':email}
		db_lightsheet.User().insert1(user_dict)
	yield sess
	print('----------Teardown login_zmd response----------')
	pass

@pytest.fixture(scope='function')
def test_login_nonadmin(test_client):
	""" Log the user in. Requires a test_client fixture to do this. """
	print('----------Setup login_nonadmin response----------')
	username = 'lightserv-test'
	with test_client.session_transaction() as sess:
		sess['user'] = username
	all_usernames = db_lightsheet.User().fetch('username') 
	if username not in all_usernames:
		email = username + '@princeton.edu'
		user_dict = {'username':username,'princeton_email':email}
		db_lightsheet.User().insert1(user_dict)
	yield sess
	print('----------Teardown login_nonadmin response----------')
	pass	

@pytest.fixture(scope='function')
def test_login_newuser(test_client):
	""" Log a completely new user in. Requires a test_client fixture to do this.
	This fixture is useful for testing out failure modes of
	things that the user manually needs to set up, like the 
	the spock ssh connection """
	print('----------Setup login_nonadmin response----------')
	username = 'foreignnetid'
	with test_client.session_transaction() as sess:
		sess['user'] = username
	all_usernames = db_lightsheet.User().fetch('username') 
	if username not in all_usernames:
		email = username + '@princeton.edu'
		user_dict = {'username':username,'princeton_email':email}
		db_lightsheet.User().insert1(user_dict)
	yield sess
	print('----------Teardown login_nonadmin response----------')
	pass	

################################
""" General purpose fixtures """
################################

@pytest.fixture(scope='function') 
def test_delete_request_db_contents(test_client):
	""" A fixture to simply delete the db contents 
	(starting at Request() as the root - does not delete User() contents)
	after each test runs
	"""
	print('----------Setup test_delete_request_db_contents fixture ----------')


	yield # this is where the test is run
	print('-------Teardown test_delete_request_db_contents fixture --------')
	db_lightsheet.Request().delete()
	# db_admin.UserActionLog().delete()	
	# db_admin.LightsheetPipelineSpockJob().delete()	

""" Fixtures for requests """

@pytest.fixture(scope='function') 
def test_single_sample_request_ahoag(test_client,test_login,test_delete_request_db_contents):
	""" Submits a new request as 'ahoag' with a single sample that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_single_request_ahoag fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-notes_for_imager':'Image horizontally please!',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_single_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_single_sample_request_4x_ahoag(test_client,test_login,test_delete_request_db_contents):
	""" Submits a new request as 'ahoag' with a single sample requesting 4x resolution
	that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_single_request_ahoag fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_4x_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'4x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_single_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_request_4x_nonadmin(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits a new request as 'lightserv-user' with a single sample requesting 4x resolution
	that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_request_4x_nonadmin fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"test2",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'test2-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'4x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'4x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'647',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-generic_imaging':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_request_4x_nonadmin fixture --------')

@pytest.fixture(scope='function') 
def test_multichannel_request_ahoag(test_client,test_login,test_delete_request_db_contents):
	""" Submits a new request as 'ahoag' with a single sample 
	requesting two different imaging channels
	that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_multichannel_request_ahoag fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_multichannel_request",
			'description':"This is a multichannel request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-channel_name':'555',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-cell_detection':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_multichannel_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_two_requests_ahoag(test_client,test_login,test_delete_request_db_contents):
	""" Submits two new requests as 'ahoag' that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_two_requests_ahoag fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response1 = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request_1",
			'description':"This is a first demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	response2 = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request_2",
			'description':"This is a second demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)

	yield test_client # this is where the testing happens
	print('-------Teardown test_two_requests_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_request_all_mouse_clearing_protocols_ahoag(test_client,test_login,test_delete_request_db_contents):
	""" Submits a new request as 'ahoag' with a sample for each of the 4 
	clearing protocols that can be used for mice.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_single_request_ahoag fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"ahoag@princeton.edu",
			'request_name':"All_mouse_clearing_protocol_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':4,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'clearing_samples-1-clearing_protocol':'iDISCO+_immuno',
			'clearing_samples-1-antibody1':'test antibody for immunostaining',
			'clearing_samples-1-sample_name':'sample-002',
			'imaging_samples-1-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-1-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-1-image_resolution_forsetup':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-channel_forms-0-registration':True,
			'clearing_samples-2-clearing_protocol':'uDISCO',
			'clearing_samples-2-sample_name':'sample-003',
			'imaging_samples-2-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-2-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-2-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-2-image_resolution_forsetup':'1.3x',
			'imaging_samples-2-image_resolution_forms-0-channel_forms-0-registration':True,
			'clearing_samples-3-clearing_protocol':'iDISCO_EdU',
			'clearing_samples-3-sample_name':'sample-004',
			'imaging_samples-3-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-3-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-3-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-3-image_resolution_forsetup':'1.3x',
			'imaging_samples-3-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_single_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_single_sample_request_nonadmin(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits a new request as 'lightserv-test' (a nonadmin) that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_single_request_nonadmin fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
		print(f"Current user is {current_user}")
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Tank/Brody",'correspondence_email':"lightserv-test@princeton.edu",
			'request_name':"nonadmin_request",
			'description':"This is a request by lightserv-test, a non admin",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_single_request_nonadmin fixture --------')
	
@pytest.fixture(scope='function') 
def test_rat_request_nonadmin(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits a new request as Manuel ('lightserv-test', a nonadmin) for species='rat' that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_single_request_nonadmin fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
		print(f"Current user is {current_user}")
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Tank/Brody",'correspondence_email':"lightserv-test@princeton.edu",
			'request_name':"Nonadmin_rat_request",
			'description':"This is a request for a rat by lightserv-test, a non admin",
			'species':"rat",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-generic_imaging':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_single_request_nonadmin fixture --------')
	
@pytest.fixture(scope='function') 
def test_request_generic_imaging_nonadmin(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits a new request as 'lightserv-test' (a nonadmin) that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_single_request_nonadmin fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
		print(f"Current user is {current_user}")
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Witten",'correspondence_email':"lightserv-test@princeton.edu",
			'request_name':"nonadmin_request",
			'description':"This is a request by lightserv-test, a non admin",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'coronal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'555',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-generic_imaging':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_single_request_nonadmin fixture --------')

@pytest.fixture(scope='function') 
def test_self_clearing_and_imaging_request(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits a new request as 'lightserv-test' (a nonadmin) that can be used for various tests.
	In this request, the user sets themselves as the clearer and imager

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_self_clearing_and_imaging_request fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
		print(f"Current user is {current_user}")
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Tank/Brody",'correspondence_email':"lightserv-test@princeton.edu",
			'request_name':"self_clearing_and_imaging_request",
			'description':"This is a request by lightserv-test, a non admin",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'self_clearing':True,
			'self_imaging':True,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_self_clearing_and_imaging_request fixture --------')
	
@pytest.fixture(scope='function') 
def test_archival_request_nonadmin(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits an archival request with a single sample that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_single_request_ahoag fixture ----------')
	request_insert_dict = {'username': 'lightserv-test', 'request_name': 'test_archival_request',
	 'requested_by': 'lightserv-test', 'date_submitted': '2019-02-26',
	  'time_submitted': '12:55:22', 'labname': 'Wang', 'subject_fullname': '',
	   'correspondence_email': 'lightserv-test@princeton.edu',
	    'description': 'Image c-fos in whole brains at 1.3x.',
	     'species': 'mouse', 'number_of_samples': 1, 'is_archival': True}
	clearing_batch_insert_dict = {
	'username': 'lightserv-test', 'request_name': 'test_archival_request', 'clearing_protocol': 'iDISCO abbreviated clearing',
	'link_to_clearing_spreadsheet': 'https://docs.google.com/spreadsheets/d/1A83HVyy1bEhctqArwt4EiT637M8wBxTFodobbt1jrXI/edit#gid=895577002',
	'antibody1': '', 'antibody2': '',
	 'clearing_batch_number': 1, 'clearing_progress': 'complete', 'number_in_batch': 1, 'notes_for_clearer': ''}
	sample_insert_dict = {
	'username': 'lightserv-test', 'request_name': 'test_archival_request', 'clearing_protocol': 'iDISCO abbreviated clearing',
	 'antibody1': '', 'antibody2': '', 'clearing_batch_number': 1, 'sample_name': 'sample-001'}
	imaging_request_insert_dict = {
	'username': 'lightserv-test', 'request_name': 'test_archival_request', 'imaging_request_number': 1,
	 'imaging_progress': 'complete', 'imaging_request_date_submitted': '2019-02-26',
	  'imaging_request_time_submitted': '12:55:22', 'sample_name': 'sample-001'}
	imaging_resolution_request_insert_dict = {
	'username': 'lightserv-test', 'request_name': 'test_archival_request', 'imaging_request_number': 1,
	'notes_for_imager': '', 'notes_from_imaging': 'Processed files are here: /somewhere/on/bucket',
	'sample_name': 'sample-001', 'image_resolution': '1.3x'}
	processing_request_insert_dict= {
	'username': 'lightserv-test', 'request_name': 'test_archival_request', 'imaging_request_number': 1,
	'processing_request_number': 1, 'processor': 'lightserv-test', 'processing_request_date_submitted': '2019-02-26',
	'processing_request_time_submitted': '12:55:22', 'processing_progress': 'complete', 'sample_name': 'sample-001'}
	db_lightsheet.Request.insert1(request_insert_dict)
	db_lightsheet.Request.ClearingBatch.insert1(clearing_batch_insert_dict)
	db_lightsheet.Request.Sample.insert1(sample_insert_dict)
	db_lightsheet.Request.ImagingRequest.insert1(imaging_request_insert_dict)
	db_lightsheet.Request.ImagingResolutionRequest.insert1(imaging_resolution_request_insert_dict)
	db_lightsheet.Request.ProcessingRequest.insert1(processing_request_insert_dict)

	yield test_client # this is where the testing happens
	print('-------Teardown test_single_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_experimental_clearing_request_nonadmin(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits a new request as 'ahoag' with a single sample that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_single_request_ahoag fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Tank/Brody",'correspondence_email':"lightserv-test@princeton.edu",
			'request_name':"nonadmin_experimental_request",
			'description':"This is a request by lightserv-test, a non admin",
			'species':"rat",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'experimental',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-generic_imaging':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_single_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_both_lightsheets_nonadmin_request(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits a new request as 'lightserv-test' (a nonadmin) that can be used for various tests.
	This request has raw data on bucket in the correct folder with both left and right lightsheets
	that can be used for testing out the imaging routes.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_both_lightsheets_nonadmin_request fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
		print(f"Current user is {current_user}")
	today = date.today()
	today_proper_format = today.strftime('%Y-%m-%d')
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"two_sheets",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':test_login_nonadmin['user'],
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'two_sheets-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-notes_for_imager':'make it good!',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'647',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_both_lightsheets_nonadmin_request fixture --------')

@pytest.fixture(scope='function') 
def test_two_channels_request_nonadmin(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits a new request as 'lightserv-test' (a nonadmin) that can be used for various tests.
	This request has raw data on bucket for two different channels
	but it is NOT multi-channel imaging, i.e. the two channels are in two different rawdata subfolders

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_two_channels_nonadmin_request fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
		print(f"Current user is {current_user}")
	today = date.today()
	today_proper_format = today.strftime('%Y-%m-%d')
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"two_channels",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':test_login_nonadmin['user'],
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'two_channels-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-cell_detection':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-channel_name':'647',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_two_channels_nonadmin_request fixture --------')

@pytest.fixture(scope='function') 
def test_4x_multitile_request_nonadmin(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits a new request as 'lightserv-user' with a single sample requesting 4x resolution
	that can be used for various tests.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_request_4x_nonadmin fixture ----------')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"4x_647_kelly",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'4x_647_kelly-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'4x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'4x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'647',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-generic_imaging':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_request_4x_nonadmin fixture --------')

""" Fixtures for clearing """

@pytest.fixture(scope='function') 
def test_cleared_request_ahoag(test_client,
	test_single_sample_request_ahoag,test_delete_request_db_contents):
	""" Clears the single request by 'ahoag' (with clearer='ahoag') 

	Uses test_single_sample_request_ahoag request so that a request is in the db
	when it comes time to do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	print('----------Setup test_cleared_request_ahoag fixture ----------')
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ahoag",
			request_name="admin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_cleared_request_4x_ahoag(test_client,
	test_single_sample_request_4x_ahoag,test_delete_request_db_contents):
	""" Clears the single request by 'ahoag' (with clearer='ahoag')
	where 4x resolution was requested 

	Uses test_single_sample_request_ahoag request so that a request is in the db
	when it comes time to do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	print('----------Setup test_cleared_request_ahoag fixture ----------')
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ahoag",
			request_name="Admin_4x_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_cleared_request_4x_nonadmin(test_client,
	test_request_4x_nonadmin,test_login_ll3,test_delete_request_db_contents):
	""" Clears the single request by 'lightserv-test' (with clearer='ahoag')
	where 4x resolution was requested 

	Uses test_single_sample_request_ahoag request so that a request is in the db
	when it comes time to do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	print('----------Setup test_cleared_request_4x_nonadmin fixture ----------')
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="test2",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_4x_nonadmin fixture --------')

@pytest.fixture(scope='function') 
def test_cleared_multichannel_request_ahoag(test_client,
	test_multichannel_request_ahoag,test_delete_request_db_contents):
	""" Clears the multichannel request by 'ahoag' (with clearer='ahoag') 

	Uses test_single_sample_request_ahoag request so that a request is in the db
	when it comes time to do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	print('----------Setup test_cleared_multichannel_request_ahoag fixture ----------')
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ahoag",
			request_name="admin_multichannel_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_multichannel_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_cleared_request_nonadmin(test_client,test_single_sample_request_nonadmin,
	test_login_ll3,test_delete_request_db_contents):
	""" Clears the single request by 'lightserv-test' (with clearer='ll3') 

	Uses test_single_sample_request_nonadmin request so that a request is in the db
	when it comes time to do the clearing
	
	Runs test_login_ll3 next so that 'll3' gets logged in and can do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	print('----------Setup test_cleared_request_nonadmin fixture ----------')
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="nonadmin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_nonadmin fixture --------')

@pytest.fixture(scope='function') 
def test_cleared_request_generic_imaging_nonadmin(test_client,test_request_generic_imaging_nonadmin,
	test_login_ll3,test_delete_request_db_contents):
	""" Clears the single request by 'lightserv-test' (with clearer='ll3') 

	Uses test_single_sample_request_nonadmin request so that a request is in the db
	when it comes time to do the clearing
	
	Runs test_login_ll3 next so that 'll3' gets logged in and can do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	print('----------Setup test_cleared_request_ahoag fixture ----------')
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="nonadmin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_ahoag fixture --------')	

@pytest.fixture(scope='function') 
def test_cleared_all_mouse_clearing_protocols_ahoag(test_client,
	test_request_all_mouse_clearing_protocols_ahoag,test_delete_request_db_contents):
	""" Clears all mouse requests by 'ahoag' (with clearer='ahoag') 

	Uses test_request_all_mouse_clearing_protocols_ahoag so that all
	requests are in the db
	when it comes time to do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	print('----------Setup test_cleared_request_ahoag fixture ----------')
	now = datetime.now()
	data_abbreviated_clearing = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ahoag",
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data_abbreviated_clearing,
		follow_redirects=True,
		)	

	data_idiscoplus_clearing = dict(time_dehydr_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',
			username="ahoag",
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO+_immuno",
			antibody1="test antibody for immunostaining",antibody2="",
			clearing_batch_number=2),
		data=data_idiscoplus_clearing,
		follow_redirects=True,
		)	

	data_udisco_clearing = dict(time_dehydr_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ahoag",
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="uDISCO",
			antibody1="",antibody2="",
			clearing_batch_number=3),
		data = data_udisco_clearing,
		follow_redirects=True,
		)	

	data_idisco_edu_clearing = dict(time_dehydr_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ahoag",
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO_EdU",
			antibody1="",antibody2="",
			clearing_batch_number=4),
		data = data_idisco_edu_clearing,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_cleared_rat_request(test_client,
	test_rat_request_nonadmin,test_login_ll3,test_delete_request_db_contents):
	""" Clears the single rat request by Manuel (lightserv-test, a nonadmin) (with clearer='ll3') 

	"""
	print('----------Setup test_cleared_request_ahoag fixture ----------')
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		pbs_wash1_notes='some rat notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="Nonadmin_rat_request",
			clearing_protocol="iDISCO abbreviated clearing (rat)",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_ahoag fixture --------')

@pytest.fixture(scope='function') 
def test_self_cleared_request_nonadmin(test_client,test_self_clearing_and_imaging_request):
	""" Clears the self-clearing single request by 'lightserv-test'
	with clearer='lightserv-test'

	"""
	print('----------test_self_cleared_request_nonadmin fixture ----------')
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="self_clearing_and_imaging_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_self_cleared_request_nonadmin fixture --------')

@pytest.fixture(scope='function') 
def test_cleared_request_both_lightsheets_nonadmin(test_client,test_both_lightsheets_nonadmin_request,
	test_login_ll3,test_delete_request_db_contents):
	""" Clears the single request by 'lightserv-test' (with clearer='ll3') 
	where both left and right light sheets are going to be imaged

	Runs test_login_ll3 next so that 'll3' gets logged in and can do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	print('----------Setup test_cleared_request_nonadmin fixture ----------')
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="two_sheets",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_nonadmin fixture --------')

@pytest.fixture(scope='function') 
def test_cleared_request_two_channels_nonadmin(test_client,test_two_channels_request_nonadmin,
	test_login_ll3,test_delete_request_db_contents):
	""" Clears the single request by 'lightserv-test' (with clearer='ll3') 
	where two channels (NOT multi-channel imaging though) are going to be imaged

	Runs test_login_ll3 next so that 'll3' gets logged in and can do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	print('----------Setup test_cleared_request_nonadmin fixture ----------')
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="two_channels",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_nonadmin fixture --------')

@pytest.fixture(scope='function') 
def test_cleared_request_4x_multitile_nonadmin(test_client,test_4x_multitile_request_nonadmin,
	test_login_ll3,test_delete_request_db_contents):
	""" Clears the single request by 'lightserv-test' (with clearer='ll3') 
	where two channels (NOT multi-channel imaging though) are going to be imaged

	Runs test_login_ll3 next so that 'll3' gets logged in and can do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	print('----------Setup test_cleared_request_nonadmin fixture ----------')
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="4x_647_kelly",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_nonadmin fixture --------')


""" Fixtures for imaging  """

@pytest.fixture(scope='function') 
def test_imaged_request_ahoag(test_client,test_cleared_request_ahoag,
	test_login_zmd,test_delete_request_db_contents):
	""" Images the cleared request by 'ahoag' (clearer='ahoag')
	with imager='zmd' """
	print('----------Setup test_imaged_request_ahoag fixture ----------')

	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)

	yield test_client
	print('----------Teardown test_imaged_request_ahoag fixture ----------')

@pytest.fixture(scope='function') 
def test_imaged_request_nonadmin(test_client,test_cleared_request_nonadmin,
	test_delete_request_db_contents,test_login_zmd):
	""" Images the cleared request by 'lightserv-test' (clearer='ll3')
	with imager='zmd' """

	print('----------Setup test_imaged_request_nonadmin fixture ----------')
	with test_client.session_transaction() as sess:
		sess['user'] = 'zmd'
	# print(db_lightsheet.Request.Sample())
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	yield test_client
	print('----------Teardown test_imaged_request_ahoag fixture ----------')

@pytest.fixture(scope='function') 
def test_imaged_request_generic_imaging_nonadmin(test_client,test_cleared_request_generic_imaging_nonadmin,
	test_delete_request_db_contents,test_login_zmd):
	""" Images the cleared request by 'lightserv-test' (clearer='ll3')
	with imager='zmd' """

	print('----------Setup test_imaged_request_nonadmin fixture ----------')
	with test_client.session_transaction() as sess:
		sess['user'] = 'zmd'
	# print(db_lightsheet.Request.Sample())
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'555',
		'image_resolution_forms-0-channel_forms-0-image_orientation':'sagittal',
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test555',
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	yield test_client
	print('----------Teardown test_imaged_request_ahoag fixture ----------')

@pytest.fixture(scope='function') 
def test_imaged_4x_request_nonadmin(test_client,test_cleared_request_4x_nonadmin,
	test_delete_request_db_contents,test_login_zmd):
	""" Images the cleared 4x request by 'lightserv-test' (clearer='ll3')
	with imager='zmd' """

	print('----------Setup test_4x_imaging_request_nonadmin fixture ----------')
	with test_client.session_transaction() as sess:
		sess['user'] = 'zmd'
	# print(db_lightsheet.Request.Sample())
	data = {
		'image_resolution_forms-0-image_resolution':'4x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'647',
		'image_resolution_forms-0-channel_forms-0-image_orientation':'sagittal',
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'2x3',
		'image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.15,
		'image_resolution_forms-0-channel_forms-0-z_step':2,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':682,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test647'
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='test2',sample_name='test2-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	yield test_client
	print('----------Teardown test_4x_imaging_request_nonadmin fixture ----------')

@pytest.fixture(scope='function') 
def imaged_request_lightserv_test(test_client,test_cleared_request_nonadmin,
	test_delete_request_db_contents,test_login_zmd):
	""" Images the cleared request by 'lightserv-test' (clearer='ll3')
	with imager='zmd' """

	print('----------Setup test_imaged_request_nonadmin fixture ----------')
	with test_client.session_transaction() as sess:
		sess['user'] = 'zmd'
	# print(db_lightsheet.Request.Sample())
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	yield test_client
	print('----------Teardown test_imaged_request_ahoag fixture ----------')

@pytest.fixture(scope='function') 
def test_imaged_multichannel_request_ahoag(test_client,test_cleared_multichannel_request_ahoag,
	test_login_zmd,test_delete_request_db_contents):
	""" Images the multi-channel cleared request by 'ahoag' (clearer='ahoag')
	with imager='zmd' """

	print('----------Setup test_imaged_request_ahoag fixture ----------')

	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':5,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'image_resolution_forms-0-channel_forms-1-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-1-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-1-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-1-z_step':15,
		'image_resolution_forms-0-channel_forms-1-number_of_z_planes':657,
		'image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test555',
		'submit':True
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_multichannel_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)

	yield test_client
	print('----------Teardown test_imaged_request_ahoag fixture ----------')

""" Fixtures for follow-up imaging and processing requests """

@pytest.fixture(scope='function') 
def test_new_imaging_request_ahoag(test_client,test_single_sample_request_ahoag):
	""" A fixture to make a new imaging request for an existing request.
	A new imaging request by default creates a new processing request. 

	Uses test_single_sample_request_ahoag to make a single request with a single 
	sample for setup

	"""
	print('-------Setup test_new_imaging_request fixture --------')
	response = test_client.post(url_for('imaging.new_imaging_request',
			username='ahoag',request_name='admin_request',
			sample_name='sample-001'),
		data={
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-atlas_name':'allen_2017',
			'image_resolution_forms-0-final_orientation':'sagittal',
			'image_resolution_forsetup':'1.3x',
			'image_resolution_forms-0-channels-0-registration':True,
			'submit':True
		},content_type='multipart/form-data',
		follow_redirects=True
		)
	yield test_client # this is where the testing happens
	print('-------Teardown test_new_imaging_request fixture --------')

@pytest.fixture(scope='function') 
def test_new_processing_request_ahoag(test_client,test_single_sample_request_ahoag):
	""" A fixture to make a request with two processing requests 
	for a single sample with a single imaging request. 

	Uses test_single_sample_request_ahoag to make a single request with a single 
	sample for setup

	"""
	print('-------Setup test_new_processing_request fixture --------')
	response = test_client.post(url_for('processing.new_processing_request',
			username='ahoag',request_name='admin_request',
			sample_name='sample-001',imaging_request_number=1),
		data={
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-atlas_name':'princeton_mouse_atlas',
			'submit':True
		},content_type='multipart/form-data',
		follow_redirects=True
		)
	yield test_client # this is where the testing happens
	print('-------Teardown test_new_processing_request fixture --------')

""" Fixtures for celery testing """

@pytest.fixture(scope='session')
def celery_config():
	return {
	    'broker_url': 'amqp://localhost//',
	    'result_backend': 'db+mysql+pymysql://ahoag:p@sswd@localhost:3307/ahoag_celery_test'
	}


