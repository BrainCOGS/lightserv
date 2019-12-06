from flask import url_for, session, request
import json
import tempfile,webbrowser

# def test_exps_show_up_on_main_page(test_client,test_login):
# 	""" Check that the test post is rendered on the home page """
# 	response = test_client.get(url_for('main.home'), follow_redirects=True)

# 	assert b'light sheet requests' in response.data and b'rabbit anti-RFP 1:1000' in response.data

def test_new_request_form_renders(test_client,test_login):
	""" Ensure that the new request form renders properly (only the top part of the form)"""

	response = test_client.get(url_for('requests.new_request'),follow_redirects=True)

	assert b'Background Info' in response.data and b"Clearing setup" not in response.data

def test_setup_samples_uniform(test_client,test_login):
	""" Ensure that hitting the "setup samples" button in the new request form
	renders the rest of the form (clearing and imaging/processing sections) 
	using uniform clearing and imaging and renders only 1 sample sub-form

	Does not actually enter any data into the db so does not need test_schema 
	fixture.
	 """

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="Demo Experiment",
			description="This is a demo experiment",
			species="mouse",number_of_samples=2,
			sample_prefix='sample',uniform_clearing=True,
			uniform_imaging=True,
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True
		)	

	assert b'Clearing setup' in response.data  
	assert b'Sample 1:' in response.data
	assert b'Sample 2:' not in response.data # uniform_imaging was used so even though number_of_samples=2, the user only needs to fill out one sample form 

def test_setup_samples_nonuniform(test_client,test_login):
	""" Ensure that hitting the "setup samples" button in the new request form
	renders the rest of the form (clearing and imaging/processing sections) 
	using non-uniform clearing and imaging and renders the correct
	number of sample sub-forms.

	It turned out that it was really counter-intuitive to submit
	the booleanfields for uniform_clearing and uniform_imaging 
	as False. It turns out you need to use "false", because 
	anything else, even the python boolean False, is considered
	True. 
	This link explains this issue somewhat:
	https://code.luasoftware.com/tutorials/python/wtforms-booleanfield-value-and-validation/ 

	Does not actually enter any data into the db so does not need test_schema 
	fixture.
	"""

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="Demo Experiment",
			description="This is a demo experiment",
			species="mouse",number_of_samples=2,
			sample_prefix='sample',uniform_clearing='false',
			uniform_imaging='false',
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data, content_type='multipart/form-data',
			follow_redirects=True
		)	
	with tempfile.NamedTemporaryFile('wb', delete=False,suffix='.html') as f:
		url = 'file://' + f.name 
		f.write(response.data)
	# print(url)
	webbrowser.open(url)
	assert b'Clearing setup' in response.data  
	assert b'Sample 1:' in response.data
	assert b'Sample 2:' in response.data  
	assert b'Sample 3:' not in response.data  

def test_setup_image_resolution_form(test_client,test_login,):
	""" Ensure that hitting the "Set up imaging parameters" button
	in the samples section (assuming samples are already set up)
	renders the imaging table for the user to fill out 
	
	Does not actually enter any data into the db so does not need test_schema 
	fixture.
	"""

	# Simulate pressing the "Set up imaging parameters" button
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Demo Experiment",
			'description':"This is a demo experiment",
			'species':"mouse",'number_of_samples':1,
			'sample_prefix':'sample',
			'username':test_login['user'],
			'uniform_clearing':True,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'imaging_samples-0-image_resolution_forsetup':"1.3x",
			'imaging_samples-0-new_image_resolution_form_submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	
	# with tempfile.NamedTemporaryFile('wb', delete=False,suffix='.html') as f:
	# 	url = 'file://' + f.name 
	# 	f.write(response.data)
	# # print(url)
	# webbrowser.open(url)
	assert b'Set up for image resolution: 1.3x' in response.data  

def test_setup_samples_too_many_samples(test_client,test_login):
	""" Ensure that hitting the "setup samples" button 
	when user has entered >50 samples gives a validation error

	Does not actually enter any data into the db so does not need test_schema 
	fixture.
	"""

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="Demo Experiment",
			description="This is a demo experiment",
			species="mouse",number_of_samples=51,
			sample_prefix='sample',uniform_clearing=True,
			uniform_imaging=True,
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True
		)	

	assert b'Clearing setup' not in response.data  
	assert b'Please limit your requested number of samples' in response.data

def test_submit_good_request(test_client,test_login,test_schema):
	""" Ensure that entire new request form submits when good
	data are used.

	Having test_schema as a parameter means that the db entry
	will be removed after this test completes.
	""" 
	from lightserv import db_lightsheet

	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Demo Experiment",
			'description':"This is a demo experiment",
			'species':"mouse",'number_of_samples':1,
			'sample_prefix':'sample',
			'username':test_login['user'],
			'uniform_clearing':True,
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"This is a demo experiment" in response.data
	assert b"New Request Form" not in response.data
	# db_lightsheet.Request.delete_quick()
def test_setup_samples_duplicate(test_client_single_request):
	""" Ensure that hitting the "setup samples" button 
	when user has entered a duplicate request name 
	gives a validation error.

	Does not actually enter any data into the db so does not need test_schema 
	fixture.
	"""

	# Simulate pressing the "Setup samples" button
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="Demo Experiment",
			description="This is a demo experiment",
			species="mouse",number_of_samples=2,
			sample_prefix='sample',uniform_clearing=True,
			uniform_imaging=True,
			sample_submit_button=True
			)

	response = test_client_single_request.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True
		)	

	assert b'Clearing setup' not in response.data  
	assert b'There already exists a request named' in response.data