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
		'sample_forms-0-notes_from_imaging':'some custom notes',
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
	restrict_dict_resolution = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x')
	""" Check that notes from imaging for that sample were recorded in db """
	imaging_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
		restrict_dict_resolution
	notes_from_imaging = imaging_resolution_request_contents.fetch1('notes_from_imaging')
	assert notes_from_imaging == 'some custom notes'
	""" Check that imaging progress and imaging performed date were updated """
	imaging_request_restrict_dict = restrict_dict_resolution = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			imaging_request_number=1)
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & \
		imaging_request_restrict_dict
	imaging_progress, imaging_performed_date = imaging_request_contents.fetch1(
		'imaging_progress','imaging_performed_date')
	assert imaging_progress == 'complete'
	assert imaging_performed_date == datetime.now().date()

def test_imaging_batch_entry_form_validates_single_sample(test_client,
	test_cleared_request_nonadmin,
	test_login_zmd):
	""" Test that submitting an individual sample section of the 
	batch entry form validates against bad data
	"""
	data = {
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_overlap':99,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x5',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-z_step':'ab',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-number_of_z_planes':680,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'sample_forms-0-submit':True
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_request',
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Tiling scheme must not exceed 2x2 for this resolution' in response.data
	assert b'z_step must be a number between 2 and 1000 microns' in response.data
	assert b'Tiling overlap must be a number between 0 and 1' in response.data

def test_imaging_batch_entry_form_validates_3p6x_smartspim(test_client,
	test_cleared_request_3p6x_smartspim_nonadmin,
	test_login_zmd):
	""" Test that both the batch entry and an individual sample entry of the 
	imaging batch entry form validates against bad data for 
	a SmartSPIM 3.6x request
	"""

	""" First test the batch validation """
	batch_data = {
		'image_resolution_batch_forms-0-image_resolution':'3.6x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'3.6x',
		'image_resolution_batch_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_batch_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_batch_forms-0-channel_forms-0-right_lightsheet_used':True,
		'image_resolution_batch_forms-0-channel_forms-0-tiling_overlap':10,
		'image_resolution_batch_forms-0-channel_forms-0-tiling_scheme':'9x11',
		'image_resolution_batch_forms-0-channel_forms-0-z_step':'ab',
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'3.6x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'3.6x',
		'apply_batch_parameters_button':True,
		}
		
	batch_response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_3p6x_smartspim_request',
			imaging_batch_number=1),
		data=batch_data,
		follow_redirects=True)
	assert b'Tiling scheme must not exceed 10x10 for this resolution' in batch_response.data
	assert b'z_step must be a number between 2 and 1000 microns' in batch_response.data
	assert b'Tiling overlap must be a number between 0 and 1' in batch_response.data

	""" Now test the individual sample validation """
	sample_data = {
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'3.6x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'3.6x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_overlap':99,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_scheme':'9x11',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-z_step':'ab',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-number_of_z_planes':3600,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'sample_forms-0-submit':True
		}
	sample_response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_3p6x_smartspim_request',
			imaging_batch_number=1),
		data=sample_data,
		follow_redirects=True)
	assert b'Tiling scheme must not exceed 10x10 for this resolution' in sample_response.data
	assert b'z_step must be a number between 2 and 1000 microns' in sample_response.data
	assert b'Tiling overlap must be a number between 0 and 1' in sample_response.data

def test_imaging_batch_entry_form_validates_3p6x_zplanes_smartspim(test_client,
	test_cleared_request_3p6x_smartspim_nonadmin,
	test_login_zmd):
	""" Test that the validation for counting expected versus
	found z planes works for a SmartSPIM 3.6x request
	"""
	sample_data = {
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'3.6x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'3.6x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-right_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_scheme':'3x5',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-z_step':2.0,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-number_of_z_planes':3300,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'sample_forms-0-submit':True
		}
	sample_response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_3p6x_smartspim_request',
			imaging_batch_number=1),
		data=sample_data,
		follow_redirects=True)
	assert b'There should be 49500 raw files in rawdata folder' in sample_response.data

