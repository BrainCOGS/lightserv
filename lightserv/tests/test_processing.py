from flask import url_for, current_app
import tempfile
import webbrowser
from PIL import Image
from lightserv import db_lightsheet, db_admin, db_spockadmin
from bs4 import BeautifulSoup 
from datetime import datetime
import os, glob
import lorem

""" Tests for Processing Manager """
def test_ahoag_access_processing_manager(test_client,test_imaged_request_ahoag):
	""" Test that ahoag can access the processing task manager
	and see the single entry made and cleared by ahoag  """
	response = test_client.get(url_for('processing.processing_manager')
		, follow_redirects=True)
	assert b'Processing management GUI' in response.data
	assert b'admin_request' in response.data 

def test_nonadmin_access_processing_manager(test_client,
	test_imaged_request_nonadmin):
	""" Test that lightserv-test, a nonadmin can access the processing task manager
	and can see his entry because everyone is by default the processor for their requests """
	response = test_client.get(url_for('processing.processing_manager')
		, follow_redirects=True)
	assert b'Processing management GUI' in response.data
	# assert b'admin_request' not in response.data 
	assert b'nonadmin_request' in response.data 
	# assert b'lightserv-test' in response.data 

def test_nonadmin_access_processing_manager_cannot_see_other_requests(test_client,
	test_imaged_request_ahoag,test_imaged_request_nonadmin):
	""" Test that Manuel (lightserv-test, a nonadmin) can access the processing task manager
	and can see his entry but cannot see ahoag's entry. """
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	response = test_client.get(url_for('processing.processing_manager')
		, follow_redirects=True)
	# print(response.data)
	assert b'Processing management GUI' in response.data
	assert b'ahoag' not in response.data 
	assert b'nonadmin_request' in response.data 
	assert b'lightserv-test' in response.data 

def test_zmd_access_processing_manager(test_client,
	test_imaged_request_ahoag,test_imaged_request_nonadmin):
	""" Test that Zahra (zmd, an admin) can access the processing task manager
	and can see entries by multiple users """
	with test_client.session_transaction() as sess:
		sess['user'] = 'zmd'
	response = test_client.get(url_for('processing.processing_manager')
		, follow_redirects=True)
	assert b'Processing management GUI' in response.data
	assert b'ahoag' in response.data 
	assert b'nonadmin_request' in response.data 
	assert b'lightserv-test' in response.data 

def test_ahoag_multiple_processing_requests_processing_manager(test_client,test_imaged_two_processing_requests_ahoag):
	""" Test that ahoag can access the processing task manager
	and see both of their processing requests for the same request """
	# First log ahoag back in
	with test_client.session_transaction() as sess:
		sess['user'] = 'ahoag'
	response = test_client.get(url_for('processing.processing_manager')
		, follow_redirects=True)
	assert b'Processing management GUI' in response.data
	assert b'admin_request' in response.data 

	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag = parsed_html.find('table',
		attrs={'id':'horizontal_ready_to_process_table'})
	table_row_tags = table_tag.find_all('tr')
	print(table_row_tags)
	print(len(table_row_tags))
	header_row = table_row_tags[0].find_all('th')
	imaging_request_1_row = table_row_tags[1].find_all('td')
	imaging_request_2_row = table_row_tags[2].find_all('td')
	for ii,col in enumerate(header_row):
		if col.text == 'processing request number':
			request_number_column_index = ii
			break
	first_request_number = imaging_request_1_row[request_number_column_index].text
	second_request_number = imaging_request_2_row[request_number_column_index].text
	assert first_request_number == '1'
	assert second_request_number == '2'

def test_ahoag_multiple_imaging_requests_processing_manager(test_client,test_imaged_both_imaging_requests_ahoag):
	""" Test that ahoag can access the processing task manager
	and see both of their imaging requests for the same base request """
	# First log ahoag back in
	with test_client.session_transaction() as sess:
		sess['user'] = 'ahoag'
	response = test_client.get(url_for('processing.processing_manager')
		, follow_redirects=True)
	assert b'Processing management GUI' in response.data
	assert b'admin_request' in response.data 

	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag = parsed_html.find('table',
		attrs={'id':'horizontal_ready_to_process_table'})
	table_row_tags = table_tag.find_all('tr')
	header_row = table_row_tags[0].find_all('th')
	imaging_request_1_row = table_row_tags[1].find_all('td')
	imaging_request_2_row = table_row_tags[2].find_all('td')
	for ii,col in enumerate(header_row):
		if col.text == 'imaging request number':
			request_number_column_index = ii
			break
	first_request_number = imaging_request_1_row[request_number_column_index].text
	second_request_number = imaging_request_2_row[request_number_column_index].text
	assert first_request_number == '1'
	assert second_request_number == '2'

