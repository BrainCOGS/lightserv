from flask import url_for, current_app,Markup	
import os, shutil, glob
from PIL import Image
import tempfile
import webbrowser
from lightserv import db_lightsheet, db_spockadmin
from bs4 import BeautifulSoup 
from datetime import datetime

""" Tests for Imaging Manager """

def test_ahoag_access_imaging_manager(test_client,test_cleared_request_ahoag):
	""" Test that ahoag can access the imaging task manager
	and see the single entry s and cleared by ahoag  """
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

def test_nonadmin_can_see_self_imaging_request(test_client,test_self_cleared_request_nonadmin):
	""" Test that lightserv-test, a nonadmin can see their 
	request in which they designated themselves as the clearer and imager 
	"""
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'self_clearing_and_imaging_request' in response.data 
	# assert b'admin_request' not in response.data 

def test_admin_can_see_self_imaging_request(test_client,test_self_cleared_request_nonadmin,test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can see the
	sample for which lightserv-test, a nonadmin designated themselves the imager.
	"""
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'self_clearing_and_imaging_request' in response.data 
	# assert b'admin_request' not in response.data 

def test_ahoag_multiple_imaging_requests_imaging_manager(test_client,test_cleared_two_imaging_requests_ahoag):
	""" Test that ahoag can access the imaging task manager
	and see both of their imaging requests  """
	# First log ahoag back in
	with test_client.session_transaction() as sess:
		sess['user'] = 'ahoag'
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'admin_request' in response.data 

	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag = parsed_html.find('table',
		attrs={'id':'horizontal_ready_to_image_table'})
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

def test_imaged_viz_fixture_worked(test_client,test_imaged_request_viz_nonadmin):
	""" Test that zmd can access the imaging task manager
	and see both of their imaging requests  """
	with test_client.session_transaction() as sess:
		# have to log an imaging manager in because the imager was zmd, not the person who requested it
		sess['user'] = 'zmd'
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'viz_processed' in response.data 

def test_3p6x_clearing_worked(test_client,test_cleared_request_3p6x_smartspim_nonadmin):
	""" Test that lightserv-test can access the imaging task manager
	and see their imaging request """

	with test_client.session_transaction() as sess:
		# have to log an imaging manager in because the imager was zmd, not the person who requested it
		sess['user'] = 'zmd'
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'nonadmin_3p6x_smartspim_request' in response.data 

def test_2x_clearing_worked(test_client,test_cleared_request_2x_nonadmin):
	""" Test that lightserv-test can access the imaging task manager
	and see their imaging request and that there is no ProcessingRequest() in the database  """

	with test_client.session_transaction() as sess:
		# have to log an imaging manager in because the imager was zmd, not the person who requested it
		sess['user'] = 'zmd'
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'test_2x_nonadmin' in response.data 
	
def test_multisample_multichannel_request_in_imaging_manager(test_client,test_cleared_multisample_multichannel_request_nonadmin):
	""" Test that lightserv-test can access the imaging task manager
	and see their imaging request and that there is no ProcessingRequest() in the database  """

	with test_client.session_transaction() as sess:
		# have to log an imaging manager in because the imager was zmd, not the person who requested it
		sess['user'] = 'zmd'
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'nonadmin_manysamp_request' in response.data 

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
	assert b'Imaging management GUI' in response.data
	assert b'admin_request' in response.data 

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
		'submit':True
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
		'submit':True
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
		'submit':True
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
		'submit':True
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
		'submit':True
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
		'submit':True
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
		'submit':True
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
		'submit':True
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
		'image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-0-z_step':1,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':647,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'submit':True
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
		'submit':True
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
		'submit':True
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
		'submit':True
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

def test_access_already_imaged_request_nonadmin(test_client,test_imaged_request_nonadmin):
	""" Test that John D'uva (jduva), an imaging admin can access the
	imaging entry form that Zahra (zmd) has already completed.
	"""
	with test_client.session_transaction() as sess:
		sess['user'] = 'ahoag'
	response = test_client.get(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		follow_redirects=True)
	str1 = ("Imaging is already complete for this sample. " 
			    "This page is read only and hitting submit will do nothing")
	assert str1.encode('utf-8') in response.data
	str2 = ("While you have access to this page, "
			"you are not the primary imager "
			"so please proceed with caution")
	assert str2.encode('utf-8') in response.data

def test_user_attempt_to_access_imaging_entry_form_redirects(test_client,test_imaged_request_nonadmin):
	""" Test that user cannot access their own imaging entry form
	if someone else (zmd) has been assigned as the imager 
	"""

	response = test_client.get(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		follow_redirects=True)
	assert b'The imager has already been assigned for this entry and you are not them.' in response.data
	assert b'Request overview:' in response.data

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
		'submit':True
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='ahoag',request_name='admin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging management GUI' in response.data

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

def test_both_lightsheets_submit(test_client,test_cleared_request_both_lightsheets_nonadmin,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can submit the imaging entry form
	for a test sample which use both the left lightsheet and the right light sheet """
	from lightserv import db_lightsheet
	print(db_lightsheet.Request.ImagingChannel())
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'647',
		'image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-0-right_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-z_step':5,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':1261,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test647',
		'submit':True
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='two_sheets',sample_name='two_sheets-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging management GUI' in response.data

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
		'submit':True
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
	assert b'Imaging management GUI' in response.data

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

def test_admin_cannot_access_self_imaging_request(test_client,test_self_cleared_request_nonadmin,test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) cannot 
	access the imaging entry form for a sample that a user (admin or not)
	has designated themselves as a self-imager.
	"""
	response = test_client.get(url_for('imaging.imaging_entry',
		username='lightserv-test',request_name='self_clearing_and_imaging_request',
		sample_name='sample-001',
		imaging_request_number=1),
		follow_redirects=True)
	assert b'Welcome to the Brain Registration and Histology' in response.data 
	assert b'The imager has already been assigned for this entry' in response.data

def test_different_subfolders_validate_against_different_tiling(test_client,test_cleared_request_two_channels_nonadmin,
	test_login_zmd):
	""" Test that a validation error is raised when 
	two channels at the same resolution but in differet
	rawdata subfolders are entered as having different tiling parameters"""
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
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':1258,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'image_resolution_forms-0-channel_forms-1-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x',
		'image_resolution_forms-0-channel_forms-1-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-1-tiling_overlap':0.3,
		'image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'image_resolution_forms-0-channel_forms-1-z_step':10,
		'image_resolution_forms-0-channel_forms-1-number_of_z_planes':1258,
		'image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test647',
		'submit':True
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='two_channels',sample_name='two_channels-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	assert b'Request overview:' not in response.data
	assert b'Imaging Entry Form' in response.data 
	validation_str = 'All tiling parameters must be the same for each channel of a given resolution'
	assert validation_str.encode('utf-8') in response.data

def test_4x_multitile_request_submits(test_client,test_cleared_request_4x_multitile_nonadmin,
	test_login_zmd):
	""" Test that a 4x multi-tile request can be submitted """
	from lightserv import db_lightsheet
	data = {
		'image_resolution_forms-0-image_resolution':'4x',
		'image_resolution_forms-0-channel_forms-0-channel_name':'647',
		'image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_forms-0-channel_forms-0-tiling_scheme':'3x3',
		'image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_forms-0-channel_forms-0-right_lightsheet_used':False,
		'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_forms-0-channel_forms-0-z_step':2,
		'image_resolution_forms-0-channel_forms-0-number_of_z_planes':3051,
		'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test_647',
		'submit':True
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='4x_647_kelly',sample_name='4x_647_kelly-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'4x_647_kelly' in response.data 

def test_imaging_entry_form_submits_for_second_imaging_request(test_client,
	test_imaged_first_of_two_imaging_requests_ahoag,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can submit the imaging entry form
	for the second imaging request for a single sample """
	print(db_lightsheet.Request.ImagingRequest())

	# imaging_contents = db_lightsheet.Request.ImagingChannel() & 'imaging_request_number=1'
	# print(imaging_contents.fetch1(''))
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
			imaging_request_number=2),
		data=data,
		follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'admin_request' in response.data 

	imaging_progress_request_2 = (db_lightsheet.Request.ImagingRequest() & 'request_name="admin_request"' & \
		'username="ahoag"' & 'sample_name="sample-001"' & 'imaging_request_number=2').fetch1('imaging_progress')
	assert imaging_progress_request_2 == 'complete'

