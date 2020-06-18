from flask import url_for
from lightserv.main import tasks

def test_welcome_login_redirects(test_client):
	""" Check that when someone lands on the welcome page they are logged in and then the 
	welcome page loads properly """
	response = test_client.get(url_for('main.welcome'),
		follow_redirects=True)

	assert b'Welcome to the' in response.data and b'How to contact us?' in response.data

def test_welcome_page(test_client,test_login):
	""" Check that the welcome page loads properly (once already logged in) """
	response = test_client.get(url_for('main.welcome'),
		follow_redirects=True)

	assert b'Welcome to the' in response.data and b'How to contact us?' in response.data


def test_login_inserts_user(test_client,test_login):
	from lightserv import db_lightsheet
	user_contents = db_lightsheet.User()
	print(user_contents)
	assert len(user_contents) > 0 

def test_welcome_page_firefox_warning(test_client_firefox):
	""" Check that the when user logs in and accesses welcome page
	for the first time they get a flash message warning them to not 
	use firefox"""
	response = test_client_firefox.get(url_for('main.welcome'),
		follow_redirects=True)

	assert b'Welcome to the' in response.data and b'How to contact us?' in response.data
	assert b'Warning: parts of this web portal were not completely tested on your browser: firefox' in response.data

def test_gallery(test_client,test_login):
	""" Check that the gallery page loads properly (once already logged in) """
	response = test_client.get(url_for('main.gallery'),
		follow_redirects=True)

	assert b'Brain Registration and Histology Core Facility Gallery' in response.data 

def test_FAQ(test_client,test_login):
	""" Check that the FAQ page loads properly (once already logged in) """
	response = test_client.get(url_for('main.FAQ'),
		follow_redirects=True)

	assert b'Q: What is stitching/tiling?' in response.data 

def test_spock_connection_page_loads(test_client,test_login):
	""" Check that the page to test the spock loads properly (once already logged in) """
	response = test_client.get(url_for('main.spock_connection_test'),
		follow_redirects=True)

	assert b'Test your connection to spock.pni.princeton.edu' in response.data 

def test_sucessful_spock_connection(test_client,test_login_nonadmin):
	""" Check that the spock connection test results in a successful flash message
	for a user for which it should work """
	response = test_client.post(
		url_for('main.spock_connection_test'),
		follow_redirects=True)

	assert b'Test your connection to spock.pni.princeton.edu' in response.data 
	assert b'Successfully connected to spock.' in response.data 

def test_failed_spock_connection(test_client,test_login_newuser):
	""" Check that the spock connection test results in a danger flash message
	for a user for which it should NOT work """
	response = test_client.post(
		url_for('main.spock_connection_test'),
		follow_redirects=True)
	# with open('test_response.html','wb') as outfile:
	# 	outfile.write(response.data)
	# print("wrote 'test_response.html'")
	assert b'Test your connection to spock.pni.princeton.edu' in response.data 
	assert b'Connection unsuccessful. Please refer to the FAQ and try again.' in response.data 

def test_pre_handoff(test_client):
	""" Check that the pre handoff page loads properly (once already logged in) """
	response = test_client.get(url_for('main.pre_handoff'),
		follow_redirects=True)

	assert b'There are some steps you would want to take before handing us your samples for clearing:' in response.data 

def test_feedback_form_loads(test_client,test_login,test_single_sample_request_ahoag):
	""" Check that the feedback form for a request that has been submitted loads """
	response = test_client.get(url_for('main.feedback',
		username='ahoag',request_name='admin_request'),
		follow_redirects=True)
	test_str = 'Please rate your experience with how we handled this request on scale from 1 (terrible) to 5 (excellent)'
	assert test_str.encode('utf-8') in response.data 	

def test_feedback_form_flashes_if_no_request(test_client,test_login,):
	""" Check that the feedback form for a request that has NOT 
	been submitted reroutes to 404 and flashes a message """
	response = test_client.get(url_for('main.feedback',
		username='ahoag',request_name='admin_request'),
		follow_redirects=True)
	test_str = 'No request with those parameters exists'
	assert test_str.encode('utf-8') in response.data 	
	assert b'Page Not Found (404)' in response.data

def test_feedback_form_submits(test_client,test_login,test_single_sample_request_ahoag):
	""" Check that the feedback form for a request that has been submitted submits """
	response = test_client.post(url_for('main.feedback',
		username='ahoag',request_name='admin_request'),
		data=dict(clearing_rating=5,clearing_notes='',
			imaging_rating=4,imaging_notes='imaging comments',
			processing_rating=3,processing_notes='None',
			other_notes=''),
		follow_redirects=True)
	assert b'Feedback received. Thank you.' in response.data 	
	test_str = 'Please rate your experience with how we handled this request on scale from 1 (terrible) to 5 (excellent)'
	assert test_str.encode('utf-8') not in response.data 	
	welcome_str="Welcome to the Brain Registration and Histology Core Facility Portal at the Princeton Neuroscience Institute"
	assert welcome_str.encode('utf-8') in response.data