def test_ahoag_can_see_running_processing_requests(test_client,processing_request_ahoag):
	""" Test that ahoag can see running processing request
	in the processing manager"""
	with test_client.session_transaction() as sess:
		sess['user'] = "ahoag"
	response = test_client.get(url_for('processing.processing_manager'),
		follow_redirects=True)
	
	assert b"Processing management GUI" in response.data
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag = parsed_html.find('table',
		attrs={'id':'horizontal_being_processed_table'})
	table_row_tags = table_tag.find_all('tr')
	header_row = table_row_tags[0].find_all('th')
	processing_request_1_row = table_row_tags[1].find_all('td')
	for ii,col in enumerate(header_row):
		if col.text == 'processing progress':
			request_number_column_index = ii
			break
	processing_progress = processing_request_1_row[request_number_column_index].text
	assert processing_progress == 'running'
	
def test_ahoag_can_see_completed_processing_requests(test_client,completed_processing_request_ahoag):
	""" Test that ahoag can see running processing request
	in the processing manager"""
	with test_client.session_transaction() as sess:
		sess['user'] = "ahoag"
	response = test_client.get(url_for('processing.processing_manager'),
		follow_redirects=True)
	
	assert b"Processing management GUI" in response.data
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag = parsed_html.find('table',
		attrs={'id':'horizontal_already_processed_table'})
	table_row_tags = table_tag.find_all('tr')
	header_row = table_row_tags[0].find_all('th')
	processing_request_1_row = table_row_tags[1].find_all('td')
	for ii,col in enumerate(header_row):
		if col.text == 'processing progress':
			request_number_column_index = ii
			break
	processing_progress = processing_request_1_row[request_number_column_index].text
	assert processing_progress == 'complete'

def test_viz_processing_request_fixture_worked(test_client,processing_request_viz_nonadmin):
	""" Test that the fixture that starts a processing request for
	lightserv-test's viz_processed request actually worked and shows 
	up in the processing manager"""
	
	# log lightserv-test in 
	with test_client.session_transaction() as sess:
		sess['user'] = "lightserv-test"
	
	response = test_client.get(url_for('processing.processing_manager'),
		follow_redirects=True)
	
	assert b"Processing management GUI" in response.data
	assert b"viz_processed" in response.data

def test_nonadmin_can_see_completed_processing_request(test_client,completed_processing_request_viz_nonadmin):
	""" Test that lightserv-test can see their completed processing request
	in the processing manager"""
	with test_client.session_transaction() as sess:
		sess['user'] = "lightserv-test"
	response = test_client.get(url_for('processing.processing_manager'),
		follow_redirects=True)
	
	assert b"Processing management GUI" in response.data
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag = parsed_html.find('table',
		attrs={'id':'horizontal_already_processed_table'})
	table_row_tags = table_tag.find_all('tr')
	header_row = table_row_tags[0].find_all('th')
	processing_request_1_row = table_row_tags[1].find_all('td')
	for ii,col in enumerate(header_row):
		if col.text == 'processing progress':
			request_number_column_index = ii
			break
	processing_progress = processing_request_1_row[request_number_column_index].text
	assert processing_progress == 'complete'




""" Tests for processing entry form """