def test_imager_changes_resolution(test_client,
	test_cleared_request_nonadmin,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can change the image resolution
	in the imaging entry form and that this change is reflected in the database"""

	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-change_resolution':True,
		'image_resolution_forms-0-new_image_resolution':'1.1x',
		'image_resolution_forms-0-update_resolution_button':True
		}

	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	""" Verify that the new image resolution is reflected in the db """
	restrict_dict = {'username':'lightserv-test','request_name':'nonadmin_request',
		'sample_name':'sample-001','imaging_request_number':1}
	imaging_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & restrict_dict
	image_resolution_recovered = imaging_resolution_request_contents.fetch1('image_resolution')
	assert image_resolution_recovered == '1.1x'

	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict
	imaging_channel_image_resolution_recovered = imaging_channel_contents.fetch1('image_resolution')
	assert imaging_channel_image_resolution_recovered == '1.1x'
	# assert b'Imaging Entry Form' in response.data

def test_imager_submits_changed_resolution(test_client,test_request_resolution_switched_nonadmin,
	test_cleared_request_nonadmin,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can submit the imaging entry form
	after switching the image resolution from 1.3x to 1.1x"""
	data = {
		'image_resolution_forms-0-image_resolution':'1.1x',
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
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'admin_request' in response.data 

	imaging_progress = (db_lightsheet.Request.ImagingRequest() & 'request_name="nonadmin_request"' & \
		'username="lightserv-test"' & 'sample_name="sample-001"' & 'imaging_request_number=1').fetch1(
			'imaging_progress')
	assert imaging_progress == 'complete'

def test_imager_adds_channel(test_client,
	test_cleared_request_nonadmin,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can add a new imaging channel in 
	imaging entry form and this channel is added to the database"""
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-new_channel_dropdown':'555',
		'image_resolution_forms-0-new_channel_purpose':'injection_detection',
		'image_resolution_forms-0-new_channel_button': True,
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	""" Make sure we are still in imaging entry form """
	assert b'Imaging Entry Form' in response.data
	""" Make sure resolution table now reflects additional row """
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag = parsed_html.find('table',
		attrs={'id':'resolution_1.3x_table'})
	table_row_tags = table_tag.find_all('tr')
	print(table_row_tags)
	print(len(table_row_tags))
	assert len(table_row_tags) == 4 # header, 488, 555, row for adding a new channel
	header_row = table_row_tags[0].find_all('th')
	# channel_488_row = table_row_tags[1].find_all('td')
	channel_555_row = table_row_tags[2].find_all('td')
	assert channel_555_row[0].text == "555"
	""" Make sure new imaging entry exists in database for channel 555 """
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & 'request_name="nonadmin_request"' & \
		'username="lightserv-test"' & 'sample_name="sample-001"' & 'imaging_request_number=1' & \
		'channel_name="555"'
	assert len(imaging_channel_contents) == 1

def test_imager_adds_channel_then_submits(test_client,
	test_cleared_request_nonadmin,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can add a new imaging channel in 
	imaging entry form and then submit the form"""
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-new_channel_dropdown':'555',
		'image_resolution_forms-0-new_channel_purpose':'injection_detection',
		'image_resolution_forms-0-new_channel_button': True,
		}
	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	""" Make sure we are still in imaging entry form """
	assert b'Imaging Entry Form' in response.data

	""" Now submit the form for both channels"""
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
		'image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test555',
		'submit':True
		}
	response2 = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	""" Make sure this was successfully submitted and we landed back in imaging manager """
	assert b'Imaging Entry Form' not in response2.data

	""" Make sure new imaging entry exists in database for channel 555 """
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & 'request_name="nonadmin_request"' & \
		'username="lightserv-test"' & 'sample_name="sample-001"' & 'imaging_request_number=1' & \
		'channel_name="555"'
	assert len(imaging_channel_contents) == 1
	
def test_imager_selects_smartspim_channel_not_present_processing_manager(
	test_client,
	test_cleared_request_nonadmin,
	test_login_zmd):

	""" Test that if Zahra (zmd, an imaging admin) changes an imaging resolution
	in the imaging entry form from LaVision to SmartSpim (e.g. 3.6x), 
	then after she submits the form an entry to process this channel
	is not visible in the processing manager. """
	
	# First, a post request to change the resolution
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-change_resolution':True,
		'image_resolution_forms-0-new_image_resolution':'3.6x',
		'image_resolution_forms-0-update_resolution_button':True
		}

	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	# Then submit the form with the new resolution
	data = {
		'image_resolution_forms-0-image_resolution':'3.6x',
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
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'admin_request' in response.data 

	# Now check the processing manager
	
	response = test_client.get(url_for('processing.processing_manager',
		follow_redirects=True))
	assert b'nonadmin_request' not in response.data

	# Make sure no ProcessingRequest() entity exists for this request, but ImagingRequest() still exists
	imaging_restrict_dict = {
		'username':'lightserv-test',
		'request_name':'nonadmin_request',
		'sample_name':'sample-001',
		'imaging_request_number':1}
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & imaging_restrict_dict
	assert len(imaging_request_contents) == 1
	processing_restrict_dict = imaging_restrict_dict.copy()
	processing_restrict_dict['processing_request_number'] = 1
	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & processing_restrict_dict
	assert len(processing_request_contents) == 0

def test_2x_changed_to_1p3x_imaging_present_processing_manager(
	test_client,
	test_cleared_request_2x_nonadmin,
	test_login_zmd):

	""" Test that if Zahra (zmd, an imaging admin) changes an imaging resolution
	in the imaging entry form 2x imaging (which doesn't generate a processing request originally)
	to 1.3x, which does need to be processed, that the processing request shows up in the 
	processing manager and in the database """
	# First verify that no ProcessingRequest() entry exists
	processing_restrict_dict = {
		'username':'lightserv-test',
		'request_name':'test_2x_nonadmin',
		'sample_name':'sample-001',
		'imaging_request_number':1,
		'processing_request_number':1}
	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & processing_restrict_dict
	assert len(processing_request_contents) == 0
	# First, a post request to change the resolution
	data = {
		'image_resolution_forms-0-image_resolution':'2x',
		'image_resolution_forms-0-change_resolution':True,
		'image_resolution_forms-0-new_image_resolution':'1.3x',
		'image_resolution_forms-0-update_resolution_button':True
		}

	response = test_client.post(url_for('imaging.imaging_entry',
			username='lightserv-test',request_name='test_2x_nonadmin',sample_name='sample-001',
			imaging_request_number=1),
		data=data,
		follow_redirects=True)
	# Make sure a ProcessingRequest() entry now exists 
	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
		processing_restrict_dict
	assert len(processing_request_contents) == 1
	processing_resolution_request_contents = db_lightsheet.Request.ProcessingResolutionRequest() & \
		processing_restrict_dict
	print(processing_resolution_request_contents)

	# # Then submit the form with the new resolution
	# data = {
	# 	'image_resolution_forms-0-image_resolution':'1.3x',
	# 	'image_resolution_forms-0-channel_forms-0-channel_name':'488',
	# 	'image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
	# 	'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
	# 	'image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
	# 	'image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
	# 	'image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
	# 	'image_resolution_forms-0-channel_forms-0-z_step':10,
	# 	'image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
	# 	'image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
	# 	'submit':True
	# 	}

	# response = test_client.post(url_for('imaging.imaging_entry',
	# 		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
	# 		imaging_request_number=1),
	# 	data=data,
	# 	follow_redirects=True)
	# assert b'Imaging management GUI' in response.data
	# assert b'admin_request' in response.data 

	# # Now check the processing manager
	
	# response = test_client.get(url_for('processing.processing_manager',
	# 	follow_redirects=True))
	# assert b'nonadmin_request' not in response.data

	# # Make sure no ProcessingRequest() entity exists for this request, but ImagingRequest() still exists
	# imaging_restrict_dict = {
	# 	'username':'lightserv-test',
	# 	'request_name':'nonadmin_request',
	# 	'sample_name':'sample-001',
	# 	'imaging_request_number':1}
	# imaging_request_contents = db_lightsheet.Request.ImagingRequest() & imaging_restrict_dict
	# assert len(imaging_request_contents) == 1
	# processing_restrict_dict = imaging_restrict_dict.copy()
	# processing_restrict_dict['processing_request_number'] = 1
	# processing_request_contents = db_lightsheet.Request.ProcessingRequest() & processing_restrict_dict
	# assert len(processing_request_contents) == 0

def test_imaging_batch_entry_form_submits_single_sample(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can submit the imaging entry form
	for a single sample within the imaging batch entry form """
	data = {
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-z_step':10,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-z_step':10,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-number_of_z_planes':657,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test555',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-z_step':10,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_orientation':'horizontal',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-left_lightsheet_used':True,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-tiling_overlap':0.2,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-z_step':10,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-number_of_z_planes':657,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test555',
		'sample_forms-0-submit':True
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	restrict_dict = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='488')
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict
	number_of_z_planes = imaging_channel_contents.fetch1('number_of_z_planes')
	assert number_of_z_planes == 657
	rawdata_subfolder = imaging_channel_contents.fetch1('rawdata_subfolder')
	assert rawdata_subfolder == 'test488'
	imaging_request_restrict_dict = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			imaging_request_number=1)
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & imaging_request_restrict_dict
	assert imaging_request_contents.fetch1('imaging_progress') == "complete"
	""" Check that the sample subform is no longer available in the form upon reaccessing"""
	response2 = test_client.get(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		follow_redirects=True)

	assert b'Sample has been imaged' in response2.data

def test_apply_batch_parameters_successful(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_zmd):
	""" Test that hitting the apply batch parameters button 
	updates the database for each sample in the batch and 
	the sample forms are correctly autofilled with the batch parameters
	"""
	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_batch_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_batch_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_batch_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_batch_forms-0-channel_forms-0-z_step':5.5,
		'image_resolution_batch_forms-0-channel_forms-1-channel_name':'555',
		'image_resolution_batch_forms-0-channel_forms-1-image_orientation':'horizontal',
		'image_resolution_batch_forms-0-channel_forms-1-left_lightsheet_used':True,
		'image_resolution_batch_forms-0-channel_forms-1-tiling_overlap':0.2,
		'image_resolution_batch_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'image_resolution_batch_forms-0-channel_forms-1-z_step':7.5,
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'apply_batch_parameters_button':True,
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Check that the sample channel entry in the db was updated """
	restrict_dict_ch488 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='488')
	restrict_dict_ch555 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='555')
	imaging_channel_contents_ch488 = db_lightsheet.Request.ImagingChannel() & restrict_dict_ch488
	assert imaging_channel_contents_ch488.fetch1('z_step') == 5.5
	imaging_channel_contents_ch555 = db_lightsheet.Request.ImagingChannel() & restrict_dict_ch555
	assert imaging_channel_contents_ch555.fetch1('z_step') == 7.5

