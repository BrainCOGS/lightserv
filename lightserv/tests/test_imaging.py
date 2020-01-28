from flask import url_for
import tempfile
import webbrowser
from lightserv import db_lightsheet
from bs4 import BeautifulSoup 
from datetime import datetime

""" Tests for Imaging Manager """
def test_ahoag_access_imaging_manager(test_client,test_cleared_request_ahoag):
	""" Test that ahoag can access the imaging task manager
	and see the single entry made and cleared by ahoag  """
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'admin_request' in response.data 

def test_nonadmin_access_imaging_manager(test_client,test_cleared_request_ahoag,test_login_nonadmin):
	""" Test that Manuel (lightserv-test, a nonadmin) can access the imaging task manager
	but cannot see his entry because he did not designate himself as the imager
	and cannot see ahoag's entry because he is a not an imaging admin. """
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'nonadmin_request' not in response.data 
	# assert b'admin_request' not in response.data 

def test_zmd_access_imaging_manager(test_client,test_cleared_request_ahoag,
	test_cleared_request_nonadmin,test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can access the imaging task manager
	and see entries made by multiple users """
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'admin_request' in response.data 
	assert b'nonadmin_request' in response.data 

def test_multichannel_imaging_worked(test_client,test_imaged_multichannel_request_ahoag):
	""" Test that the multi channel imaging fixture worked: 
	test_imaged_multichannel_request_ahoag """
	# print(db_lightsheet.Request.Sample())
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'admin_multichannel_request' in response.data 

""" Tests for imaging entry form """

def test_imaging_entry_form_loads(test_client,test_cleared_request_ahoag,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can access the imaging entry form
	for a test sample """
	response = test_client.get(url_for('imaging.imaging_entry',
		username='ahoag',request_name='admin_request',sample_name='sample-001',
		imaging_request_number=1)
		, follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	assert b'admin_request' in response.data 
	# assert b'nonadmin_request' in response.data 

def test_imaging_entry_form_submits(test_client,test_cleared_request_ahoag,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can submit the imaging entry form
	for a test sample """
	from lightserv import db_lightsheet
	# print(db_lightsheet.Request.ImagingRequest())
	print(db_lightsheet.Request.ImagingChannel())
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
	assert b'Request overview:' in response.data
	assert b'Samples in this request:' in response.data 

	imaging_progress = (db_lightsheet.Request.ImagingRequest() & 'request_name="admin_request"' & \
		'username="ahoag"' & 'sample_name="sample-001"' & 'imaging_request_number=1').fetch1('imaging_progress')
	assert imaging_progress == 'complete'

def test_tiling_scheme_validation(test_client,test_cleared_request_ahoag,
	test_login_zmd):
	""" Test that an incorrect tiling scheme format raises 
	the intended validation error """

	data1 = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x11',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response1 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data1,
		follow_redirects=True)
	assert b'Tiling scheme is not in correct format. Make sure it is like: 1x1 with no spaces.' in response1.data


	data2= {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'gx2',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response2 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data2,
		follow_redirects=True)
	assert b'Tiling scheme is not in correct format. Make sure it is like: 1x1 with no spaces.' in response2.data

	data3= {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'4x4',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response3 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data3,
		follow_redirects=True)
	assert b'Tiling scheme must not exceed 2x2 for this resolution' in response3.data

def test_tiling_scheme_validation_4x(test_client,test_cleared_request_4x_ahoag,
	test_login_zmd):
	""" Test that an incorrect tiling scheme format raises 
	the intended validation error """

	data1 = {
		'image_resolution_forms-0-image_resolution':'4x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'4x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x11',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response1 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='Admin_4x_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data1,
		follow_redirects=True)
	assert b'Tiling scheme is not in correct format. Make sure it is like: 1x1 with no spaces.' in response1.data


	data2= {
		'image_resolution_forms-0-image_resolution':'4x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'4x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'gx2',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response2 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='Admin_4x_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data2,
		follow_redirects=True)
	assert b'Tiling scheme is not in correct format. Make sure it is like: 1x1 with no spaces.' in response2.data

	data3= {
		'image_resolution_forms-0-image_resolution':'4x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'4x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'4x6',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response3 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='Admin_4x_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data3,
		follow_redirects=True)
	assert b'Tiling scheme must not exceed 4x4 for this resolution' in response3.data

def test_tiling_overlap_validation(test_client,test_cleared_request_ahoag,
	test_login_zmd):
	""" Test that an incorrect tiling overlap raises 
	the intended validation error """

	data1 = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':-0.4,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response1 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data1,
		follow_redirects=True)
	assert b'Tiling overlap must be a number between 0.0 and 1.0' in response1.data

	data2 = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':'gg',
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response2 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data2,
		follow_redirects=True)
	assert b'Tiling overlap must be a number between 0.0 and 1.0' in response2.data

def test_z_step_validation(test_client,test_cleared_request_ahoag,
	test_login_zmd):
	""" Test that an incorrect z resolution gives
	the intended validation error """

	data1 = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':1,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response1 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data1,
		follow_redirects=True)
	assert b'z_step must be a positive number larger than 2 microns' in response1.data

	data2 = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':1001,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response2 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data2,
		follow_redirects=True)
	assert b'z_step greater than 1000 microns is not supported by the microscope.' in response2.data
	
def test_number_of_z_planes_validation(test_client,test_cleared_request_ahoag,
	test_login_zmd):
	""" Test that an incorrect number of z planes gives
	the intended validation error """

	data1 = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':0,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response1 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data1,
		follow_redirects=True)
	assert b'The number of z planes must be a positive number' in response1.data

	data2 = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':5501,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response2 = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data2,
		follow_redirects=True)
	assert b'More than 5500 z planes is not supported by the microscope.' in response2.data
	
def test_bad_imaging_request_redirects(test_client,test_cleared_request_ahoag,
	test_login_zmd):
	""" Test that trying to access the imaging entry form for an
	imaging request that does not exist
	redirects the user to the all requests form and puts up a flash message.
	"""

	response = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=8),
		follow_redirects=True)
	assert b'No imaging request exists with those parameters. Please try again.' in response.data
	assert b'core facility requests:' in response.data

def test_access_already_imaged_request_ahoag(test_client,test_imaged_request_ahoag):
	""" Test that accessing the imaging entry form 
	that has already been completed results in a flash message
	saying so  """

	
	response = test_client.get(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		follow_redirects=True)

	test_str = ("Imaging is already complete for this sample. " 
			    "This page is read only and hitting submit will do nothing")
	assert test_str.encode('utf-8') in response.data

def test_post_request_already_imaged_request_ahoag(test_client,test_imaged_request_ahoag):
	""" Test that trying to hit buttons in the imaging entry form 
	that has already been completed results in a flash message
	saying so and does not submit the form """
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
		'submit':True
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)

	test_str = ("Imaging is already complete for this sample. " 
			    "This page is read only and hitting submit will do nothing")
	assert test_str.encode('utf-8') in response.data
	assert b"Imaging Entry Form" in response.data

def test_no_right_lightsheet_submits(test_client,test_cleared_request_ahoag,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can submit the imaging entry form
	for a test sample with only the left lightsheet and the right light sheet
	is set to false in the db """
	from lightserv import db_lightsheet
	# print(db_lightsheet.Request.ImagingRequest())
	print(db_lightsheet.Request.ImagingChannel())
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
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
	assert b'Request overview:' in response.data
	assert b'Samples in this request:' in response.data 

	imaging_progress = \
	(db_lightsheet.Request.ImagingRequest() & 'request_name="admin_request"' & \
		'username="ahoag"' & 'sample_name="sample-001"' & \
		'imaging_request_number=1').fetch1(
			'imaging_progress')

	assert imaging_progress == 'complete'
	left_lightsheet_used,right_lightsheet_used =\
	(db_lightsheet.Request.ImagingChannel() & 'request_name="admin_request"' & \
		'username="ahoag"' & 'sample_name="sample-001"' & \
		'imaging_request_number=1' & 'channel_name="488"').fetch1(
			'left_lightsheet_used','right_lightsheet_used')
	assert left_lightsheet_used == True
	assert right_lightsheet_used == False

def test_no_lightsheets_validation_error(test_client,test_cleared_request_ahoag,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) cannot submit the imaging entry form
	for a test sample if she does not check the left lightsheet or right light sheet
	checkboxes
	"""
	from lightserv import db_lightsheet
	# print(db_lightsheet.Request.ImagingRequest())
	print(db_lightsheet.Request.ImagingChannel())
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-z_step':10,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':500,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data

	error_str = ("Image resolution: 1.3x, Channel: 488: "
				 "At least one light sheet needs to be selected")
	assert error_str.encode('utf-8') in response.data

def test_multichannel_imaging_entry_form_submits(test_client,test_cleared_multichannel_request_ahoag,
	test_login_zmd):
	""" Test that the multi-channel imaging entry submits 
	when all of the imaging parameters are identical for both channels
	in same rawdata subfolder """
	from lightserv import db_lightsheet
	# print(db_lightsheet.Request.ImagingRequest())
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
		'image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'image_resolution_forms-0-channel_forms-1-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-1-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-1-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-1-z_step':10,
		'image_resolution_forms-0-channel_forms-1-number_of_z_planes':657,
		'image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test488',
		'submit':True
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_multichannel_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	assert b'Request overview:' in response.data
	assert b'Samples in this request:' in response.data 

	imaging_progress = (db_lightsheet.Request.ImagingRequest() & 'request_name="admin_multichannel_request"' & \
		'username="ahoag"' & 'sample_name="sample-001"' & 'imaging_request_number=1').fetch1('imaging_progress')
	assert imaging_progress == 'complete'

def test_multichannel_imaging_entry_form_validates(test_client,test_cleared_multichannel_request_ahoag,
	test_login_zmd):
	""" Test that a validation error is raised when 
	two channels in the same rawdata subfolder are 
	entered as having different imaging parameters"""
	from lightserv import db_lightsheet
	# print(db_lightsheet.Request.ImagingRequest())
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
		'image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'image_resolution_forms-0-channel_forms-1-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x',
		'image_resolution_forms-0-channel_forms-1-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-1-tiling_overlap':0.3,
		'image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-1-z_step':10,
		'image_resolution_forms-0-channel_forms-1-number_of_z_planes':657,
		'image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test488',
		'submit':True
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_multichannel_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	assert b'Request overview:' not in response.data
	assert b'Imaging Entry Form' in response.data 
	validation_str = 'Subfolder: test488. Tiling and imaging parameters must be identical for all channels in the same subfolder. Check your entries.'
	assert validation_str.encode('utf-8') in response.data

""" Tests for New imaging request """	

def test_new_imaging_request(test_client,test_single_sample_request_ahoag):
	""" Check that a new imaging request submits successfully

	Uses the test_single_sample_request_ahoag fixture
	to insert a request into the database as ahoag. 

	"""
	response = test_client.post(
				url_for('imaging.new_imaging_request',username='ahoag',request_name='admin_request',
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
	assert b'core facility requests' in response.data	
	assert b'New Imaging Request' not in response.data

def test_new_imaging_request_image_resolution_form_submit(test_client,test_single_sample_request_ahoag):
	""" Test that hitting the new image resolution button works

	Uses the test_single_sample_request_ahoag fixture
	to insert a request into the database as ahoag. 

	"""
	response1 = test_client.post(
				url_for('imaging.new_imaging_request',username='ahoag',request_name='admin_request',
					sample_name='sample-001'),
				data={
					'image_resolution_forsetup':'1.3x',
					'new_image_resolution_form_submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b'New Imaging Request' in response1.data
	assert b'Setup for image resolution: 1.3x' in response1.data
	
def test_new_imaging_request_image_resolution_forms_validation(test_client,test_single_sample_request_ahoag):
	""" Test that the validation errors that need to be raised 
	in the image resolution form are raised 

	Uses the test_single_sample_request_ahoag fixture
	to insert a request into the database as ahoag. 

	"""
	response1 = test_client.post(
				url_for('imaging.new_imaging_request',username='ahoag',request_name='admin_request',
					sample_name='sample-001'),
				data={
					'image_resolution_forms-0-image_resolution':'1.3x',
					'image_resolution_forms-0-atlas_name':'allen_2017',
					'image_resolution_forms-0-final_orientation':'sagittal',
					'image_resolution_forsetup':'1.3x',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b'New Imaging Request' in response1.data
	assert b'The image resolution table: 1.3x is empty. Please select at least one option.' in response1.data

	response2 = test_client.post(
				url_for('imaging.new_imaging_request',username='ahoag',request_name='admin_request',
					sample_name='sample-001'),
				data={
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b'New Imaging Request' in response2.data
	assert b'You must set up the imaging parameters for at least one image resolution' in response2.data

	response3 = test_client.post(
				url_for('imaging.new_imaging_request',username='ahoag',request_name='admin_request',
					sample_name='sample-001'),
				data={
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-atlas_name':'allen_2017',
			'image_resolution_forms-0-final_orientation':'sagittal',
			'image_resolution_forsetup':'1.3x',
			'image_resolution_forms-0-channels-0-injection_detection':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b'New Imaging Request' in response3.data
	test_str3 = ("Image resolution table: 1.3x. "
			"You must select a registration channel " 
			"when requesting any of the detection channels")
	assert test_str3.encode('utf-8') in response3.data


	response4 = test_client.post(
				url_for('imaging.new_imaging_request',username='ahoag',request_name='admin_request',
					sample_name='sample-001'),
				data={
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-atlas_name':'allen_2017',
			'image_resolution_forms-0-final_orientation':'sagittal',
			'image_resolution_forsetup':'1.3x',
			'image_resolution_forms-0-channels-0-registration':True,
			'image_resolution_forsetup':'1.3x',
			'new_image_resolution_form_submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b'New Imaging Request' in response4.data
	test_str4 = ("You tried to make a table for image_resolution: 1.3x"
				", but that resolution has already been picked")
	assert test_str4.encode('utf-8') in response4.data

def test_new_imaging_request_self_imaging(test_client,test_single_sample_request_ahoag):
	""" Test that hitting the new image resolution button works
	Uses the test_single_sample_request_ahoag fixture
	to insert a request into the database as ahoag. 
	"""
	from lightserv import db_lightsheet
	response = test_client.post(
				url_for('imaging.new_imaging_request',username='ahoag',request_name='admin_request',
					sample_name='sample-001'),
				data={
			'self_imaging':True,
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-atlas_name':'allen_2017',
			'image_resolution_forms-0-final_orientation':'sagittal',
			'image_resolution_forsetup':'1.3x',
			'image_resolution_forms-0-channels-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	imager_request2 = (db_lightsheet.Request.ImagingRequest() & 'username="ahoag"' & \
		f'request_name="admin_request"' & 'sample_name="sample-001"' & 
		'imaging_request_number=2').fetch1('imager')
	assert imager_request2 == 'ahoag'
	assert b'core facility requests' in response.data	
	assert b'New Imaging Request' not in response.data	

def test_new_imaging_request_final_orientation_sagittal_if_registration(test_client,test_single_sample_request_ahoag):
	""" Ensure that a validation error is raised is user tries
	to submit a request where output orientation is not sagittal
	but they requested registration. 

	Uses the test_single_sample_request_ahoag fixture
	to insert a request into the database as ahoag. 

	"""
	response = test_client.post(
				url_for('imaging.new_imaging_request',username='ahoag',request_name='admin_request',
					sample_name='sample-001'),
				data={
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-atlas_name':'allen_2017',
			'image_resolution_forms-0-final_orientation':'coronal',
			'image_resolution_forsetup':'1.3x',
			'image_resolution_forms-0-channels-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	
	assert b'New Imaging Request' in response.data
	assert b'core facility requests' not in response.data	
	assert b'Output orientation must be sagittal since registration was selected' in response.data 

def test_new_imaging_rat_request_only_generic_imaging_allowed(test_client,test_login,test_cleared_rat_request):
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
		url_for('imaging.new_imaging_request',username="lightserv-test",
			request_name="Nonadmin_rat_request",
			sample_name="sample-001"),data={
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-atlas_name':'allen_2017',
			'image_resolution_forms-0-final_orientation':'sagittal',
			'image_resolution_forsetup':'1.3x',
			'image_resolution_forms-0-channels-0-registration':True,
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"Only generic imaging is currently available" in response1.data
	assert b"New Imaging Request" in response1.data
