from flask import url_for, session, request
import json
import tempfile,webbrowser
from bs4 import BeautifulSoup 
from datetime import datetime, date

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

def test_home_page(test_client,test_login):
	""" Check that the home page loads properly """
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)

	assert b'All core facility requests:' in response.data 

""" Testing new_request() """

def test_new_request_form_renders(test_client,test_login):
	""" Ensure that the new request form renders properly (only the top part of the form)"""

	response = test_client.get(url_for('requests.new_request'),
		follow_redirects=True)

	assert b'Background Info' in response.data and b"Clearing setup" not in response.data

def test_setup_samples_mouse(test_client,test_login):
	""" Ensure that hitting the "setup samples" button in the new request form
	renders the rest of the form (clearing and imaging/processing sections) 

	Does not actually enter any data into the db 
	"""

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="admin_request",
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

def test_setup_samples_rat(test_client,test_login):
	""" Ensure that hitting the "setup samples" button in the new request form
	renders the rest of the form (clearing and imaging/processing sections) 

	Does not actually enter any data into the db 
	 """

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Tank",correspondence_email="test@demo.com",
			request_name="Admin_rat_request",
			description="This is a demo request",
			species="rat",number_of_samples=2,
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True,
		)	

	assert b'Clearing setup' in response.data  
	assert b'Sample 1' in response.data
	assert b'Sample 2' in response.data 

def test_setup_image_resolution_form_mouse(test_client,test_login,):
	""" Ensure that hitting the "Set up imaging parameters" button
	in the samples section (assuming samples are already set up)
	renders the imaging table for the user to fill out 
	
	Does not actually enter any data into the db
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
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

def test_setup_image_resolution_form_rat(test_client,test_login,):
	""" Ensure that hitting the "Set up imaging parameters" button
	in the samples section (assuming samples are already set up)
	renders the imaging table for the user to fill out 
	
	Does not actually enter any data into the db
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Tank/Brody",'correspondence_email':"test@demo.com",
			'request_name':"Admin_rat_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'username':test_login['user'],
			'clearing_samples-0-sample_name':'sample-001',
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
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
			'request_name':"admin_request",
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
	print(parsed_html.body.find('textarea', attrs={'id':'clearing_samples-1-antibody1'}))
	assert sample2_antibody1.strip() == 'test_antibody'

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
			'request_name':"admin_request",
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

def test_uniform_clearing_imaging_buttons_visible_nsamplesgt1(test_client,test_login):
	""" Ensure that the uniform clearing and imaging buttons are  visible 
	if number of samples > 1

	Does not actually enter any data into the db 
	 """

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="admin_request",
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
			request_name="admin_request",
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
			request_name="admin_request",
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