def test_apply_batch_parameters_validates(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_zmd):
	""" Test that hitting the apply batch parameters with
	bad batch parameters is subject to validation and does not 
	go through
	"""
	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_batch_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_batch_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_batch_forms-0-channel_forms-0-tiling_scheme':'1x8',
		'image_resolution_batch_forms-0-channel_forms-0-z_step':5.5,
		'image_resolution_batch_forms-0-channel_forms-1-channel_name':'555',
		'image_resolution_batch_forms-0-channel_forms-1-image_orientation':'horizontal',
		'image_resolution_batch_forms-0-channel_forms-1-left_lightsheet_used':True,
		'image_resolution_batch_forms-0-channel_forms-1-tiling_overlap':0.2,
		'image_resolution_batch_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'image_resolution_batch_forms-0-channel_forms-1-z_step':7.5,
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'apply_batch_parameters_button':True,
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	error_str = ("Issue with batch parameters for image resolution: 1.3x, "
				 "channel: 488. Tiling scheme must not exceed 2x2 for this resolution")
	assert error_str.encode('utf-8') in response.data
	""" Check that the sample channel entries in the db were NOT updated """
	restrict_dict_ch488 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='488')
	restrict_dict_ch555 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='555')
	imaging_channel_contents_ch488 = db_lightsheet.Request.ImagingChannel() & restrict_dict_ch488
	assert imaging_channel_contents_ch488.fetch1('z_step') == 10
	imaging_channel_contents_ch555 = db_lightsheet.Request.ImagingChannel() & restrict_dict_ch555
	assert imaging_channel_contents_ch555.fetch1('z_step') == 10