def test_processing_entry_form_loads(test_client,test_imaged_request_ahoag):
	""" Test that ahoag can access the processing entry form
	for his request"""
	response = test_client.get(url_for('processing.processing_entry',
		username='ahoag',request_name='admin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		, follow_redirects=True)

	assert b'Processing Entry Form' in response.data
	assert b'admin_request' in response.data 

def test_processing_entry_form_loads_nonadmin(test_client,test_imaged_request_nonadmin):
	""" Test that lightserv-test can access the processing entry form
	for his request"""
	response = test_client.get(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		, follow_redirects=True)
	assert b'Processing Entry Form' in response.data
	assert b'nonadmin_request' in response.data 

def test_processing_entry_form_submits(test_client,test_imaged_request_ahoag):
	""" Test that ahoag can submit the processing entry form
	for a test sample """
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-atlas_name':'allen_2017',
		'image_resolution_forms-0-image_resolution':'1.3x',
		'submit':True
		}

	username = "ahoag"
	request_name = "admin_request"
	sample_name = "sample-001"
	imaging_request_number = 1
	processing_request_number = 1
	response = test_client.post(url_for('processing.processing_entry',
			username=username,request_name=request_name,sample_name=sample_name,
			imaging_request_number=imaging_request_number,
			processing_request_number=processing_request_number),
		data=data,
		follow_redirects=True)
	assert b"core facility requests" in response.data
	assert b"Processing entry form" not in response.data

	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
			f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' & \
			f'processing_request_number="{processing_request_number}"'
	processing_progress = processing_request_contents.fetch1('processing_progress')
	assert processing_progress == 'running'

def test_multichannel_processing_entry_form_submits(test_client,test_imaged_multichannel_request_ahoag):
	""" Test that the multi-channel imaging request with different 
	tiling schemes for channels 488 and 555 get split into two parameter 
	dictionaries and therefore two spock jobs """
	# print(db_lightsheet.request.Sample())
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-atlas_name':'allen_2017',
		'image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'submit':True
		}
	username = "ahoag"
	request_name = "admin_multichannel_request"
	sample_name = "sample-001"
	imaging_request_number = 1
	processing_request_number = 1
	response = test_client.post(url_for('processing.processing_entry',
			username=username,request_name=request_name,sample_name=sample_name,
			imaging_request_number=imaging_request_number,
			processing_request_number=processing_request_number),
		data=data,
		follow_redirects=True)
	assert b"core facility requests" in response.data
	assert b"Processing entry form" not in response.data

	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
			f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' & \
			f'processing_request_number="{processing_request_number}"'
	processing_progress = processing_request_contents.fetch1('processing_progress')
	assert processing_progress == 'running'
	# print(db_admin.SpockJobManager())
	# assert b'Your data processing has begun. You will receive an email when the first steps are completed.' in response.data	

	# imaging_progress = (db_lightsheet.Request.ImagingRequest() & 'request_name="admin_request"' & \
	# 	'username="ahoag"' & 'sample_name="sample-001"' & 'imaging_request_number=1').fetch1('imaging_progress')
	# assert imaging_progress == 'complete'

def test_processing_admin_access_processing_entry_for_nonadmin(test_client,test_imaged_request_nonadmin,):
	""" Test that zmd cannot  access the processing entry form
	for lightserv-test request"""
	with test_client.session_transaction() as sess:
		sess['user'] = 'zmd'
	response = test_client.get(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		, follow_redirects=True)
	print(db_lightsheet.Request.ProcessingRequest())
	assert b'The processor has already been assigned for this entry and you are not them' in response.data
	assert b'Welcome to the Brain Registration and Histology Core Facility' in response.data 

def test_processing_admin_submit_processing_entry_for_nonadmin(test_client,test_imaged_request_nonadmin,):
	""" Test that lightserv-test can access the processing entry form
	for his request"""
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'


	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-atlas_name':'allen_2017',
		'image_resolution_forms-0-image_resolution':'1.3x',
		'submit':True
		}
	username='lightserv-test'
	request_name='nonadmin_request'
	sample_name='sample-001'
	imaging_request_number=1
	processing_request_number=1
	response = test_client.post(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		,data=data,
		follow_redirects=True)
	
	assert b"core facility requests" in response.data
	assert b"Processing entry form" not in response.data

	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
			f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' & \
			f'processing_request_number="{processing_request_number}"'
	processing_progress = processing_request_contents.fetch1('processing_progress')
	assert processing_progress == 'running'

def test_submit_processing_entry_generic_imaging_nonadmin(test_client,test_imaged_request_generic_imaging_nonadmin):
	""" Test that lightserv-test can access the processing entry form
	for his request"""
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'

	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'555',
		'image_resolution_forms-0-atlas_name':'allen_2017',
		'image_resolution_forms-0-image_resolution':'1.3x',
		'submit':True
		}
	username='lightserv-test'
	request_name='nonadmin_request'
	sample_name='sample-001'
	imaging_request_number=1
	processing_request_number=1
	response = test_client.post(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		,data=data,
		follow_redirects=True)
	
	assert b"core facility requests" in response.data
	assert b"Processing entry form" not in response.data

	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
			f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' & \
			f'processing_request_number="{processing_request_number}"'
	processing_progress = processing_request_contents.fetch1('processing_progress')
	assert processing_progress == 'running'