def test_submit_good_mouse_request(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	today = date.today()
	today_proper_format = today.strftime('%Y-%m-%d')
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':test_login['user'],
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

def test_submit_good_mouse_request_4x(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	today = date.today()
	today_proper_format = today.strftime('%Y-%m-%d')
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':test_login['user'],
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

def test_submit_good_rat_request(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	today = date.today()
	today_proper_format = today.strftime('%Y-%m-%d')
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Admin_rat_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'username':test_login['user'],
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
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

	assert b"core facility requests" in response.data
	assert b"Admin_rat_request" in response.data
	assert b"New Request Form" not in response.data

def test_submit_mouse_self_clearing_request(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	from lightserv import db_lightsheet

	request_name = "Admin_self_clearing_request"
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':request_name,
			'description':"This is a demo request where the clearer is self-assigned",
			'species':"mouse",'number_of_samples':1,
			'username':test_login['user'],
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
	clearer = (db_lightsheet.Request.ClearingBatch() & 'username="ahoag"' & \
		f'request_name="{request_name}"' & 'clearing_batch_number=1').fetch1('clearer')
	assert clearer == 'ahoag'
	assert b"core facility requests" in response.data
	assert b"This is a demo request where the clearer is self-assigned" in response.data
	assert b"New Request Form" not in response.data

def test_submit_mouse_self_imaging_request(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	from lightserv import db_lightsheet

	request_name = "Admin_self_clearing_request"
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':request_name,
			'description':"This is a demo request where the imager is self-assigned",
			'species':"mouse",'number_of_samples':1,
			'username':test_login['user'],
			'self_imaging':True,
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
	imager = (db_lightsheet.Request.ImagingRequest() & 'username="ahoag"' & \
		f'request_name="{request_name}"' & 'sample_name="sample-001"' & 
		'imaging_request_number=1').fetch1('imager')
	assert imager == 'ahoag'
	assert b"core facility requests" in response.data
	assert b"This is a demo request where the imager is self-assigned" in response.data
	assert b"New Request Form" not in response.data

def test_submit_mouse_self_clearing_nonadmin_request(test_client,
	test_login_nonadmin,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	from lightserv import db_lightsheet

	request_name = "Nonadmin_self_clearing_request"
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':request_name,
			'description':"This is a demo request where the clearer is self-assigned",
			'species':"mouse",'number_of_samples':1,
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
	clearer = (db_lightsheet.Request.ClearingBatch() & 'username="lightserv-test"' & \
		f'request_name="{request_name}"' & 'clearing_batch_number=1').fetch1('clearer')
	assert clearer == 'lightserv-test'
	assert b"core facility requests" in response.data
	assert b"This is a demo request where the clearer is self-assigned" in response.data
	assert b"New Request Form" not in response.data


def test_idiscoplus_request_validates_antibody(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that trying to submit a request where
	iDISCO+_immuno clearing protocol is used but 
	antibody1 is not specified results in a validation error

	DOES not enter data into the db, unless it fails, so keep the 
	test_delete_request_db_contents fixture just in case
	""" 
	from lightserv import db_lightsheet
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request_with_immunostaining",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':test_login['user'],
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

def test_submit_empty_samples(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that sample sections have content upon final submission of new request form
	
	Uses test_delete_request_db_contents just in case test fails and actually 
	enters something into the db
	""" 
	from lightserv import db_lightsheet
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':test_login['user'],
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"New Request Form" in response.data
	assert b"You must fill out and submit the Samples setup section first." in response.data

def test_submit_no_samples(test_client,test_login):
	""" Ensure that sample setup button gives validation error
	if number_of_samples = 0

	""" 
	from lightserv import db_lightsheet
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':0,
			'username':test_login['user'],
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

def test_submit_bad_mouse_clearing_protocol(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that a validation error is raised if
	one tries to use a rat clearing protocol when species='mouse'

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	from lightserv import db_lightsheet
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':test_login['user'],
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

def test_submit_bad_rat_clearing_protocol(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that a validation error is raised if
	one tries to use a mouse clearing protocol when species='rat'

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	from lightserv import db_lightsheet
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'username':test_login['user'],
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

def test_rat_request_only_generic_imaging_allowed(test_client,test_login,test_delete_request_db_contents):
	""" Ensure that only generic imaging is allowed (other options disabled)
	for rat imaging (we cannot register for them because they don't have an atlas yet)

	Does not enter data into the db if it passes, but it might 
	by accident so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	from lightserv import db_lightsheet
	response1 = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'username':test_login['user'],
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

	assert b"Only generic imaging is currently available" in response1.data
	assert b"New Request Form" in response1.data

	response2 = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'username':test_login['user'],
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-injection_detection':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"Only generic imaging is currently available" in response2.data
	assert b"New Request Form" in response2.data

	response3 = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'username':test_login['user'],
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-probe_detection':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"Only generic imaging is currently available" in response3.data
	assert b"New Request Form" in response3.data

	response4 = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"rat",'number_of_samples':1,
			'username':test_login['user'],
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing (rat)',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-cell_detection':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"Only generic imaging is currently available" in response4.data
	assert b"New Request Form" in response4.data
	
def test_setup_samples_duplicate(test_client,test_login,test_single_sample_request_ahoag):
	""" Ensure that hitting the "setup samples" button 
	when user has entered a duplicate request name 
	gives a validation error.


	Uses the test_single_sample_request_ahoag fixture so that 
	there is already a request in the db ahead of time

	"""
	from lightserv import db_lightsheet

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="admin_request",
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

def test_no_image_resolution_forms(test_client,test_login):
	""" Ensure that a validation error is raised is user tries
	to submit a request without setting up any image resolution forms 
	
	Uses test_delete_request_db_contents in case test fails
	and it actually enters data into the db
	"""
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
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

def test_empty_image_resolution_form(test_client,test_login):
	""" Ensure that a validation error is raised is user tries
	to submit a request without setting up any image resolution forms 
	
	Uses test_delete_request_db_contents in case test fails
	and it actually enters data into the db
	"""
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
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
			'request_name':"admin_request",
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
	# with tempfile.NamedTemporaryFile('wb', delete=False,suffix='.html') as f:
	# 	url = 'file://' + f.name 
	# 	f.write(response.data)
	# # print(url)
	# webbrowser.open(url)
	assert b'Imaging/Processing setup' in response.data  
	assert b'You tried to make a table for image_resolution 1.3x. But that resolution was already picked for this sample:' in response.data

def test_sagittal_orientation_required_if_registration(test_client,test_login):
	""" Ensure that a validation error is raised is user tries
	to submit a request where output orientation is not sagittal
	but they requested registration. 
	
	"""
	today = date.today()
	today_proper_format = today.strftime('%Y-%m-%d')
	with test_client.session_transaction() as sess:
		current_user = sess['user']
	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':current_user,
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

def test_duplicate_sample_names(test_client,test_login):
	""" Ensure that having duplicate sample names raises an error

	Does not enter data into the db 
	""" 
	from lightserv import db_lightsheet
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"admin_request",
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
	# with tempfile.NamedTemporaryFile('wb', delete=False,suffix='.html') as f:
	# 	url = 'file://' + f.name 
	# 	f.write(response.data)
	# # print(url)
	# webbrowser.open(url)
	assert b"New Request Form" in response.data
	assert b"Sample name: sample-001 is duplicated." in response.data

def test_detection_modes_require_registration(test_client,test_login,test_delete_request_db_contents):
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
			'request_name':"admin_request",
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
			'username':test_login['user'],
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

def test_multiple_samples_same_clearing_batch(test_client,test_login,test_delete_request_db_contents):
	""" Test that submitting multiple samples with the same 
	clearing protocol, antibody1, antibody2 combination 
	results in samples being put into the same clearing batch

	Enters data into the db so uses the 
	test_delete_request_db_contents fixture to remove it 
	after the test
	""" 
	from lightserv import db_lightsheet
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Multiple_sample_admin_request",
			'description':"This is a multiple sample test request",
			'species':"mouse",'number_of_samples':2,
			'username':test_login['user'],
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-0-sample_name':'sample-001',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'clearing_samples-1-clearing_protocol':'iDISCO abbreviated clearing',
			'clearing_samples-1-sample_name':'sample-002',
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
	# print(db_lightsheet.Request.ClearingBatch())
	number_in_batch = (db_lightsheet.Request.ClearingBatch() & \
		'request_name="Multiple_sample_admin_request"' & \
		'username = "ahoag"' & 'clearing_protocol="iDISCO abbreviated clearing"' & \
		'clearing_batch_number=1').fetch1('number_in_batch')
	assert number_in_batch == 2

def test_nonadmin_cannot_see_checkbox_to_submit_as_someone_else(test_client,
		test_login_nonadmin):
	""" Ensure that a nonadmin, e.g. Manuel (lightserv-test) 
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

def test_admin_can_see_checkbox_to_submit_as_someone_else(test_client,
		test_login_zmd):
	""" Ensure that a Zahra (zmd, an admin) 
	can see the checkbox to submit the request
	as another user

	Does not enter data into the db  
	""" 

	response = test_client.get(
		url_for('requests.new_request'),
			content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"New Request Form" in response.data
	assert b"Check if you are filling out this form for someone else" in response.data

def test_submit_good_mouse_request_for_someone_else(test_client,
		test_login,test_delete_request_db_contents):
	""" Ensure that entire new request form submits when good
	data are used, entering for someone else.

	DOES enter data into the db so it uses the fixture:
	test_delete_request_db_contents, which simply deletes 
	the Request() contents (and all dependent tables) after the test is run
	so that other tests see blank contents 
	""" 
	today = date.today()
	today_proper_format = today.strftime('%Y-%m-%d')
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Tank/Brody",'correspondence_email':"test@demo.com",
			'request_name':"Request_for_someone_else",
			'requested_by':test_login['user'],
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
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

def test_request_name_no_spaces(test_client,
		test_login,test_delete_request_db_contents):
	""" Ensure that entire new request form raises a 
	ValidationError when user tries to submit a request name 
	that has spaces in it

	If test fails, it could possibly write data to the db
	so use the fixture test_delete_request_db_contents
	to remove any contents just in case
	""" 
	today = date.today()
	today_proper_format = today.strftime('%Y-%m-%d')
	
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Request with spaces",
			'requested_by':test_login['user'],
			'description':"This is a demo request",
			'species':"mouse",'number_of_samples':1,
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

	assert b"New Request Form" in response.data
	assert b"core facility requests" not in response.data
	assert b"Request_name must not contain any blank spaces" in response.data


""" Testing all_requests() """

def test_admin_sees_all_requests(test_client,test_single_sample_request_ahoag,test_login_zmd):
	""" Check that Zahra (zmd, an admin) can see the request made by ahoag
	on the all requests page. 

	Uses the test_single_sample_request_ahoag fixture
	to insert a request into the database as ahoag. Note that the test_login_zmd
	fixture must be after the test_single_sample_request_ahoag fixture in the parameter list 
	in order for Zahra to be logged in after the post request is issued in test_single_sample_request_ahoag
	"""
	
	response = test_client.get(url_for('requests.all_requests'),
		follow_redirects=True)
	assert b'This is a demo request' in response.data 	

def test_nonadmin_only_sees_their_requests(test_client,test_single_sample_request_ahoag,test_single_sample_request_nonadmin):
	""" Check that Manuel (lightserv-test, a nonadmin) cannot see the request made by ahoag
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

def test_multichannel_request_works(test_client,test_multichannel_request_ahoag):
	""" Testing that my fixture: test_multichannel_request_ahoag
	works
	""" 
	response = test_client.get(
		url_for('requests.all_requests'),
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"admin_multichannel_request" in response.data


""" Testing all_samples() """

def test_admin_sees_all_samples(test_client,test_single_sample_request_ahoag,test_login_zmd):
	""" Check that Zahra (zmd, an admin) can see the samples from the request made by ahoag
	on the all samples page. 

	Uses the test_single_sample_request_ahoag fixture
	to insert a request into the database as ahoag. Note that the test_login_zmd
	fixture must be after the test_single_sample_request_ahoag fixture in the parameter list 
	in order for Zahra to be logged in after the post request is issued in test_single_sample_request_ahoag
	"""
	
	response = test_client.get(url_for('requests.all_samples'),
		follow_redirects=True)
	assert b'admin_request' in response.data 	
	assert b'sample-001' in response.data 	

def test_nonadmin_only_sees_their_samples(test_client,test_single_sample_request_ahoag,test_single_sample_request_nonadmin):
	""" Check that Manuel (lightserv-test, a nonadmin) can only see the samples from their request 
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

def test_all_samples_multiple_imaging_requests(test_client,test_new_imaging_request_ahoag):
	""" Check that both imaging requests are displayed 
	in the all samples table in the all_samples route
	when multiple imaging requests are present in the 
	same request.

	Uses the test_new_imaging_request_ahoag fixture
	to insert a request and then a new imaging request
	into the database as ahoag. 
	"""
	response = test_client.get(
				url_for('requests.all_samples'),
			follow_redirects=True
		)	
	assert b'core facility samples (from all requests):' in response.data	

	parsed_html = BeautifulSoup(response.data,features="html.parser")
	
	table_tag = parsed_html.body.find('table',attrs={'id':'all_samples_table'})
	# print(table_tag)
	first_sample_imaging_requests_table_tag = table_tag.find('table',attrs={'id':'imaging_requests'})
	rows = first_sample_imaging_requests_table_tag.find_all('tr')
	assert len(rows) == 7 # 1 for main sample, 3 for first imaging request (the nested processing request adds an extra row), 3 for second imaging request

def test_all_samples_multiple_processing_requests(test_client,test_new_processing_request_ahoag):
	""" Check that both processing requests are displayed 
	in the all samples table in the all_samples route
	when a single imaging request but two processing requests
	are present in the same request.

	Uses the test_new_processing_request_ahoag fixture
	to insert a request and then a new processing request
	into the database as ahoag. 
	"""
	response = test_client.get(
				url_for('requests.all_samples'),
			follow_redirects=True
		)	
	assert b'core facility samples (from all requests):' in response.data	

	parsed_html = BeautifulSoup(response.data,features="html.parser")
	
	table_tag = parsed_html.body.find('table',attrs={'id':'all_samples_table'})
	# print(table_tag)
	first_sample_processing_requests_table_tag = table_tag.find('table',attrs={'id':'processing_requests'})
	print(first_sample_processing_requests_table_tag)
	rows = first_sample_processing_requests_table_tag.find_all('tr')
	assert len(rows) == 3 # 1 for header, 1 for first processing request, 1 for second processing request

""" Testing request_overview() """
	
def test_request_samples_multiple_imaging_requests(test_client,test_new_imaging_request_ahoag):
	""" Check that both imaging requests are displayed 
	in the samples table in the request_overview() route
	when multiple imaging requests are present in the 
	same request.

	Uses the test_new_imaging_request_ahoag fixture
	to insert a request and then a new imaging request
	into the database as ahoag. 
	"""
	response = test_client.get(
				url_for('requests.request_overview',request_name='admin_request',
					username='ahoag',sample_name='sample-001'),
			follow_redirects=True
		)	
	assert b'Samples in this request:' in response.data	

	parsed_html = BeautifulSoup(response.data,features="html.parser")
	
	table_tag = parsed_html.body.find('table',attrs={'id':'horizontal_samples_table'})
	# print(table_tag)
	first_sample_imaging_requests_table_tag = table_tag.find('table',attrs={'id':'imaging_requests'})
	rows = first_sample_imaging_requests_table_tag.find_all('tr')
	assert len(rows) == 7 # 1 for main sample, 3 for first imaging request (the nested processing request adds an extra row), 3 for second imaging request

def test_request_samples_multiple_processing_requests(test_client,test_new_processing_request_ahoag):
	""" Check that both imaging requests are displayed 
	in the samples table in the request_overview() route
	when multiple imaging requests are present in the 
	same request.

	Uses the test_new_imaging_request_ahoag fixture
	to insert a request and then a new imaging request
	into the database as ahoag. 
	"""
	response = test_client.get(
				url_for('requests.request_overview',request_name='admin_request',
					username='ahoag',sample_name='sample-001'),
			follow_redirects=True
		)	
	assert b'Samples in this request:' in response.data	

	parsed_html = BeautifulSoup(response.data,features="html.parser")
	
	table_tag = parsed_html.body.find('table',attrs={'id':'horizontal_samples_table'})
	# print(table_tag)
	first_sample_imaging_requests_table_tag = table_tag.find('table',attrs={'id':'processing_requests'})
	rows = first_sample_imaging_requests_table_tag.find_all('tr')
	assert len(rows) == 3 # 1 for main sample, 3 for first imaging request (the nested processing request adds an extra row), 3 for second imaging request

def test_sort_request_overview_table(test_client,test_single_sample_request_ahoag):
	""" Check that the sort links work in request overview table

	Uses the test_new_imaging_request_ahoag fixture
	to insert a request and then a new imaging request
	into the database as ahoag. 
	"""


	for column_name in ['sample_name','request_name','username','clearing_protocol']:
		print(column_name)
		response = test_client.get(
					url_for('requests.request_overview',request_name='admin_request',
						username='ahoag',sample_name='sample-001',sort=column_name,direction='desc'),
				follow_redirects=True
			)	
		print(response.data)
		assert b'Samples in this request:' in response.data	