def test_change_image_resolution_batch_parameters(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_zmd):
	""" Test that changing the image resolution in the batch
	section of the batch entry form results in all samples 
	having their image resolution changed in the db and subsequent form.
	"""
	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-new_image_resolution':'1.1x',
		'image_resolution_batch_forms-0-update_resolution_button':True,
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Check that the sample channel entries in the db were updated """
	restrict_dict_ch488 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			channel_name='488')
	restrict_dict_ch555 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			channel_name='555')
	imaging_channel_contents_ch488 = db_lightsheet.Request.ImagingChannel() & restrict_dict_ch488
	assert imaging_channel_contents_ch488.fetch1('image_resolution') == '1.1x'
	imaging_channel_contents_ch555 = db_lightsheet.Request.ImagingChannel() & restrict_dict_ch555
	assert imaging_channel_contents_ch555.fetch1('image_resolution') == '1.1x'
	""" Now check that the image resolution shown in the form is correct """
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	header_tag_sample1 = parsed_html.find('h3',
		attrs={'id':'sample_0_image_resolution_header_0'})
	assert header_tag_sample1.text == '(1/1) Image resolution: 1.1x'
	header_tag_sample2 = parsed_html.find('h3',
		attrs={'id':'sample_1_image_resolution_header_0'})
	assert header_tag_sample2.text == '(1/1) Image resolution: 1.1x'

def test_add_channel_batch_parameters(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_zmd):
	""" Test that adding a channel in the batch
	section of the batch entry form results in all samples 
	also adding this channel and the new channel appearing in 
	the sample forms.
	"""
	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-new_channel_dropdown':'647',
		'image_resolution_batch_forms-0-new_channel_purpose':'cell_detection',
		'image_resolution_batch_forms-0-new_channel_button':True,
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Check that the sample channel entries in the db were updated """
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='647')
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents) == 1
	restrict_dict_sample2 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-002',
			image_resolution='1.3x',
			channel_name='647')
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents) == 1
	""" Now check that the new channel is shown in the sample resolution forms """
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag_sample1 = parsed_html.find('table',
		attrs={'id':'sample_0_resolution_1.3x_table'})
	table_row_tags_sample1 = table_tag_sample1.find_all('tr')
	assert len(table_row_tags_sample1) == 11
	ch647_row_sample1 = table_row_tags_sample1[-4].find_all('td')
	channel_name_ch647_sample1 = ch647_row_sample1[0].text
	assert channel_name_ch647_sample1 == '647'

	table_tag_sample2 = parsed_html.find('table',
		attrs={'id':'sample_1_resolution_1.3x_table'})
	table_row_tags_sample2 = table_tag_sample2.find_all('tr')
	assert len(table_row_tags_sample2) == 11
	ch647_row_sample2 = table_row_tags_sample2[-4].find_all('td')
	channel_name_ch647_sample2 = ch647_row_sample2[0].text
	assert channel_name_ch647_sample2 == '647'

