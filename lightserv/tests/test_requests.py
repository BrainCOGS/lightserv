from flask import url_for, session, request
import json
import tempfile,webbrowser
from bs4 import BeautifulSoup 
from datetime import datetime

def test_requests_redirects(test_client):
	""" Tests that the requests page returns a 302 code (i.e. a redirect signal) for a not logged in user """
	response = test_client.get(url_for('requests.all_requests'),
		content_type='html/text')
	assert response.status_code == 302, \
			'Status code is {0}, but should be 302 (redirect)'.\
			 format(response.status_code)

def test_home_login_redirects(test_client):
	""" Tests that the home page redirects to the login route """
	response = test_client.get(url_for('requests.all_requests'),
		content_type='html/text',
		follow_redirects=True)

	assert response.status_code == 200, 'Status code is {0}, but should be 200'.format(response.status_code)
	assert b'Logged in as' in response.data

def test_home_page(test_client,test_login):
	""" Check that the home page loads properly """
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)

	assert b'All core facility requests:' in response.data 

def test_new_request_form_renders(test_client,test_login):
	""" Ensure that the new request form renders properly (only the top part of the form)"""

	response = test_client.get(url_for('requests.new_request'),
		follow_redirects=True)

	assert b'Background Info' in response.data and b"Clearing setup" not in response.data

def test_setup_samples(test_client,test_login):
	""" Ensure that hitting the "setup samples" button in the new request form
	renders the rest of the form (clearing and imaging/processing sections) 

	Does not actually enter any data into the db 
	 """

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="Admin request",
			description="This is a demo request",
			species="mouse",number_of_samples=2,
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True,
		)	

	assert b'Clearing setup' in response.data  
	assert b'Sample 1' in response.data
	assert b'Sample 2' in response.data 

def test_setup_image_resolution_form(test_client,test_login,):
	""" Ensure that hitting the "Set up imaging parameters" button
	in the samples section (assuming samples are already set up)
	renders the imaging table for the user to fill out 
	
	Does not actually enter any data into the db
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':test_login['user'],
			'clearing_samples-0-sample_name':'sample-001',
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'imaging_samples-0-image_resolution_forsetup':"1.3x",
			'imaging_samples-0-new_image_resolution_form_submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	
	assert b'Clearing setup' in response.data  
	assert b'Setup for image resolution: 1.3x' in response.data  

def test_uniform_clearing_button_works(test_client,test_login,):
	""" Ensure that hitting the "Apply these clearing parameters to all samples"
	button in the samples section copies the data from sample 1 clearing section 
	to all other clearing sections
	
	Does not actually enter any data into the db
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':2,
			'username':test_login['user'],
			'clearing_samples-0-sample_name':'sample-001',
			'clearing_samples-0-clearing_protocol':'iDISCO+_immuno',
			'clearing_samples-0-antibody1':'test_antibody',
			'clearing_samples-1-sample_name':'sample-002',
			'clearing_samples-1-clearing_protocol':'iDISCO abbreviated clearing',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-1-image_resolution_forsetup':'1.3x',
			'uniform_clearing_submit_button':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	
	select_tag = parsed_html.body.find('select',attrs={'id':'clearing_samples-0-clearing_protocol'})
	sample2_clearing_protocol = select_tag.find('option', selected=True)['value']
	assert sample2_clearing_protocol == 'iDISCO+_immuno'
	sample2_antibody1 = parsed_html.body.find('textarea', attrs={'id':'clearing_samples-1-antibody1'}).text
	assert sample2_antibody1 == 'test_antibody'