def test_imaging_batch_entry_form_sample_submits_3p6x_smartspim(test_client,
	test_cleared_request_3p6x_smartspim_nonadmin,
	test_login_zmd):
	""" Test that submitting a sample form works for a SmartSPIM 3.6x request.
	This tests out the file count validation which is different for SmartSPIM vs. LaVision
	"""
	sample_data = {
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'3.6x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'3.6x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-right_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_scheme':'3x5',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-z_step':2.0,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-number_of_z_planes':3300,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'Ex_785_Em_3',
		'sample_forms-0-submit':True
		}
	sample_response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_3p6x_smartspim_request',
			imaging_batch_number=1),
		data=sample_data,
		follow_redirects=True)

	assert b'There should be 49500 raw files in rawdata folder' not in sample_response.data
	restrict_dict = dict(username='lightserv-test',
			request_name='nonadmin_3p6x_smartspim_request',
			sample_name='sample-001',
			image_resolution='3.6x',
			channel_name='488')
	imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict
	number_of_z_planes,rawdata_subfolder = imaging_channel_contents.fetch1(
		'number_of_z_planes','rawdata_subfolder')
	assert number_of_z_planes == 3300
	assert rawdata_subfolder == 'Ex_785_Em_3'
	imaging_request_restrict_dict = dict(username='lightserv-test',
			request_name='nonadmin_3p6x_smartspim_request',
			sample_name='sample-001',
			imaging_request_number=1)
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & imaging_request_restrict_dict
	assert imaging_request_contents.fetch1('imaging_progress') == "complete"
	""" Check that the sample subform is no longer available in the form upon reaccessing"""
	response2 = test_client.get(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_3p6x_smartspim_request',
			imaging_batch_number=1),
		follow_redirects=True)

	assert b'Sample has been imaged' in response2.data
	restrict_dict_resolution = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x')



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
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
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
	channel_name_ch647_sample1 = ch647_row_sample1[0].text[0:3]
	assert channel_name_ch647_sample1 == '647'

	table_tag_sample2 = parsed_html.find('table',
		attrs={'id':'sample_1_resolution_1.3x_table'})
	table_row_tags_sample2 = table_tag_sample2.find_all('tr')
	assert len(table_row_tags_sample2) == 11
	ch647_row_sample2 = table_row_tags_sample2[-4].find_all('td')
	channel_name_ch647_sample2 = ch647_row_sample2[0].text[0:3]
	assert channel_name_ch647_sample2 == '647'

def test_delete_channel_batch_parameters(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_zmd):
	""" Test that deleting a channel in the batch
	section of the batch entry form results in all samples 
	also deleting this channel and the deleted channel no longer 
	appears in the sample forms.
	"""

	""" Check that originally there are ch555 entries for both samples """
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='555')
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 1
	restrict_dict_sample2 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-002',
			image_resolution='1.3x',
			channel_name='555')
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents_sample2) == 1

	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-1-channel_name':'555',
		'image_resolution_batch_forms-0-channel_forms-1-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-1-delete_channel_button':True,
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		}

	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Now check that the ImagingChannel() db entries 
	that previously existed above are now absent """
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 0
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents_sample2) == 0

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

	""" Now check that the new channel is shown in the sample resolution form """
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag_sample1 = parsed_html.find('table',
		attrs={'id':'sample_0_resolution_1.3x_table'})
	table_row_tags_sample1 = table_tag_sample1.find_all('tr')
	assert len(table_row_tags_sample1) == 11
	ch647_row_sample1 = table_row_tags_sample1[-4].find_all('td')
	channel_name_ch647_sample1 = ch647_row_sample1[0].text[0:3]
	assert channel_name_ch647_sample1 == '790'

	table_tag_sample2 = parsed_html.find('table',
		attrs={'id':'sample_1_resolution_1.3x_table'})
	table_row_tags_sample2 = table_tag_sample2.find_all('tr')
	assert len(table_row_tags_sample2) == 8

def test_delete_channel_individual_sample(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_zmd):
	""" Test that deleting a channel in an
	individual sample section of the imaging batch form 
	works and only affects the single sample
	"""

	""" Check that originally there is a ch555 entry for both samples """
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='555')
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 1
	restrict_dict_sample2 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-002',
			image_resolution='1.3x',
			channel_name='555')
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents_sample2) == 1

	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',		
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-delete_channel_button':True,
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Check that the sample1 channel entry was NOT deleted in the db """
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 1
	""" Check that the sample2 channel entry was deleted in the db """
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents_sample2) == 0

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