# def test_submit_processing_entry_4x_nonadmin(test_client,test_imaged_4x_request_nonadmin):
# 	""" Test that lightserv-test can submit their 4x processing request"""
# 	with test_client.session_transaction() as sess:
# 		sess['user'] = 'lightserv-test'
# 	data = {
# 		'image_resolution_forms-0-image_resolution':'4x',
# 		'image_resolution_forms-0-channel_forms-0-channel_name':'647',
# 		'submit':True
# 		}
# 	username='lightserv-test'
# 	request_name='test2'
# 	sample_name='test2-001'
# 	imaging_request_number=1
# 	processing_request_number=1
# 	response = test_client.post(url_for('processing.processing_entry',
# 		username=username,request_name=request_name,sample_name=sample_name,
# 		imaging_request_number=imaging_request_number,
# 		processing_request_number=processing_request_number)
# 		,data=data,
# 		follow_redirects=True)
	
# 	assert b"core facility requests" in response.data
# 	assert b"Processing entry form" not in response.data

# 	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
# 			f'request_name="{request_name}"' & \
# 			f'username="{username}"' & f'sample_name="{sample_name}"' & \
# 			f'imaging_request_number="{imaging_request_number}"' & \
# 			f'processing_request_number="{processing_request_number}"'
# 	processing_progress = processing_request_contents.fetch1('processing_progress')
# 	assert processing_progress == 'running'

def test_processing_entry_form_shows_readonly_if_already_submitted(test_client,processing_request_nonadmin):
	""" Test that the processing entry form shows a flash message 
	that it is read only if the processing request has already been submitted
	"""
	response = test_client.get(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		, follow_redirects=True)

	assert b'Processing Entry Form' in response.data
	assert b'nonadmin_request' in response.data 
	warning_message = ("Processing is running for this sample. "
			"This page is read only and hitting submit will do nothing")
	assert warning_message.encode('utf-8') in response.data 

def test_processing_entry_form_redirects_on_post_if_already_submitted(test_client,processing_request_nonadmin):
	""" Test that the processing entry form redirects 
	to the processing manager if a post request is received and the entry 
	form has already been submitted in the past. 
	"""
	response = test_client.post(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1),
		data = {
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'image_resolution_forms-0-atlas_name':'allen_2017',
			'image_resolution_forms-0-image_resolution':'1.3x',
			'submit':True
		}, follow_redirects=True)

	assert b'Processing management GUI' in response.data
	warning_message = ("Processing is running for this sample.  " 
                       "It cannot be re-processed. To open a new processing request, " 
                       "see your request page") 
	assert warning_message.encode('utf-8') in response.data

def test_new_channel_added_visible_in_processing_entry_form(test_client,test_imaged_request_nonadmin_new_channel_added,):
	""" Test that lightserv-test can submit processing for the original channel as well as the channel 
	that was added by zmd (555) in the imaging entry form"""
	import time
	from lightserv.processing import tasks

	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'image_resolution_forms-0-atlas_name':'allen_2017',
		'image_resolution_forms-0-image_resolution':'1.3x',
		'submit':True
		}

	username = "lightserv-test"
	request_name = "nonadmin_request"
	sample_name = "sample-001"
	imaging_request_number = 1
	processing_request_number = 1
	response = test_client.post(url_for('processing.processing_entry',
			username=username,request_name=request_name,sample_name=sample_name,
			imaging_request_number=imaging_request_number,
			processing_request_number=processing_request_number),
		data=data,
		follow_redirects=True)
	assert b"core facility requests" in response.data
	assert b"Processing entry form" not in response.data

	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
			f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' & \
			f'processing_request_number="{processing_request_number}"'
	processing_progress = processing_request_contents.fetch1('processing_progress')
	assert processing_progress == 'running'
	""" Make sure ProcessingChannel() entry gets created for channel 555 """

	kwargs = dict(username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number)
	
	all_channel_contents = db_lightsheet.Request.ImagingChannel() & f'username="{username}"' \
		& f'request_name="{request_name}"'  & f'sample_name="{sample_name}"' & \
		f'imaging_request_number="{imaging_request_number}"'
	print(all_channel_contents)
	print("Starting light sheet pipeline job synchronously")
	tasks.run_lightsheet_pipeline.run(**kwargs)
	table_contents = db_spockadmin.ProcessingPipelineSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0
	# time.sleep(2) # sleep to allow celery task that starts light sheet pipeline to create the database entry
	processing_channel_contents = db_lightsheet.Request.ProcessingChannel() & \
		'request_name="nonadmin_request"' & 'username="lightserv-test"' & \
		'sample_name="sample-001"' & 'imaging_request_number=1' & \
		'processing_request_number=1' &	'channel_name="555"'
	assert len(processing_channel_contents) == 1