def test_change_image_resolution_individual_sample(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_zmd):
	""" Test that changing the image resolution in an
	individual sample section of the imaging batch form 
	works and only affects the single sample
	"""
	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-new_image_resolution':'1.1x',
		'sample_forms-0-image_resolution_forms-0-update_resolution_button':True,
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Check that the sample-001 image resolution was updated in the db 
	and that sample-001 image resolution was NOT updated in the db"""
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			channel_name='488')
	restrict_dict_sample2 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-002',
			channel_name='488')
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert imaging_channel_contents_sample1.fetch1('image_resolution') == '1.1x'
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert imaging_channel_contents_sample2.fetch1('image_resolution') == '1.3x'

def test_add_channel_individual_sample(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_zmd):
	""" Test that adding a new channel in an
	individual sample section of the imaging batch form 
	works and only affects the single sample
	"""
	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-new_channel_dropdown':'790',
		'sample_forms-0-image_resolution_forms-0-new_channel_purpose':'cell_detection',
		'sample_forms-0-image_resolution_forms-0-new_channel_button':True,
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Check that the sample1 channel entry was added in the db """
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='790')
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 1
	restrict_dict_sample2 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-002',
			image_resolution='1.3x',
			channel_name='790')
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents_sample2) == 0
	""" Now check that the new channel is shown in the sample resolution forms """
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag_sample1 = parsed_html.find('table',
		attrs={'id':'sample_0_resolution_1.3x_table'})
	table_row_tags_sample1 = table_tag_sample1.find_all('tr')
	assert len(table_row_tags_sample1) == 11
	ch647_row_sample1 = table_row_tags_sample1[-4].find_all('td')
	channel_name_ch647_sample1 = ch647_row_sample1[0].text
	assert channel_name_ch647_sample1 == '790'

	table_tag_sample2 = parsed_html.find('table',
		attrs={'id':'sample_1_resolution_1.3x_table'})
	table_row_tags_sample2 = table_tag_sample2.find_all('tr')
	assert len(table_row_tags_sample2) == 8

