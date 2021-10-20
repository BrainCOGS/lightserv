from flask import url_for, session, request
import json
import tempfile,webbrowser
from bs4 import BeautifulSoup 
from datetime import datetime, date
from lightserv import db_lightsheet

today = date.today()
today_proper_format = today.strftime('%Y-%m-%d')

""" Testing new_request() """

def test_new_request_form_loads(test_client,test_login):
	""" Ensure that the new request form renders properly (only the top part of the form)"""

	response = test_client.get(url_for('requests.new_request'),
		follow_redirects=True)

	assert b'Background Info' in response.data and b"Clearing setup" not in response.data

def test_mouse_request(test_client,test_login_nonadmin,
	test_delete_request_db_contents):
	""" Ensure that hitting the "setup samples" button in the new request form
	renders the rest of the form (clearing and imaging/processing sections) 

	Does not actually enter any data into the db 
	"""

	username = test_login_nonadmin['user']
	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="admin_requesnont",
			description="This is a demo request",
			raw_data_retention_preference="important",
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

	""" Ensure that hitting the "Set up imaging parameters" button
	in the samples section (assuming samples are already set up)
	renders the imaging table for the user to fill out 
	
	Does not actually enter any data into the db
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-sample_name':'sample-001',
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'imaging_samples-0-image_resolution_forsetup':"1.3x",
			'imaging_samples-0-new_image_resolution_form_submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	
	assert b'Clearing setup' in response.data  
	assert b'Setup for image resolution: 1.3x' in response.data  

	""" Ensure that hitting the "Apply these clearing parameters to all samples"
	button in the samples section copies the data from sample 1 clearing section 
	to all other clearing sections
	
	Does not actually enter any data into the db
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':2,
			'raw_data_retention_preference':"important",
			'username':username,
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
	print(parsed_html.body.find('textarea', attrs={'id':'clearing_samples-1-antibody1'}))
	assert sample2_antibody1.strip() == 'test_antibody'

	""" Ensure that hitting the "Apply these imaging/processing parameters to all samples"
	button in the samples section copies the data from sample 1 clearing section 
	to all other clearing sections
	
	Does not actually enter any data into the db
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':2,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-sample_name':'sample-001',
			'clearing_samples-0-clearing_protocol':'iDISCO+_immuno',
			'clearing_samples-0-antibody1':'test_antibody',
			'clearing_samples-1-sample_name':'sample-002',
			'clearing_samples-1-clearing_protocol':'iDISCO abbreviated clearing',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
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

	""" Ensure that the uniform clearing and imaging buttons are visible 
	if number of samples > 1

	Does not actually enter any data into the db 
	"""

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="nonadmin_request",
			description="This is a demo request",
			species="mouse",number_of_samples=2,
			raw_data_retention_preference="important",
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True,
		)	

	assert b'Apply these clearing parameters to all samples' in response.data  
	assert b'Apply these imaging/processing parameters to all samples' in response.data  

	""" Ensure that the uniform clearing and imaging buttons are not visible 
	if number of samples = 1

	Does not actually enter any data into the db 
	 """

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="nonadmin_request",
			description="This is a demo request",
			species="mouse",number_of_samples=1,
			raw_data_retention_preference="important",
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True,
		)	

	assert b'Apply these clearing parameters to all samples' not in response.data  
	assert b'Apply these imaging/processing parameters to all samples' not in response.data  

	""" Ensure that hitting the "setup samples" button 
	when user has entered >50 samples gives a validation error

	Does not actually enter any data into the db 
	"""
	
	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="nonadmin_request",
			description="This is a demo request",
			species="mouse",number_of_samples=52,
			raw_data_retention_preference="important",
			sample_prefix='sample',
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data
		)	

	assert b'Clearing setup' not in response.data  
	assert b'Please limit your requested number of samples' in response.data

	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"This is a demo request" in response.data
	assert b"New Request Form" not in response.data

	""" Ensure that a 4x entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 

	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request_4x",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'4x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"This is a demo request" in response.data
	assert b"New Request Form" not in response.data
	

	""" Ensure that trying to submit a request where
	iDISCO+_immuno clearing protocol is used but 
	antibody1 is not specified results in a validation error

	DOES not enter data into the db, unless it fails, so keep the 
	test_delete_request_db_contents fixture just in case
	""" 
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request_with_immunostaining",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-clearing_protocol':'iDISCO+_immuno',
			'clearing_samples-0-antibody1':'',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"New Request Form" in response.data
	assert b"Antibody must be specified because you selected an immunostaining clearing protocol"

	""" Ensure that sample sections have content upon final submission of new request form
	
	Uses test_delete_request_db_contents just in case test fails and actually 
	enters something into the db
	""" 
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request2",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"New Request Form" in response.data
	assert b"You must fill out and submit the Samples setup section first." in response.data

	""" Ensure that sample setup button gives validation error
	if number_of_samples = 0

	""" 
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request2",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':0,
			'raw_data_retention_preference':"important",
			'username':username,
			'sample_submit_button':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	# with tempfile.NamedTemporaryFile('wb', delete=False,suffix='.html') as f:
	# 	url = 'file://' + f.name 
	# 	f.write(response.data)
	# # print(url)
	# webbrowser.open(url)
	assert b"New Request Form" in response.data
	assert b"You must have at least one sample to submit a request" in response.data


	""" Ensure that a validation error is raised if
	one tries to use a rat clearing protocol when species='mouse'
	""" 
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request_bad_clearing_protocol",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b"New Request Form" in response.data
	assert b"Clearing protocol: iDISCO abbreviated clearing (rat) can only be used with rat subjects." in response.data

	""" Ensure that hitting the "setup samples" button 
	when user has entered a duplicate request name 
	gives a validation error. Uses the same request
	name as the submitted request above so it should
	trigger the duplicate validation error.
	"""
	

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="nonadmin_request",
			description="This is a demo request",
			species="mouse",number_of_samples=1,
			raw_data_retention_preference="important",
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True
		)	

	assert b'Clearing setup' not in response.data  
	assert b'There already exists a request named' in response.data

	""" Ensure that a validation error is raised if user tries
	to submit a request without setting up any image resolution forms 
	
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request3",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'uniform_clearing':True,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'submit':True
			},
			content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b'New Request Form' in response.data  
	assert b'you must set up the imaging parameters for at least one image resolution' in response.data 

	""" Ensure that having duplicate sample names raises an error
	""" 
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request3",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':2,
			'raw_data_retention_preference':"important",
			'username':username,
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
	assert b"New Request Form" in response.data
	assert b"Sample name: sample-001 is duplicated." in response.data

	""" Ensure that a validation error is raised is user tries
	to submit a request without setting up any image resolution forms 
	
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request3",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'uniform_clearing':True,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'submit':True
			},
			content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b'New Request Form' in response.data  
	assert b'The image resolution table: 1.3x for sample name: sample-001 is empty. Please select at least one option.' in response.data 

	""" Ensure that hitting the "Set up imaging parameters" button
	in the samples section results in an error if the user tries 
	to render an image resolution table that already exists. 
	"""
	
	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_request4",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
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

	assert b'Imaging/Processing setup' in response.data  
	assert b'You tried to make a table for image_resolution 1.3x. But that resolution was already picked for this sample:' in response.data

	""" Ensure that a validation error is raised is user tries
	to submit a request where output orientation is not sagittal
	but they requested registration. 
	
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'coronal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b'New Request Form' in response.data  
	assert b'Output orientation must be sagittal since registration was selected' in response.data 

	""" Ensure that any of the "*detection" imaging modes require a registration 
	channel to be selected
	""" 
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-injection_detection':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"New Request Form"  in response.data
	assert b"You must select a registration channel when requesting any of the detection channels" in response.data


	""" Test that submitting multiple samples with the same 
	clearing protocol, antibody1, antibody2 combination 
	results in samples being put into the same clearing batch
	"""
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Multiple_sample_nonadmin_request",
			'description':"This is a multiple sample test request",
			'species':"mouse",'number_of_samples':2,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'clearing_samples-1-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-1-sample_name':'sample-002',
			'clearing_samples-1-expected_handoff_date':today_proper_format,
			'clearing_samples-1-perfusion_date':today_proper_format,
			'imaging_samples-1-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-1-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-1-image_resolution_forsetup':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b"New Request Form" not in response.data # redirected away from new request form
	number_in_batch = (db_lightsheet.Request.ClearingBatch() & \
		'request_name="Multiple_sample_nonadmin_request"' & \
		f'username = "{username}"' & 'clearing_protocol="iDISCO abbreviated clearing"' & \
		'clearing_batch_number=1').fetch1('number_in_batch')
	assert number_in_batch == 2

	""" Ensure that a nonadmin, e.g lightserv-test
	cannot see the checkbox to submit the request
	as another user

	Does not enter data into the db  
	""" 
	response = test_client.get(
		url_for('requests.new_request'),
			content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"New Request Form" in response.data
	assert b"Check if you are filling out this form for someone else" not in response.data

	""" Test submitting a request using all available resolutions """
	
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_allres_request",
			'description':"This is a demo request to submit all image resolutions",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'uniform_clearing':True,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-1-image_resolution':'1.1x',
			'imaging_samples-0-image_resolution_forms-1-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-1-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-1-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-2-image_resolution':'2x',
			'imaging_samples-0-image_resolution_forms-2-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-2-channel_forms-0-generic_imaging':True,
			'imaging_samples-0-image_resolution_forms-2-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-3-image_resolution':'3.6x',
			'imaging_samples-0-image_resolution_forms-3-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-3-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-3-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-4-image_resolution':'4x',
			'imaging_samples-0-image_resolution_forms-4-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-4-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-4-channel_forms-0-channel_name':'488',
			'submit':True
			},
			content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b"core facility requests" in response.data
	assert b"This is a demo request" in response.data
	assert b"New Request Form" not in response.data

	""" Ensure that new request form raises a 
	ValidationError when user tries to submit a request name 
	that has spaces or non-alphanumeric chars (besides '_'),
	likewise for sample_name

	If test fails, it could possibly write data to the db
	so use the fixture test_delete_request_db_contents
	to remove any contents just in case
	""" 
	# Request name with spaces
	data1 = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="request with spaces",
			description=username,
			raw_data_retention_preference="important",
			species="mouse",number_of_samples=1,
			sample_submit_button=True
			)
	response1 = test_client.post(
		url_for('requests.new_request'),
			data=data1,
			content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"New Request Form" in response1.data
	assert b"core facility requests" not in response1.data
	assert b"Request name must not contain any blank spaces" in response1.data

	# Request name with special chars
	data2 = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="request:special;chars",
			description=username,
			raw_data_retention_preference="important",
			species="mouse",number_of_samples=1,
			sample_submit_button=True
			)
	response2 = test_client.post(
		url_for('requests.new_request'),
			data=data2,
			content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"New Request Form" in response2.data
	assert b"core facility requests" not in response2.data
	assert b"Request name must not contain any non-alpha numeric characters" in response2.data

	# sample name with spaces
	data3 = {
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"good_nonadmin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-sample_name':'sample name with spaces',
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'imaging_samples-0-image_resolution_forsetup':"1.3x",
			'imaging_samples-0-new_image_resolution_form_submit':True
			}
	response3 = test_client.post(
		url_for('requests.new_request'),
			data=data3,
			content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b"New Request Form" in response3.data
	assert b"core facility requests" not in response3.data
	assert b"Sample name: sample name with spaces must not contain any blank spaces" in response3.data


	# sample name with non alphanumeric chars
	data4 = {
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"good_nonadmin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-sample_name':'sample_name_nonalphanumeric:1',
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'imaging_samples-0-image_resolution_forsetup':"1.3x",
			'imaging_samples-0-new_image_resolution_form_submit':True
			}
	response4 = test_client.post(
		url_for('requests.new_request'),
			data=data4,
			content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b"New Request Form" in response4.data
	assert b"core facility requests" not in response4.data
	assert b"Sample name: sample_name_nonalphanumeric:1 must not contain any non-alpha numeric characters" in response4.data

	""" Ensure that trying to use multiple registration channels 
	in the same image resolution table results in an error
	
	Does not enter any data into the database
	"""

	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'uniform_clearing':True,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-injection_detection':True,
			'imaging_samples-0-image_resolution_forsetup':"1.3x",
			'imaging_samples-0-new_image_resolution_form_submit':True
			},
			content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b'There can only be one registration channel per image resolution' in response.data  

	""" Ensure that an AntibodyHistory() db entry is made when antibodies are requested """

	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_antibody_request",
			'description':"This is a test request with an antibody",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'uniform_clearing':True,
			'clearing_samples-0-clearing_protocol':'iDISCO+_immuno',
			'clearing_samples-0-antibody1':'a primary antibody',
			'clearing_samples-0-antibody2':'a secondary antibody',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'submit':True
			},
			content_type='multipart/form-data',
			follow_redirects=True
		)	
	
	assert b"core facility requests" in response.data
	assert b"This is a demo request" in response.data
	assert b"New Request Form" not in response.data
	""" Check that an insert was made into the AntibodyHistory() table """
	antibody_history_contents = db_lightsheet.AntibodyHistory() & 'request_name="nonadmin_antibody_request"'
	print(antibody_history_contents)
	assert len(antibody_history_contents) == 1

def test_rat_request(test_client,test_login_nonadmin,
	test_delete_request_db_contents):
	
	""" Ensure that only generic imaging is allowed (other options disabled)
	for rat imaging (we cannot register for them because they don't have an atlas yet)

	Does not enter data into the db if it passes, but it might 
	by accident so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	username = test_login_nonadmin['user']
	data1 = {'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			}

	response1 = test_client.post(
		url_for('requests.new_request'),data=data1
		,content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"Only generic imaging is currently available" in response1.data
	assert b"New Request Form" in response1.data

	data2 = data1.copy()
	data2['imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration'] = False
	data2['imaging_samples-0-image_resolution_forms-0-channel_forms-0-injection_detection'] = True
	response2 = test_client.post(
		url_for('requests.new_request'),data=data2,content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"Only generic imaging is currently available" in response2.data
	assert b"New Request Form" in response2.data

	data3 = data1.copy()
	data3['imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration'] = False
	data3['imaging_samples-0-image_resolution_forms-0-channel_forms-0-probe_detection'] = True
	response3 = test_client.post(
		url_for('requests.new_request'),data=data3,
			content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"Only generic imaging is currently available" in response3.data
	assert b"New Request Form" in response3.data

	data4 = data1.copy()
	data4['imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration'] = False
	data4['imaging_samples-0-image_resolution_forms-0-channel_forms-0-cell_detection'] = True
	response4 = test_client.post(
		url_for('requests.new_request'),data=data4,
		content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"Only generic imaging is currently available" in response4.data
	assert b"New Request Form" in response4.data

	""" Ensure that hitting the "setup samples" button in the new request form
	renders the rest of the form (clearing and imaging/processing sections) 

	Does not actually enter any data into the db 
	"""

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Tank",correspondence_email="test@demo.com",
			request_name="nonadmin_rat_request",
			description="This is a demo request",
			species="rat",number_of_samples=2,
			raw_data_retention_preference="important",
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True,
		)	

	assert b'Clearing setup' in response.data  
	assert b'Sample 1' in response.data
	assert b'Sample 2' in response.data 


	""" Ensure that hitting the "Set up imaging parameters" button
	in the samples section (assuming samples are already set up)
	renders the imaging table for the user to fill out 
	
	Does not actually enter any data into the db
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Tank/Brody",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_rat_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-sample_name':'sample-001',
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
			'imaging_samples-0-image_resolution_forsetup':"1.3x",
			'imaging_samples-0-new_image_resolution_form_submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b'Clearing setup' in response.data  
	assert b'Setup for image resolution: 1.3x' in response.data  



	""" Ensure that a validation error is raised if
	one tries to use a mouse clearing protocol when species='rat'

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_rat_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-generic_imaging':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b"New Request Form" in response.data
	assert b"The clearing protocol you selected: iDISCO abbreviated clearing is not valid for species=rat." in response.data

	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_rat_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
			'clearing_samples-0-sample_name':'sample-001',
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-generic_imaging':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"nonadmin_rat_request" in response.data
	assert b"New Request Form" not in response.data

	""" Ensure that entire new request form successfully 
	submits for a rat uDISCO request for lightserv-test user.
	""" 
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"rat_udisco_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-clearing_protocol':'uDISCO (rat)',
			'clearing_samples-0-sample_name':'sample-001',
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-generic_imaging':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"rat_udisco_request" in response.data
	assert b"New Request Form" not in response.data

def test_submit_mouse_self_clearing_self_imaging_request(test_client,test_login_nonadmin,
	test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	username = test_login_nonadmin['user']
	request_name = "nonadmin_self_clearing_request"
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':request_name,
			'description':"This is a demo request where the clearer is self-assigned",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'self_clearing':True,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	clearer = (db_lightsheet.Request.ClearingBatch() & f'username="{username}"' & \
		f'request_name="{request_name}"' & 'clearing_batch_number=1').fetch1('clearer')
	assert clearer == username
	assert b"core facility requests" in response.data
	assert b"This is a demo request where the clearer is self-assigned" in response.data
	assert b"New Request Form" not in response.data

	request_name = "nonadmin_self_imaging_request"
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':request_name,
			'description':"This is a demo request where the imager is self-assigned",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'self_imaging':True,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	imager = (db_lightsheet.Request.ImagingRequest() & f'username="{username}"' & \
		f'request_name="{request_name}"' & 'sample_name="sample-001"' & 
		'imaging_request_number=1').fetch1('imager')
	assert imager == username
	assert b"core facility requests" in response.data
	assert b"This is a demo request where the imager is self-assigned" in response.data
	assert b"New Request Form" not in response.data

def test_submit_good_mouse_request_for_someone_else(test_client,
	test_login_imager,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used, entering for someone else.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 

	""" Ensure that an admin 
	can see the checkbox to submit the request
	as another user
	""" 

	response = test_client.get(
		url_for('requests.new_request'),
			content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"New Request Form" in response.data
	assert b"Check if you are filling out this form for someone else" in response.data

	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Tank/Brody",'correspondence_email':"test@demo.com",
			'request_name':"Request_for_someone_else",
			'other_username':'newuser',
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':'lightserv-test',
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"Request_for_someone_else" in response.data
	assert b"New Request Form" not in response.data

def test_submit_good_mouse_request_with_auditor(test_client,
	test_login_nonadmin,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used, and an auditor is given.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 

	""" Ensure that an admin
	can see the checkbox to submit the request
	as another user
	""" 

	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Tank/Brody",'correspondence_email':"test@demo.com",
			'request_name':"Request_with_auditor",
			'auditor_username':'audit-user',
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':'lightserv-test',
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"Request_with_auditor" in response.data
	assert b"New Request Form" not in response.data

	""" Make sure auditor can see this request all all_requests and all_samples 
	pages """
	""" Log user in """
	with test_client.session_transaction() as sess:
		sess['user'] = "audit-user"
	response = test_client.get(
		url_for('requests.all_requests'),
			content_type='multipart/form-data',
			follow_redirects=True
		)
	assert b"core facility requests" in response.data
	assert b"Request_with_auditor" in response.data
	assert b"lightserv-test" in response.data

def test_newlines_do_not_affect_clearing_batch_membership(test_client,
	test_login_nonadmin,test_delete_request_db_contents):
	""" Ensure that carriage returns
	or newlines entered when typing in primary or secondary antibodies 
	do not affect which clearing batches the samples end up in.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"test_request_newlines",
			'description':"This is a test request to ensure that newlines in antibody fields do not affect clearing batch membership",
			'species':"mouse",'number_of_samples':2,
			'raw_data_retention_preference':"important",
			'username':test_login_nonadmin['user'],
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO+_immuno',
			'clearing_samples-0-antibody1':'test_antibody1',
			'clearing_samples-0-antibody2':'test_antibody2',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'clearing_samples-1-expected_handoff_date':today_proper_format,
			'clearing_samples-1-perfusion_date':today_proper_format,
			'clearing_samples-1-clearing_protocol':'iDISCO+_immuno',
			'clearing_samples-1-antibody1':'test_antibody1\r\n',
			'clearing_samples-1-antibody2':'test_antibody2\r\n',
			'clearing_samples-1-sample_name':'sample-002',
			'imaging_samples-1-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-1-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-1-image_resolution_forsetup':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"This is a test request to ensure" in response.data
	assert b"New Request Form" not in response.data

	""" Now check to make sure that only one clearing batch was made """
	clearing_batch_results = db_lightsheet.Request().ClearingBatch() & 'request_name="test_request_newlines"'
	assert len(clearing_batch_results) == 1

def test_expected_handoff_date_required_for_non_self_clearing(
	test_client,test_login_nonadmin,test_delete_request_db_contents):
	""" Test that if lightserv-test tries to submit the new request and 
	did not select self clearing and did not fill out the expected handoff date 
	a validation error occurs.

	""" 
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':test_login_nonadmin['user'],
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"New Request Form" in response.data
	assert b"Expected handoff date required for samples: sample-001" in response.data
	assert b"core facility requests" not in response.data

def test_submit_good_mouse_request_3p6x(test_client,
	test_login_nonadmin,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_3p6x_smartspim_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':test_login_nonadmin['user'],
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'3.6x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-injection_detection':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-channel_name':'642',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"This is a demo request" in response.data
	assert b"New Request Form" not in response.data

	# Verify that the microscope entered into the db is the correct one
	imaging_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
		'request_name="nonadmin_3p6x_smartspim_request"'
	microscope,image_resolution = imaging_resolution_request_contents.fetch1('microscope','image_resolution')
	assert microscope == 'SmartSPIM'
	assert image_resolution == '3.6x'

def test_submit_good_mouse_request_15x(test_client,
	test_login_nonadmin,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"nonadmin_15x_smartspim_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':test_login_nonadmin['user'],
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'15x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-cell_detection':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-channel_name':'642',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"This is a demo request" in response.data
	assert b"New Request Form" not in response.data

	# Verify that the microscope entered into the db is the correct one
	imaging_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
		'request_name="nonadmin_15x_smartspim_request"'
	microscope,image_resolution = imaging_resolution_request_contents.fetch1('microscope','image_resolution')
	assert microscope == 'SmartSPIM'
	assert image_resolution == '15x'

def test_submit_multisample_multichannel_request(test_client,test_login_nonadmin,
	test_multisample_multichannel_request_nonadmin):
	""" Test submitting a request for 3 samples 
	and multiple channels. 
	Samples 1 and 2 use 1.3x with 488,555
	Sample 3 uses 1.3x with 488 and 647"""
	
	response = test_client.get(url_for('requests.all_requests'),
		content_type='html/text')
	assert b"core facility requests" in response.data
	assert b"nonadmin_manysamp_request" in response.data
	assert b"New Request Form" not in response.data

def test_submit_paxinos_mouse_request(test_client,
	test_login_nonadmin,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 

	username = test_login_nonadmin['user']
	request_name = "nonadmin_paxinos_request"
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':request_name,
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'paxinos',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"This is a demo request" in response.data
	assert b"New Request Form" not in response.data

	""" check db to make sure correct atlas was inserted for this request """
	
	restrict_dict = {'username':username,'request_name':request_name}
	processing_resolution_request_contents = db_lightsheet.Request.ProcessingResolutionRequest() & restrict_dict
	atlas_name = processing_resolution_request_contents.fetch1('atlas_name')
	assert atlas_name == 'paxinos'

def test_clearing_and_imaging_batches_properly_assigned(test_client,
	test_login_nonadmin,
	test_delete_request_db_contents):
	""" Ensure that clearing and imaging batches are 
	properly assigned when multiple samples with different parameters
	are entered.
	Sample 1: CB #1, IB #1
	Sample 2: CB #1, IB #1
	Sample 3: CB #1, IB #2
	Sample 4: CB #2, IB #1 

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	username = test_login_nonadmin['user']
	request_name = "nonadmin_request"
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':request_name,
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':4,
			'raw_data_retention_preference':"important",
			'username':username,
			'clearing_samples-0-expected_handoff_date':today_proper_format,
			'clearing_samples-0-perfusion_date':today_proper_format,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'clearing_samples-1-expected_handoff_date':today_proper_format,
			'clearing_samples-1-perfusion_date':today_proper_format,
			'clearing_samples-1-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-1-sample_name':'sample-002',
			'imaging_samples-1-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-1-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-1-image_resolution_forsetup':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'clearing_samples-2-expected_handoff_date':today_proper_format,
			'clearing_samples-2-perfusion_date':today_proper_format,
			'clearing_samples-2-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-2-sample_name':'sample-003',
			'imaging_samples-2-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-2-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-2-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-2-image_resolution_forsetup':'1.3x',
			'imaging_samples-2-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-2-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-2-image_resolution_forms-0-channel_forms-1-cell_detection':True,
			'imaging_samples-2-image_resolution_forms-0-channel_forms-1-channel_name':'647',
			'clearing_samples-3-expected_handoff_date':today_proper_format,
			'clearing_samples-3-perfusion_date':today_proper_format,
			'clearing_samples-3-clearing_protocol':'uDISCO',
			'clearing_samples-3-sample_name':'sample-004',
			'imaging_samples-3-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-3-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-3-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-3-image_resolution_forsetup':'1.3x',
			'imaging_samples-3-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-3-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"This is a demo request" in response.data
	assert b"New Request Form" not in response.data

	""" Make sure clearing and imaging batches were assigned correctly
	by checking the db contents """
	clearing_batch_1_restrict_dict = {'username':username,
		'request_name':request_name,
		'clearing_batch_number':1}
	clearing_batch_1_contents = db_lightsheet.Request().ClearingBatch() & clearing_batch_1_restrict_dict
	number_of_samples_in_clearing_batch_1 = clearing_batch_1_contents.fetch1('number_in_batch')
	assert number_of_samples_in_clearing_batch_1 == 3
	clearing_batch_1_sample_contents = db_lightsheet.Request().ClearingBatchSample() & clearing_batch_1_restrict_dict
	samples_in_clearing_batch_1 = clearing_batch_1_sample_contents.fetch('sample_name')
	assert 'sample-004' not in samples_in_clearing_batch_1

	clearing_batch_2_restrict_dict = {'username':username,
		'request_name':request_name,
		'clearing_batch_number':2}
	clearing_batch_2_contents = db_lightsheet.Request().ClearingBatch() & clearing_batch_2_restrict_dict
	number_of_samples_in_clearing_batch_2 = clearing_batch_2_contents.fetch1('number_in_batch')
	assert number_of_samples_in_clearing_batch_2 == 1
	clearing_batch_2_sample_contents = db_lightsheet.Request().ClearingBatchSample() & clearing_batch_2_restrict_dict
	sample_in_clearing_batch_2 = clearing_batch_2_sample_contents.fetch1('sample_name')
	assert sample_in_clearing_batch_2 == 'sample-004' 

	clearing_batch_1_imaging_batch_1_restrict_dict = {'username':username,
		'request_name':request_name,
		'clearing_batch_number':1,
		'imaging_batch_number':1}
	clearing_batch_1_imaging_batch_1_contents = db_lightsheet.Request().ImagingBatch() & clearing_batch_1_imaging_batch_1_restrict_dict
	number_of_samples_in_clearing_batch_1_imaging_batch_1 = clearing_batch_1_imaging_batch_1_contents.fetch1(
		'number_in_imaging_batch')
	assert number_of_samples_in_clearing_batch_1_imaging_batch_1 == 2
	clearing_batch_1_imaging_batch_1_sample_contents = db_lightsheet.Request().ImagingBatchSample() & \
		clearing_batch_1_imaging_batch_1_restrict_dict
	samples_in_clearing_batch_1_imaging_batch_1 = clearing_batch_1_imaging_batch_1_sample_contents.fetch('sample_name')
	assert 'sample-003' not in samples_in_clearing_batch_1_imaging_batch_1 \
		and 'sample-004' not in samples_in_clearing_batch_1_imaging_batch_1

	clearing_batch_1_imaging_batch_2_restrict_dict = {'username':username,
		'request_name':request_name,
		'clearing_batch_number':1,
		'imaging_batch_number':2}
	clearing_batch_1_imaging_batch_2_contents = db_lightsheet.Request().ImagingBatch() & \
		clearing_batch_1_imaging_batch_2_restrict_dict
	number_of_samples_in_clearing_batch_1_imaging_batch_2 = clearing_batch_1_imaging_batch_2_contents.fetch1(
		'number_in_imaging_batch')
	assert number_of_samples_in_clearing_batch_1_imaging_batch_2 == 1
	clearing_batch_1_imaging_batch_2_sample_contents = db_lightsheet.Request().ImagingBatchSample() & \
		clearing_batch_1_imaging_batch_2_restrict_dict
	sample_in_clearing_batch_1_imaging_batch_2 = clearing_batch_1_imaging_batch_2_sample_contents.fetch1('sample_name')
	assert sample_in_clearing_batch_1_imaging_batch_2 == 'sample-003'

	clearing_batch_2_imaging_batch_1_restrict_dict = {'username':username,
		'request_name':request_name,
		'clearing_batch_number':2,
		'imaging_batch_number':1}
	clearing_batch_2_imaging_batch_1_contents = db_lightsheet.Request().ImagingBatch() & clearing_batch_2_imaging_batch_1_restrict_dict
	number_of_samples_in_clearing_batch_2_imaging_batch_1 = clearing_batch_2_imaging_batch_1_contents.fetch1(
		'number_in_imaging_batch')
	assert number_of_samples_in_clearing_batch_2_imaging_batch_1 == 1
	clearing_batch_2_imaging_batch_1_sample_contents = db_lightsheet.Request().ImagingBatchSample() & \
		clearing_batch_2_imaging_batch_1_restrict_dict
	sample_in_clearing_batch_2_imaging_batch_1 = clearing_batch_2_imaging_batch_1_sample_contents.fetch1('sample_name')
	assert sample_in_clearing_batch_2_imaging_batch_1 == 'sample-004' 
 

""" Testing all_requests() """

def test_all_requests(test_client):
	""" Tests that the all_requests page redirects to the login route """
	response = test_client.get(url_for('requests.all_requests'),
		content_type='html/text',
		follow_redirects=True)

	assert response.status_code == 200, 'Status code is {0}, but should be 200'.format(response.status_code)


	""" Tests that the requests page returns a 302 code (i.e. a redirect signal) for a not logged in user """
	""" clear out any "user" key in session if it happened to sneak in 
	during a previous test """
	with test_client.session_transaction() as sess:
		try:
			sess.pop('user')
		except:
			pass
	
	response = test_client.get(url_for('requests.all_requests'),
		content_type='html/text')
	
	assert response.status_code == 302, \
			'Status code is {0}, but should be 302 (redirect)'.\
			 format(response.status_code)

def test_admin_sees_nonadmin_request(test_client,test_single_sample_request_nonadmin,test_login_imager):
	""" Check that an admin can see requests from all users """
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)

	assert b'All core facility requests:' in response.data 
	assert b'nonadmin_request' in response.data

def test_nonadmin_only_sees_their_requests(test_client,
	test_single_sample_request_ahoag,test_single_sample_request_nonadmin):
	""" Check that lightserv-test, a nonadmin cannot see the request made by ahoag
	on the all requests page, but they can see their request.

	Uses the test_single_sample_request_ahoag fixture
	to insert a request into the database as ahoag.

	Uses the test_single_sample_request_nonadmin fixture to insert a request 
	into the database as lightserv-test, a nonadmin. With this fixture being
	the last parameter, this leaves lightserv-test logged in.
	"""
	
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)

	assert b'This is a demo request' not in response.data 	
	assert b'This is a request by lightserv-test' in response.data 	

def test_sort_requests_table_all_columns(test_client,test_two_requests_ahoag):
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
	assert request_name1_forward == 'admin_request_2'

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
	assert request_name1_reverse == 'admin_request_1'

	""" Check that sorting all columns of all requests table works 
	"""
	for column_name in ['datetime_submitted','username','request_name','description','species','number_of_samples',
	'fraction_cleared','fraction_imaged','fraction_processed']:
		response = test_client.get(
			url_for('requests.all_requests',sort=column_name,direction='desc'),
			follow_redirects=True)
		assert b'All core facility requests' in response.data

def test_nonadmin_sees_their_archival_request(test_client,test_archival_request_nonadmin):
	""" Check that lightserv-test, a nonadmin cannot see their
	archival request that was ingested outside of the usual new request form. 

	"""
	
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag = parsed_html.find('table',
		attrs={'id':'horizontal'})
	table_row_tags = table_tag.find_all('tr')
	header_row = table_row_tags[0].find_all('th')
	data_row = table_row_tags[1].find_all('td')
	for ii,col in enumerate(header_row):
		if col.text == 'archival?':
			archival_column_index = ii
			break
	is_archival = data_row[archival_column_index].text
	assert is_archival == "yes"

def test_all_requests_reflects_cleared_request(test_client,test_cleared_request_nonadmin):
	""" Check that a cleared request shows shows fraction_cleared = 1/1
	for a request where clearing is complete. 
	"""

	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	# table_tags = parsed_html.find('table')
	table_tag = parsed_html.find('table',
		attrs={'id':'horizontal'})
	table_row_tags = table_tag.find_all('tr')
	header_row = table_row_tags[0].find_all('th')

	data_row = table_row_tags[1].find_all('td')
	for ii,col in enumerate(header_row):
		if col.text == 'fraction cleared':
			clearing_log_column_index = ii
			print(clearing_log_column_index)
			break
	fraction_cleared = data_row[clearing_log_column_index].text
	assert fraction_cleared == "1/1"

""" Testing all_samples() """

def test_admin_sees_all_samples(test_client,test_single_sample_request_nonadmin,test_login_imager):
	""" Check that an admin can see the samples from the request made by a nonadmin
	on the all samples page. 

	Uses the test_single_sample_request_nonadmin fixture
	to insert a request into the database as nonadmin. Note that the test_login_imager
	fixture must be after the test_single_sample_request_nonadmin fixture in the parameter list 
	in order for imager to be logged in after the post request is issued in test_single_sample_request_nonadmin
	"""
	
	response = test_client.get(url_for('requests.all_samples'),
		follow_redirects=True)
	# assert b'nonadmin_request' in response.data 	
	assert b'sample-001' in response.data 	

def test_nonadmin_only_sees_their_samples(test_client,test_single_sample_request_ahoag,test_single_sample_request_nonadmin):
	""" Check that lightserv-test, a nonadmin can only see the samples from their request 
	but not the one made by ahoag on the all samples page. 

	Uses the test_single_sample_request_ahoag fixture
	to insert a request into the database as ahoag.

	Uses the test_single_sample_request_nonadmin fixture to insert a request 
	into the database as lightserv-test, a nonadmin. With this fixture being
	the last parameter, this leaves lightserv-test logged in.
	"""
	
	response = test_client.get(url_for('requests.all_samples'),
		follow_redirects=True)
	assert b'ahoag' not in response.data 	
	assert b'nonadmin_request' in response.data 	

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

""" Testing request_overview() """
	
def test_sort_request_overview_table(test_client,test_single_sample_request_ahoag):
	""" Check that the sort links work in request overview table

	Uses the test_new_imaging_request_ahoag fixture
	to insert a request and then a new imaging request
	into the database as ahoag. 
	"""


	for column_name in ['sample_name','request_name','username','clearing_protocol']:
		response = test_client.get(
					url_for('requests.request_overview',request_name='admin_request',
						username='ahoag',sample_name='sample-001',sort=column_name,direction='desc'),
				follow_redirects=True
			)	
		assert b'Samples in this request:' in response.data	

def test_clearing_table_link_works(test_client,test_cleared_request_nonadmin):
	""" Check that the clearing link shows up for a request where clearing is complete. 
	"""
	# print(processing_request_contents)
	# assert len(processing_request_contents) > 0
	response = test_client.get(url_for('requests.request_overview',
		username='lightserv-test',request_name='nonadmin_request'),
		follow_redirects=True)
	# print(response.data)
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	# table_tags = parsed_html.find('table')
	table_tag = parsed_html.find('table',
		attrs={'id':'horizontal_samples_table'})
	table_row_tags = table_tag.find_all('tr')
	header_row = table_row_tags[0].find_all('th')
	data_row = table_row_tags[1].find_all('td')
	# print(len(header_row))
	# print(len(data_row))
	
	# print(data_row)
	for ii,col in enumerate(header_row):
		if col.text == 'Clearing log':
			clearing_log_column_index = ii
			print(clearing_log_column_index)
			break
	anchor = data_row[clearing_log_column_index].find_all('a',href=True)[0]
	href = anchor['href']
	assert href == "/clearing/clearing_table/lightserv-test/nonadmin_request/1"

def test_archival_nonadmin_request_overview(test_client,test_archival_request_nonadmin):
	""" Check that lightserv-test, a nonadmin can see their
	archival request that was ingested outside of the usual new request form
	in the samples table in request overview route
	"""
	# print("Request() contents:")
	# request_contents = db_lightsheet.Request()
	# print(request_contents)
	# print("Sample() contents:")
	# sample_contents = db_lightsheet.Request().Sample()
	# print(sample_contents)
	response = test_client.get(url_for('requests.request_overview',
		username='lightserv-test',request_name='test_archival_request'),
		follow_redirects=True)
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag = parsed_html.find('table',
		attrs={'id':'horizontal_samples_table'})
	# print(parsed_html)
	table_row_tags = table_tag.find_all('tr')
	header_row = table_row_tags[0].find_all('th')
	data_row = table_row_tags[1].find_all('td')
	for ii,col in enumerate(header_row):
		if col.text == 'archival?':
			archival_column_index = ii
			break
	is_archival = data_row[archival_column_index].text
	assert is_archival == "yes"

""" Testing delete_request() """

def test_delete_request_works(test_client,test_single_sample_request_nonadmin):
	""" Check that lightserv-test (a nonadmin) can delete their own request provided
	the clearing has not started yet.

	Uses the test_single_sample_request_nonadmin fixture
	to insert a request into the database as nonadmin that 
	can then be deleted.	"""
	
	response = test_client.get(url_for('requests.delete_request',
		username='lightserv-test',request_name='nonadmin_request'),
		follow_redirects=True)
	assert b'core facility requests:' in response.data
	assert b'nonadmin_request' not in response.data 	

def test_delete_request_validation(test_client,test_single_sample_request_nonadmin,test_login_imager):
	""" Test that an admin cannot delete a request for lightserv-test since only the one who submitted 
	the request can delete it.

	Uses the test_single_sample_request_nonadmin fixture
	to insert a request into the database.	"""
	
	response = test_client.get(url_for('requests.delete_request',
		username='lightserv-test',request_name='nonadmin_request'),
		follow_redirects=True)

	assert b'core facility requests:' in response.data
	assert b'nonadmin_request' in response.data
	assert b'Only lightserv-test can delete their own request.' in response.data 	

def test_delete_request_denied_if_clearing_started(test_client,test_cleared_request_nonadmin):
	""" Test that request cannot be deleted if clearing has been started (or completed) already

	Uses the test_single_sample_request_nonadmin fixture
	to insert a request into the database.	"""
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	response = test_client.get(url_for('requests.delete_request',
		username='lightserv-test',request_name='nonadmin_request'),
		follow_redirects=True)

	assert b'core facility requests:' in response.data
	assert b'nonadmin_request' in response.data
	assert b'At least one clearing batch for this request is already started.' in response.data 	