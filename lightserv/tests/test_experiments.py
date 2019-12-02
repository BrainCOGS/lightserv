from flask import url_for, session, request
import json

def test_exps_show_up_on_main_page(test_client,test_login):
	""" Check that the test post is rendered on the home page """
	response = test_client.get(url_for('main.home'), follow_redirects=True)

	assert b'light sheet requests' in response.data and b'rabbit anti-RFP 1:1000' in response.data

def test_new_request_form_renders(test_client,test_login):
	""" Ensure that the experiment form renders properly """

	response = test_client.get(url_for('requests.new_request'),follow_redirects=True)

	assert b'Background Info' in response.data	

def test_setup_samples(test_client,test_login):
	""" Ensure that submitting the experiment form correctly works """

	# First simulate pressing the "Setup samples" button
	from lightserv.requests.forms import NewRequestForm
	data = dict(
			labname="Wang",correspondence_email="test@demo.com",
			request_name="Demo Experiment",
			description="This is a demo experiment",
			species="mouse",number_of_samples=1,
			sample_prefix='sample',uniform_clearing=True,
			uniform_imaging=True,
			sample_submit_button=True
			)

	response = test_client.post(url_for('requests.new_request'),
		data=data,
			follow_redirects=True
		)	

	assert b'Clearing setup' in response.data  

def test_submit_good_experiment(test_client,test_login):
	# Simulate filling out entire new request form including clearing and imaging sections 
	from lightserv.requests.forms import NewRequestForm
	form = NewRequestForm(formdata=None)
	

	# request.form['clearing_samples.append_entry()
	response = test_client.post(
		url_for('requests.new_request'),data={
			'labname':"Wang",'correspondence_email':"test@demo.com",
			'request_name':"Demo Experiment",
			'description':"This is a demo experiment",
			'species':"mouse",'number_of_samples':1,
			'sample_prefix':'sample',
			'username':test_login['user'],
			'clearing_samples-0-clearing_protocol':'iDISCO abbreviated clearing',
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data

def test_submit_bad_experiments(test_client,test_schema,test_login):
	""" Ensure that submitting the experiment form incorrectly (two different ways)
	does not result in a successful post request """
	response1 = test_client.post(
		url_for('requests.new_request'),data=dict(
			labname="Wang",correspondence_email="test@demo.com",
			title="Bad Experiment",
			description="This is a bad experiment that should not work because Image resolution is enum and I give it an empty string",
			species="rat",clearing_protocol="uDISCO",
			primary_antibody="None",secondary_antibody="None",
			image_resolution="",channel488='cell_detection',
			channel555='',channel647='registration',channel790='',
			username=test_login['user']
			),
			follow_redirects=True
		)

	response2 = test_client.post(
		url_for('requests.new_request'),data=dict(
			labname="Wang",correspondence_email="test@demo.com",
			title="Bad Experiment2",
			description="\
			This is a bad experiment that should not work because when clearing_protocol=iDISCO+, \
			there needs to be a primary antibody provided",
			species="rat",clearing_protocol="iDISCO+",
			antibody1="",antibody2="None",
			image_resolution="",channel488='cell_detection',
			channel555='',channel647='registration',channel790='',
			username=test_login['user']
			),
			follow_redirects=True
		)	
	# Now check that the post just goes back to the new experiment form
	# If it were to succeed, it would go to the home page and 'Your Datasets' would be displayed
	assert b'light sheet requests' not in response1.data
	assert b'light sheet requests' not in response2.data