""" Tests for processing_table """

def test_ahoag_access_processing_table(test_client,processing_request_ahoag):
	""" Test that ahoag can access their processing table route
	after request has been processed"""
	with test_client.session_transaction() as sess:
		sess['user'] = "ahoag"
	username = "ahoag"
	request_name = "admin_request"
	sample_name = "sample-001"
	imaging_request_number = 1
	processing_request_number = 1
	response = test_client.get(url_for('processing.processing_table',
		username=username,request_name=request_name,sample_name=sample_name,
		imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number),
		follow_redirects=True)
	
	assert b"Processing Log" in response.data
	assert b"Processed channels:" in response.data


""" Tests for new_processing_request """

def test_access_new_processing_request_nonadmin(test_client,test_single_sample_request_nonadmin):
	""" Test that the new processing request page loads OK 

	Uses test_single_sample_request_nonadmin to make a single request with a single 
	sample for setup

	"""
	response = test_client.get(url_for('processing.new_processing_request',
			username='lightserv-test',request_name='nonadmin_request',
			sample_name='sample-001',imaging_request_number=1),
		follow_redirects=True
		)
	assert b"New Image Processing Request" in response.data

def test_submit_new_processing_request_nonadmin(test_client,test_single_sample_request_nonadmin):
	""" Test that the new processing request form submits OK

	Uses test_single_sample_request_nonadmin to make a single request with a single 
	sample for setup

	"""

	response = test_client.post(url_for('processing.new_processing_request',
			username='lightserv-test',request_name='nonadmin_request',
			sample_name='sample-001',imaging_request_number=1),
			data={
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-atlas_name':'princeton_mouse_atlas',
			'submit':True
		},
		follow_redirects=True
		)
	assert b"New Image Processing Request" not in response.data
	assert b"Processing request successfully submitted." in response.data
	assert b'Processing management GUI' in response.data

def test_new_processing_request_nonadmin_validates(test_client,test_single_sample_request_nonadmin):
	""" Test that the new processing request route validates when
	the form is submitted with bad data

	Uses test_single_sample_request_nonadmin to make a single request with a single 
	sample for setup

	"""

	response = test_client.post(url_for('processing.new_processing_request',
			username='lightserv-test',request_name='nonadmin_request',
			sample_name='sample-001',imaging_request_number=1),
			data={
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-atlas_name':'princeton_mouse_atlas',
			'image_resolution_forms-0-notes_for_processor':lorem.text()*2,
			'submit':True
		},
		follow_redirects=True
		)
	assert b"There were errors below. Correct them before proceeding" in response.data
	assert b"Field cannot be longer than 1024 characters" in response.data
	assert b"New Image Processing Request" in response.data


	response2 = test_client.post(url_for('processing.new_processing_request',
			username='lightserv-test',request_name='nonadmin_request',
			sample_name='sample-001',imaging_request_number=1),
			data={
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-atlas_name':'princeton_mouse_atlas',
			'notes_from_processing':lorem.text()*2,
			'submit':True
		},
		follow_redirects=True
		)
	assert b"There were errors below. Correct them before proceeding" in response2.data
	assert b"Field cannot be longer than 1024 characters" in response2.data
	assert b"New Image Processing Request" in response2.data

""" Tests for processing utils """

