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
from lightserv import create_app, config, db_lightsheet
import secrets
import pytest
from flask import url_for
import datajoint as dj
from datetime import datetime

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
	ctx.pop()

@pytest.fixture(scope='module') 
def test_client_firefox():
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

	testing_client.environ_base["HTTP_USER_AGENT"] = user_agent_str_firefox
	testing_client.environ_base["HTTP_X_REMOTE_USER"] = 'ahoag'

	ctx = app.test_request_context() # makes it so I can use the url_for() function in the tests
	ctx.push()
	yield testing_client # this is where the testing happens
	print('-------Teardown test client--------')
	ctx.pop()

""" Fixtures for logging in as different users (admins, non admins) """

@pytest.fixture(scope='function')
def test_login(test_client):

	""" Log the user in. Requires a test_client fixture to do this. """
	print('----------Setup login as ahoag response----------')
	username = 'ahoag'
	with test_client.session_transaction() as sess:
		sess['user'] = username
	all_usernames = db_lightsheet.User().fetch('username') 
	if username not in all_usernames:
		email = username + '@princeton.edu'
		user_dict = {'username':username,'princeton_email':email}
		db_lightsheet.User().insert1(user_dict)
	yield sess
	print('----------Teardown login as ahoag response----------')
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
	username = 'ms81'
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

""" General purpose fixtures """

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

""" Fixtures for inserting requests as different users or using different species """

@pytest.fixture(scope='function') 
def test_single_sample_request_ahoag(test_client,test_login,test_delete_request_db_contents):
	""" Submits a new request as 'ahoag' with a single sample that can be used for various tests.

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
	from lightserv import db_lightsheet
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin 4x request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'4x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
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
def test_request_all_mouse_clearing_protocols_ahoag(test_client,test_login,test_delete_request_db_contents):
	""" Submits a new request as 'ahoag' with a sample for each of the 4 
	clearing protocols that can be used for mice.

	It uses the test_delete_request_db_contents fixture, which means that 
	the entry is deleted as soon as the test has been run
	"""
	print('----------Setup test_single_request_ahoag fixture ----------')
	from lightserv import db_lightsheet
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"ahoag@princeton.edu",
			'request_name':"All mouse clearing protocol request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':4,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'clearing_samples-1-clearing_protocol':'iDISCO+_immuno',
			'clearing_samples-1-antibody1':'test antibody for immunostaining',
			'clearing_samples-1-sample_name':'sample-002',
			'imaging_samples-1-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-1-image_resolution_forsetup':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-channel_forms-0-registration':True,
			'clearing_samples-2-clearing_protocol':'uDISCO',
			'clearing_samples-2-sample_name':'sample-003',
			'imaging_samples-2-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-2-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-2-image_resolution_forsetup':'1.3x',
			'imaging_samples-2-image_resolution_forms-0-channel_forms-0-registration':True,
			'clearing_samples-3-clearing_protocol':'iDISCO_EdU',
			'clearing_samples-3-sample_name':'sample-004',
			'imaging_samples-3-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-3-image_resolution_forms-0-atlas_name':'allen_2017',
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
	
@pytest.fixture(scope='function') 
def test_rat_request_nonadmin(test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Submits a new request as Manuel ('ms81', a nonadmin) for species='rat' that can be used for various tests.

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
			'request_name':"Nonadmin rat request",
			'description':"This is a request for a rat by ms81, a non admin",
			'species':"rat",'number_of_samples':1,
			'username':current_user,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-generic_imaging':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_single_request_nonadmin fixture --------')
	
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
	from lightserv import db_lightsheet
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ahoag",
			request_name="Admin request",
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
	from lightserv import db_lightsheet
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ahoag",
			request_name="Admin 4x request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_ahoag fixture --------')


@pytest.fixture(scope='function') 
def test_cleared_request_nonadmin(test_client,test_single_sample_request_nonadmin,
	test_login_ll3,test_delete_request_db_contents):
	""" Clears the single request by 'ms81' (with clearer='ll3') 

	Uses test_single_sample_request_nonadmin request so that a request is in the db
	when it comes time to do the clearing
	
	Runs test_login_ll3 next so that 'll3' gets logged in and can do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	print('----------Setup test_cleared_request_ahoag fixture ----------')
	from lightserv import db_lightsheet
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ms81",
			request_name="Nonadmin request",
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
	from lightserv import db_lightsheet
	now = datetime.now()
	data_abbreviated_clearing = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ahoag",
			request_name="All mouse clearing protocol request",
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
			request_name="All mouse clearing protocol request",
			clearing_protocol="iDISCO+_immuno",
			antibody1="test antibody for immunostaining",antibody2="",
			clearing_batch_number=2),
		data=data_idiscoplus_clearing,
		follow_redirects=True,
		)	

	data_udisco_clearing = dict(time_dehydr_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ahoag",
			request_name="All mouse clearing protocol request",
			clearing_protocol="uDISCO",
			antibody1="",antibody2="",
			clearing_batch_number=3),
		data = data_udisco_clearing,
		follow_redirects=True,
		)	

	data_idisco_edu_clearing = dict(time_dehydr_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ahoag",
			request_name="All mouse clearing protocol request",
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
	""" Clears the single rat request by Manuel (ms81, a nonadmin) (with clearer='ll3') 

	"""
	print('----------Setup test_cleared_request_ahoag fixture ----------')
	from lightserv import db_lightsheet
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		pbs_wash1_notes='some rat notes',submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="ms81",
			request_name="Nonadmin rat request",
			clearing_protocol="iDISCO abbreviated clearing (rat)",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	

	yield test_client # this is where the testing happens
	print('-------Teardown test_cleared_request_ahoag fixture --------')

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
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_resolution':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='Admin request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	yield test_client
	print('----------Teardown test_imaged_request_ahoag fixture ----------')


""" Fixtures for follow-up imaging and processing requests """


@pytest.fixture(scope='function') 
def test_new_imaging_request_ahoag(test_client,test_single_sample_request_ahoag):
	""" A fixture to make a request with two imaging requests 
	for a single sample. 

	Uses test_single_sample_request_ahoag to make a single request with a single 
	sample for setup

	"""
	print('-------Setup test_new_imaging_request fixture --------')
	response = test_client.post(url_for('imaging.new_imaging_request',
			username='ahoag',request_name='Admin request',
			sample_name='sample-001'),
		data={
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-atlas_name':'allen_2017',
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
			username='ahoag',request_name='Admin request',
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