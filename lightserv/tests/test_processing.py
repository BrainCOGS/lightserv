from flask import url_for
import tempfile
import webbrowser
from lightserv import db_lightsheet, db_admin
from bs4 import BeautifulSoup 
from datetime import datetime

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
	""" Test that lightserv-test can access the processing entry form
	for his request"""
	with test_client.session_transaction() as sess:
		sess['user'] = 'zmd'
	response = test_client.get(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		, follow_redirects=True)
	print(db_lightsheet.Request.ProcessingRequest())
	assert b'Processing Entry Form' in response.data
	assert b'nonadmin_request' in response.data 

def test_processing_admin_submit_processing_entry_for_nonadmin(test_client,test_imaged_request_nonadmin,):
	""" Test that lightserv-test can access the processing entry form
	for his request"""
	with test_client.session_transaction() as sess:
		sess['user'] = 'zmd'


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