def test_determine_status_code():
	""" Test that the new processing request route validates when
	the form is submitted with bad data

	Uses test_single_sample_request_nonadmin to make a single request with a single 
	sample for setup

	"""
	from lightserv.processing.utils import determine_status_code

	# if all are same then return the one code that is duplicated
	status_codes1 = ['COMPLETED','COMPLETED']
	status_code1 = determine_status_code(status_codes1)
	assert status_code1 == 'COMPLETED'
	# if none have failed but all are not the same then status should be RUNNING
	status_codes2 = ['PENDING','PENDING','RUNNING','COMPLETED']
	status_code2 = determine_status_code(status_codes2)
	assert status_code2 == 'RUNNING'
	# if any are problematic, return failed
	status_codes3 = ['PENDING','PENDING','RUNNING','CANCELLED']
	status_code3 = determine_status_code(status_codes3)
	assert status_code3 == 'FAILED'
	# if only 1 status code then just return that value
	status_codes4 = ['PENDING']
	status_code4 = determine_status_code(status_codes4)
	assert status_code4 == 'PENDING'
	# if CANCELLED by {UID} is the status code then just return CANCELLED
	status_codes5 = ['CANCELLED by 1234']
	status_code5 = determine_status_code(status_codes5)
	assert status_code5 == 'CANCELLED'

""" Test for processing tasks """

def test_lightsheet_pipeline_starts(test_client,test_imaged_request_viz_nonadmin):
	""" Test that the light sheet pipeline starts,
	given the correct input. Uses a test script on spock which just returns
	job ids. Runs a celery task """
	from lightserv.processing import tasks
	import time
	username='lightserv-test'
	request_name='viz_processed'
	sample_name='viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	kwargs = dict(username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number)
	all_channel_contents = db_lightsheet.Request.ImagingChannel() & f'username="{username}"' \
		& f'request_name="{request_name}"'  & f'sample_name="{sample_name}"' & \
		f'imaging_request_number="{imaging_request_number}"'
	print(all_channel_contents)
	# assert 4==4
	tasks.run_lightsheet_pipeline.delay(**kwargs)
	time.sleep(2)
	table_contents = db_spockadmin.ProcessingPipelineSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0

def test_stitched_precomputed_pipeline_starts(test_client,):
	""" Test that the stitched precomputed pipeline task runs through,
	given the correct input. Uses a test script on spock which just returns
	job ids. Runs a celery task """
	from lightserv.processing import tasks
	import time
	username='lightserv-test'
	request_name='tracing_test'
	sample_name='tracing_test-001'
	imaging_request_number=1
	processing_request_number=1
	image_resolution='4x'
	channel_name='647'
	channel_index=0
	number_of_z_planes=682
	lightsheet='left'
	left_lightsheet_used=True
	right_lightsheet_used=False
	z_step=2
	rawdata_subfolder='test647'
	processing_pipeline_jobid_step0=12345678 # just some dummy number
	stitched_viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
							 f"{request_name}/{sample_name}/"
							 f"imaging_request_{imaging_request_number}/viz/"
							 f"processing_request_{processing_request_number}/"
							 f"stitched_raw")
	channel_viz_dir = os.path.join(stitched_viz_dir,f'channel_{channel_name}')
	this_viz_dir = os.path.join(channel_viz_dir,'left_lightsheet')

	precomputed_kwargs = dict(
				username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number,
				image_resolution=image_resolution,channel_name=channel_name,
				channel_index=channel_index,
				rawdata_subfolder=rawdata_subfolder,
				left_lightsheet_used=left_lightsheet_used,
				right_lightsheet_used=right_lightsheet_used,
				processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
				z_step=z_step,lightsheet='left',viz_dir=this_viz_dir)
	
	tasks.make_precomputed_stitched_data.delay(**precomputed_kwargs) 
	time.sleep(2)
	table_contents = db_spockadmin.StitchedPrecomputedSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0

def test_blended_precomputed_pipeline_starts(test_client,):
	""" Test that the blended precomputed pipeline task runs through,
	given the correct input. Uses a test script on spock which just returns
	job ids. Runs a celery task """
	from lightserv.processing import tasks
	import time
	username='lightserv-test'
	request_name='viz_processed'
	sample_name='viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	image_resolution='1.3x'
	channel_name='488'
	channel_index=0
	left_lightsheet_used=True
	right_lightsheet_used=False
	z_step=5
	rawdata_subfolder='test488'
	processing_pipeline_jobid_step0=12345679 # just some dummy number
	data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
	channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
	blended_data_path = os.path.join(data_bucket_rootpath,username,
					 request_name,sample_name,
					 f"imaging_request_{imaging_request_number}",
					 "output",
					 f"processing_request_{processing_request_number}",
					 f"resolution_{image_resolution}",
					 "full_sizedatafld",
					 f"{rawdata_subfolder}_ch{channel_index_padded}")
	blended_viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
							 f"{request_name}/{sample_name}/"
							 f"imaging_request_{imaging_request_number}/viz/"
							 f"processing_request_{processing_request_number}/"
							 f"blended")
	channel_viz_dir = os.path.join(blended_viz_dir,f'channel_{channel_name}')
	precomputed_kwargs = dict(
				username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number,
				image_resolution=image_resolution,channel_name=channel_name,
				channel_index=channel_index,
				processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
				z_step=z_step,blended_data_path=blended_data_path)

	precomputed_kwargs['viz_dir'] = channel_viz_dir
	tasks.make_precomputed_blended_data.delay(**precomputed_kwargs)

	time.sleep(2)
	table_contents = db_spockadmin.BlendedPrecomputedSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0