def test_imaging_batch_entry_entire_form_submits(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can submit the entire imaging entry form
	for both samples and then the final submit button works and imaging_progress
	is updated in the db """

	""" First need to submit sample 1 """
	data1 = {
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-z_step':10,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-z_step':10,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-number_of_z_planes':657,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test555',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-z_step':10,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_orientation':'horizontal',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-left_lightsheet_used':True,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-tiling_overlap':0.2,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-z_step':10,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-number_of_z_planes':657,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test555',
		'sample_forms-0-submit':True
		}
	response1 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data1,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response1.data
	restrict_dict = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='488')
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict
	number_of_z_planes = imaging_channel_contents.fetch1('number_of_z_planes')
	assert number_of_z_planes == 657
	rawdata_subfolder = imaging_channel_contents.fetch1('rawdata_subfolder')
	assert rawdata_subfolder == 'test488'
	data2 = {
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-z_step':10,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-z_step':10,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-number_of_z_planes':657,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test555',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-z_step':10,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_orientation':'horizontal',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-left_lightsheet_used':True,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-tiling_overlap':0.2,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-z_step':10,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-number_of_z_planes':657,
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test555',
		'sample_forms-1-submit':True
		}
	
	response2 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data2,
		follow_redirects=True)
	restrict_dict = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-002',
			image_resolution='1.3x',
			channel_name='555')
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict
	number_of_z_planes = imaging_channel_contents.fetch1('number_of_z_planes')
	assert number_of_z_planes == 657
	rawdata_subfolder = imaging_channel_contents.fetch1('rawdata_subfolder')
	assert rawdata_subfolder == 'test555'
	assert b'Imaging Entry Form' in response2.data

	data3 = {
		'submit':True
		}

	response3 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data3,
		follow_redirects=True)
	assert b'Imaging Entry Form' not in response3.data
	assert b'Imaging management GUI'  in response3.data

	restrict_dict = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1)
	imaging_batch_contents = db_lightsheet.Request.ImagingBatch() & restrict_dict
	assert imaging_batch_contents.fetch1('imaging_progress') == 'complete'

""" Test for imaging tasks """

def test_raw_precomputed_pipeline_starts(test_client,test_delete_spockadmin_db_contents):
	""" Test that the raw precomputed pipeline task runs through,
	given the correct input. Uses a test script on spock which just returns
	job ids. Runs a celery task """
	from lightserv.imaging import tasks
	import time
	table_contents = db_spockadmin.RawPrecomputedSpockJob() 
	username='ahoag'
	request_name='admin_request'
	sample_name='sample-001'
	imaging_request_number=1
	image_resolution='1.3x'
	channel_name='488'
	channel_index=0
	number_of_z_planes=657
	left_lightsheet_used=True
	right_lightsheet_used=False
	z_step=10
	rawdata_subfolder='test488'
	precomputed_kwargs = dict(username=username,request_name=request_name,
							sample_name=sample_name,imaging_request_number=imaging_request_number,
							image_resolution=image_resolution,channel_name=channel_name,
							channel_index=channel_index,number_of_z_planes=number_of_z_planes,
							left_lightsheet_used=left_lightsheet_used,
							right_lightsheet_used=right_lightsheet_used,
							z_step=z_step,rawdata_subfolder=rawdata_subfolder)
	raw_viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
			 f"{request_name}/{sample_name}/"
			 f"imaging_request_{imaging_request_number}/viz/raw")

	channel_viz_dir = os.path.join(raw_viz_dir,f'channel_{channel_name}')
	raw_data_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
						request_name,sample_name,
						f"imaging_request_{imaging_request_number}","rawdata",
						f"resolution_{image_resolution}",f"{rawdata_subfolder}")
	this_viz_dir = os.path.join(channel_viz_dir,'left_lightsheet')
	precomputed_kwargs['lightsheet'] = 'left'
	precomputed_kwargs['viz_dir'] = this_viz_dir
	layer_name = f'channel{channel_name}_raw_left_lightsheet'
	precomputed_kwargs['layer_name'] = layer_name
	layer_dir = os.path.join(this_viz_dir,layer_name)
	# Figure out what x and y dimensions are
	lightsheet_index_code = 'C00' # always for left lightsheet
	precomputed_kwargs['lightsheet_index_code'] = lightsheet_index_code
	all_slices = glob.glob(
		f"{raw_data_dir}/*RawDataStack[00 x 00*{lightsheet_index_code}*Filter000{channel_index}*tif")
	first_slice = all_slices[0]
	first_im = Image.open(first_slice)
	x_dim,y_dim = first_im.size
	first_im.close() 
	precomputed_kwargs['x_dim'] = x_dim
	precomputed_kwargs['y_dim'] = y_dim
	tasks.make_precomputed_rawdata.run(**precomputed_kwargs) 
	table_contents = db_spockadmin.RawPrecomputedSpockJob() 
	assert len(table_contents) > 0

def test_raw_precomputed_pipeline_starts_added_channel(test_client,
	test_imaged_request_nonadmin_new_channel_added,
	test_delete_spockadmin_db_contents):
	""" Test that the raw precomputed pipeline task runs through with 
	the original imaging channel and a channel that is added by the imager during
	the imaging entry form.
	 """
	from lightserv.imaging import tasks
	table_contents = db_spockadmin.RawPrecomputedSpockJob() 
	username = "lightserv-test"
	request_name = "nonadmin_request"
	sample_name = "sample-001"
	imaging_request_number = 1
	image_resolution='1.3x'
	channel_name='555'
	channel_index=0
	number_of_z_planes=657
	left_lightsheet_used=True
	right_lightsheet_used=False
	z_step=10
	rawdata_subfolder='test555'
	precomputed_kwargs = dict(username=username,request_name=request_name,
							sample_name=sample_name,imaging_request_number=imaging_request_number,
							image_resolution=image_resolution,channel_name=channel_name,
							channel_index=channel_index,number_of_z_planes=number_of_z_planes,
							left_lightsheet_used=left_lightsheet_used,
							right_lightsheet_used=right_lightsheet_used,
							z_step=z_step,rawdata_subfolder=rawdata_subfolder)
	raw_viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
			 f"{request_name}/{sample_name}/"
			 f"imaging_request_{imaging_request_number}/viz/raw")

	channel_viz_dir = os.path.join(raw_viz_dir,f'channel_{channel_name}')
	raw_data_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
						request_name,sample_name,
						f"imaging_request_{imaging_request_number}","rawdata",
						f"resolution_{image_resolution}",f"{rawdata_subfolder}")
	this_viz_dir = os.path.join(channel_viz_dir,'left_lightsheet')
	precomputed_kwargs['lightsheet'] = 'left'
	precomputed_kwargs['viz_dir'] = this_viz_dir
	layer_name = f'channel{channel_name}_raw_left_lightsheet'
	precomputed_kwargs['layer_name'] = layer_name
	layer_dir = os.path.join(this_viz_dir,layer_name)
	# Figure out what x and y dimensions are
	lightsheet_index_code = 'C00' # always for left lightsheet
	precomputed_kwargs['lightsheet_index_code'] = lightsheet_index_code
	all_slices = glob.glob(
		f"{raw_data_dir}/*RawDataStack[00 x 00*{lightsheet_index_code}*Filter000{channel_index}*tif")
	first_slice = all_slices[0]
	first_im = Image.open(first_slice)
	x_dim,y_dim = first_im.size
	first_im.close() 
	precomputed_kwargs['x_dim'] = x_dim
	precomputed_kwargs['y_dim'] = y_dim
	tasks.make_precomputed_rawdata.run(**precomputed_kwargs) 
	spockjob_table_contents = db_spockadmin.RawPrecomputedSpockJob() 
	print(spockjob_table_contents)
	assert len(spockjob_table_contents) > 0
	""" Make sure jobid in ImagingEntry() table and RawPrecomputedSpockJob() tables are the same """
	restrict_dict = {'username':username,'request_name':request_name,
		'sample_name':sample_name,'imaging_request_number':imaging_request_number,
		'image_resolution':image_resolution,'channel_name':channel_name}
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict
	spock_jobid_imaging_table = imaging_channel_contents.fetch1('left_lightsheet_precomputed_spock_jobid')
	spock_jobid_admin_table = spockjob_table_contents.fetch1('jobid_step2')
	assert spock_jobid_imaging_table == spock_jobid_admin_table



""" Tests for New imaging request """	

def test_new_imaging_request_submits(test_client,test_single_sample_request_ahoag):
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
	""" Test that a user can request a new imaging request
	with self-imaging
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


""" Tests for Imaging table """	

def test_imaging_table_loads_nonadmin(test_client,test_imaged_request_nonadmin,
	test_login_zmd):
	""" Test that the imaging table page loads properly for an imaged request """
	from lightserv import db_lightsheet
	
	response = test_client.get(url_for('imaging.imaging_table',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		follow_redirects=True)
	assert b'Imaging Log' in response.data

def test_imaging_table_redirects_incomplete_imaging_nonadmin(test_client,test_cleared_request_nonadmin,
	test_login_zmd):
	""" Test that the imaging table page redirects to request_overview
	when imaging request is not yet complete """
	from lightserv import db_lightsheet
	
	response = test_client.get(url_for('imaging.imaging_table',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		follow_redirects=True)
	assert b'Imaging Log' not in response.data
	assert b'Request overview:' in response.data