def test_uniform_imaging_button_works(test_client,test_login,):
	""" Ensure that hitting the "Apply these imaging/processing parameters to all samples"
	button in the samples section copies the data from sample 1 clearing section 
	to all other clearing sections
	
	Does not actually enter any data into the db
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':2,
			'username':test_login['user'],
			'clearing_samples-0-sample_name':'sample-001',
			'clearing_samples-0-clearing_protocol':'iDISCO+_immuno',
			'clearing_samples-0-antibody1':'test_antibody',
			'clearing_samples-1-sample_name':'sample-002',
			'clearing_samples-1-clearing_protocol':'iDISCO abbreviated clearing',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-injection_detection':True,
			'imaging_samples-1-image_resolution_forsetup':'1.3x',
			'uniform_imaging_submit_button':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	input_tag_registration = parsed_html.body.find('input',
		attrs={'id':'imaging_samples-1-image_resolution_forms-0-channel_forms-0-registration'},checked=True) 
	assert input_tag_registration != None
	input_tag_injection_detection = parsed_html.body.find('input',
		attrs={'id':'imaging_samples-1-image_resolution_forms-0-channel_forms-1-injection_detection'},checked=True) 
	assert input_tag_injection_detection != None
	input_tag_probe_detection = parsed_html.body.find('input',
		attrs={'id':'imaging_samples-1-image_resolution_forms-0-channel_forms-0-probe_detection'},checked=True) 
	assert input_tag_probe_detection == None

def test_uniform_clearing_imaging_buttons_visible_nsamplesgt1(test_client,test_login):
	""" Ensure that the uniform clearing and imaging buttons are  visible 
	if number of samples > 1

	Does not actually enter any data into the db 
	 """

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="Admin request",
			description="This is a demo request",
			species="mouse",number_of_samples=2,
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True,
		)	

	assert b'Apply these clearing parameters to all samples' in response.data  
	assert b'Apply these imaging/processing parameters to all samples' in response.data  

def test_uniform_clearing_imaging_buttons_invisible_nsamples1(test_client,test_login):
	""" Ensure that the uniform clearing and imaging buttons are not visible 
	if number of samples = 1

	Does not actually enter any data into the db 
	 """

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="Admin request",
			description="This is a demo request",
			species="mouse",number_of_samples=1,
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True,
		)	

	assert b'Apply these clearing parameters to all samples' not in response.data  
	assert b'Apply these imaging/processing parameters to all samples' not in response.data  

def test_setup_samples_too_many_samples(test_client,test_login):
	""" Ensure that hitting the "setup samples" button 
	when user has entered >50 samples gives a validation error

	Does not actually enter any data into the db 
	"""
	
	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="Admin request",
			description="This is a demo request",
			species="mouse",number_of_samples=52,
			sample_prefix='sample',
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data
		)	

	assert b'Clearing setup' not in response.data  
	assert b'Please limit your requested number of samples' in response.data

def test_submit_good_request(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	from lightserv import db_lightsheet
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':test_login['user'],
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

	assert b"core facility requests" in response.data
	assert b"This is a demo request" in response.data
	assert b"New Request Form" not in response.data

def test_rat_request_generic_imaging_only(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that only generic imaging is allowed (other options disabled)
	for rat imaging (we cannot register for them because they don't have an atlas yet)

	Does not enter data into the db if it passes, but it might 
	by accident so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	from lightserv import db_lightsheet
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'username':test_login['user'],
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	# with tempfile.NamedTemporaryFile('wb', delete=False,suffix='.html') as f:
	# 	url = 'file://' + f.name 
	# 	f.write(response.data)
	# # print(url)
	# webbrowser.open(url)
	assert b"Only generic imaging is currently available" in response.data
	assert b"New Request Form" in response.data
	
def test_setup_samples_duplicate(test_client,test_login,test_single_request_ahoag):
	""" Ensure that hitting the "setup samples" button 
	when user has entered a duplicate request name 
	gives a validation error.


	Uses the test_single_request_ahoag fixture so that 
	there is already a request in the db ahead of time

	"""
	from lightserv import db_lightsheet

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="Admin request",
			description="This is a demo request",
			species="mouse",number_of_samples=1,
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True
		)	

	assert b'Clearing setup' not in response.data  
	assert b'There already exists a request named' in response.data

def test_duplicate_image_resolution_form(test_client,test_login):
	""" Ensure that hitting the "Set up imaging parameters" button
	in the samples section results in an error if the user tries 
	to render an image resolution table that already exists. 
	
	Does not enter any data into the database
	"""
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
			'uniform_clearing':True,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forsetup':"1.3x",
			'imaging_samples-0-new_image_resolution_form_submit':True
			},
			content_type='multipart/form-data',
			follow_redirects=True
		)	
	with tempfile.NamedTemporaryFile('wb', delete=False,suffix='.html') as f:
		url = 'file://' + f.name 
		f.write(response.data)
	# print(url)
	webbrowser.open(url)
	assert b'Imaging/Processing setup' in response.data  
	assert b'You tried to make a table for image_resolution 1.3x. But that resolution was already picked for this sample:' in response.data

def test_duplicate_sample_names(test_client,test_login):
	""" Ensure that having duplicate sample names raises an error

	Does not enter data into the db 
	""" 
	from lightserv import db_lightsheet
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':2,
			'username':test_login['user'],
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'clearing_samples-1-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-1-sample_name':'sample-001',
			'imaging_samples-1-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-1-image_resolution_forsetup':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	with tempfile.NamedTemporaryFile('wb', delete=False,suffix='.html') as f:
		url = 'file://' + f.name 
		f.write(response.data)
	# print(url)
	webbrowser.open(url)
	assert b"New Request Form" in response.data
	assert b"Sample name: sample-001 is duplicated." in response.data

def test_admin_sees_all_requests(test_client,test_single_request_ahoag,test_login_zmd):
	""" Check that Zahra (zmd, an admin) can see the request made by ahoag
	on the all requests page. 

	Uses the test_single_request_ahoag fixture
	to insert a request into the database as ahoag. Note that the test_login_zmd
	fixture must be after the test_single_request_ahoag fixture in the parameter list 
	in order for Zahra to be logged in after the post request is issued in test_single_request_ahoag
	"""
	
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)
	assert b'Logged in as: zmd' in response.data 	
	assert b'This is a demo request' in response.data 	

def test_nonadmin_only_sees_their_requests(test_client,test_single_request_ahoag,test_single_request_nonadmin):
	""" Check that Manuel (ms81, a nonadmin) cannot see the request made by ahoag
	on the all requests page, but they can see their request.

	Uses the test_single_request_ahoag fixture
	to insert a request into the database as ahoag.

	Uses the test_single_request_nonadmin fixture to insert a request 
	into the database as ms81, a nonadmin. With this fixture being
	the last parameter, this leaves ms81 logged in.
	"""
	
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)
	assert b'Logged in as: ms81' in response.data 	
	assert b'This is a demo request' not in response.data 	
	assert b'This is a request by ms81' in response.data 	

def test_admin_sees_all_samples(test_client,test_single_request_ahoag,test_login_zmd):
	""" Check that Zahra (zmd, an admin) can see the samples from the request made by ahoag
	on the all samples page. 

	Uses the test_single_request_ahoag fixture
	to insert a request into the database as ahoag. Note that the test_login_zmd
	fixture must be after the test_single_request_ahoag fixture in the parameter list 
	in order for Zahra to be logged in after the post request is issued in test_single_request_ahoag
	"""
	
	response = test_client.get(url_for('requests.all_samples'),
		follow_redirects=True)
	assert b'Logged in as: zmd' in response.data 	
	assert b'Admin request' in response.data 	
	assert b'sample-001' in response.data 	

def test_nonadmin_only_sees_their_samples(test_client,test_single_request_ahoag,test_single_request_nonadmin):
	""" Check that Manuel (ms81, a nonadmin) can only see the samples from their request 
	but not the one made by ahoag on the all samples page. 

	Uses the test_single_request_ahoag fixture
	to insert a request into the database as ahoag.

	Uses the test_single_request_nonadmin fixture to insert a request 
	into the database as ms81, a nonadmin. With this fixture being
	the last parameter, this leaves ms81 logged in.
	"""
	
	response = test_client.get(url_for('requests.all_samples'),
		follow_redirects=True)
	assert b'Logged in as: ms81' in response.data 	
	assert b'Admin request' not in response.data 	
	assert b'Nonadmin request' in response.data 	

def test_sort_requests_table_asc_desc(test_client,test_two_requests_ahoag):
	""" Check that sorting the all requests table works 
	for ascending and descending sorting

	Uses the test_two_requests_ahoag fixture
	to insert a two requests into the database as ahoag. 

	"""

	response_forward = test_client.get(url_for('requests.all_requests',sort='request_name',direction='desc'),
		follow_redirects=True)
	parsed_html_forward = BeautifulSoup(response_forward.data,features="html.parser")
	table_tag_forward = parsed_html_forward.find('table',
		attrs={'id':'horizontal'})
	table_row_tags_forward = table_tag_forward.find_all('tr')
	
	assert len(table_row_tags_forward) == 3 # 1 for header, 2 for content
	request_name1_forward = table_row_tags_forward[1].find_all('td')[2].text 
	assert request_name1_forward == 'Admin request 2'

	""" Now GET request with reverse=True """
	response_reverse = test_client.get(url_for('requests.all_requests',sort='request_name',direction='asc'),
		follow_redirects=True)
	parsed_html_reverse = BeautifulSoup(response_reverse.data,features="html.parser")
	table_tag_reverse = parsed_html_reverse.find('table',
		attrs={'id':'horizontal'}) 
	table_row_tags_reverse = table_tag_reverse.find_all('tr')
	# print(table_row_tags_reverse)
	assert len(table_row_tags_reverse) == 3 # 1 for header, 2 for content
	request_name1_reverse = table_row_tags_reverse[1].find_all('td')[2].text 
	assert request_name1_reverse == 'Admin request 1'

def test_sort_requests_table_all_columns(test_client,test_two_requests_ahoag):
	""" Check that sorting all columns of all requests table works 

	Uses the test_two_requests_ahoag fixture
	to insert a two requests into the database as ahoag. 
	"""
	for column_name in ['datetime_submitted','username','request_name','description','species','number_of_samples',
	'fraction_cleared','fraction_imaged','fraction_processed']:
		response = test_client.get(
			url_for('requests.all_requests',sort=column_name,direction='desc'),
			follow_redirects=True)
		assert b'All core facility requests' in response.data

def test_sort_samples_table_all_columns(test_client,test_two_requests_ahoag):
	""" Check that sorting all columns of all samples table works 

	Uses the test_two_requests_ahoag fixture
	to insert a two requests into the database as ahoag. 
	"""
	for column_name in ['sample_name','request_name','username','species','datetime_submitted']:
		response = test_client.get(
			url_for('requests.all_samples',sort=column_name,direction='desc'),
			follow_redirects=True)
		assert b'All core facility samples' in response.data	

def test_sort_request_samples_table_all_columns(test_client,test_single_request_ahoag):
	""" Check that sorting all columns of samples table
	for a given request works 

	Uses the test_single_request_ahoag fixture
	to insert a request into the database as ahoag. 

	"""
	for column_name in ['sample_name','request_name','username','imaging_request_number','clearing_protocol',
	'antibody1','antibody2','imaging_progress']:
		response = test_client.get(
			url_for('requests.request_overview',username='ahoag',request_name='Admin request',
				table_id='horizontal_samples_table',sort=column_name,direction='desc'),
			follow_redirects=True)
		assert b'Samples in this request' in response.data	