def test_downsized_precomputed_pipeline_starts(test_client,):
	""" Test that the downsized precomputed pipeline task runs through,
	given the correct input. Uses a test script on spock which just returns
	job ids. Runs a celery task """
	from lightserv.processing import tasks
	import time
	username='lightserv-test'
	request_name='viz_processed'
	sample_name='viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	image_resolution='1.3x'
	channel_name='488'
	channel_index=0
	left_lightsheet_used=True
	right_lightsheet_used=False
	z_step=5
	rawdata_subfolder='test488'
	processing_pipeline_jobid_step0=12345680 # just some dummy number
	data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
	atlas_name='princeton_mouse_atlas'
	downsized_data_path = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "output",
							 f"processing_request_{processing_request_number}",
							 f"resolution_{image_resolution}")
	precomputed_kwargs = dict(
				username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number,
				image_resolution=image_resolution,channel_name=channel_name,
				channel_index=channel_index,rawdata_subfolder=rawdata_subfolder,
				processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
				downsized_data_path=downsized_data_path,atlas_name=atlas_name)
	downsized_viz_dir = os.path.join(data_bucket_rootpath,username,
					 request_name,sample_name,
					 f"imaging_request_{imaging_request_number}",
					 "viz",
					 f"processing_request_{processing_request_number}",
					 "downsized")
	channel_viz_dir = os.path.join(downsized_viz_dir,
				f'channel_{channel_name}')
	precomputed_kwargs['viz_dir'] = channel_viz_dir
	tasks.make_precomputed_downsized_data.delay(**precomputed_kwargs)
	time.sleep(2)
	table_contents = db_spockadmin.DownsizedPrecomputedSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0

def test_registered_precomputed_pipeline_starts(test_client,):
	""" Test that the downsized precomputed pipeline task runs through,
	given the correct input. Uses a test script on spock which just returns
	job ids. Runs a celery task """
	from lightserv.processing import tasks
	import time
	username='lightserv-test'
	request_name='viz_processed'
	sample_name='viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	image_resolution='1.3x'
	channel_name='488'
	channel_index=0
	lightsheet_channel_str='regch'	
	z_step=5
	rawdata_subfolder='test488'
	processing_pipeline_jobid_step0=12345684 # just some dummy number
	data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
	atlas_name='princeton_mouse_atlas'
	
	registered_data_path = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "output",
							 f"processing_request_{processing_request_number}",
							 f"resolution_{image_resolution}",
							 "elastix")

	""" number of z planes could be altered in the case of tiling due to terastitcher 
	so we will calculate it on the fly when doing the precomputed steps """
	precomputed_kwargs = dict(
		username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number,
		image_resolution=image_resolution,channel_name=channel_name,
		channel_index=channel_index,
		lightsheet_channel_str=lightsheet_channel_str,
		rawdata_subfolder=rawdata_subfolder,
		atlas_name=atlas_name,
		processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
		registered_data_path=registered_data_path)

	registered_viz_dir = os.path.join(data_bucket_rootpath,username,
					 request_name,sample_name,
					 f"imaging_request_{imaging_request_number}",
					 "viz",
					 f"processing_request_{processing_request_number}",
					 "registered")
	channel_viz_dir = os.path.join(registered_viz_dir,
		f'channel_{channel_name}_{lightsheet_channel_str}')
	precomputed_kwargs['viz_dir'] = channel_viz_dir
	layer_name = f'channel{channel_name}_registered'
	precomputed_kwargs['layer_name'] = layer_name

	tasks.make_precomputed_registered_data.delay(**precomputed_kwargs)
	time.sleep(2)
	table_contents = db_spockadmin.RegisteredPrecomputedSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0
