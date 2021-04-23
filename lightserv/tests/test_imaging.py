from flask import url_for, current_app,Markup	
import os, shutil, glob
from PIL import Image
import tempfile
import webbrowser
from lightserv import db_lightsheet, db_spockadmin
from bs4 import BeautifulSoup 
from datetime import datetime

""" Tests for Imaging Manager """

def test_access_imaging_manager(test_client,
	test_cleared_request_nonadmin,):
	""" Test that lightserv-test, a nonadmin, can access the imaging task manager
	but cannot see their entry because they did not designate himself as the imager """
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'nonadmin_request' not in response.data 
	""" Now login as an admin and make sure they can see request """
	imager = current_app.config['IMAGING_ADMINS'][-1] 
	with test_client.session_transaction() as sess:
		sess['user'] = imager
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'nonadmin_request' in response.data 

def test_nonadmin_can_see_self_imaging_request(test_client,test_self_cleared_request_nonadmin):
	""" Test that lightserv-test, a nonadmin can see their 
	request in which they designated themselves as the clearer and imager.
	
	Also check that an imaging manager can see this request
	"""

	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'self_clearing_and_imaging_request' in response.data 
	""" Now login as an admin and make sure they can see request """
	imager = current_app.config['IMAGING_ADMINS'][-1] 
	with test_client.session_transaction() as sess:
		sess['user'] = imager
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'self_clearing_and_imaging_request' in response.data 
	
def test_multisample_multichannel_request_in_imaging_manager(test_client,
	test_cleared_multisample_multichannel_request_nonadmin):
	""" Test that lightserv-test can access the imaging task manager
	and see their imaging request and that there is no ProcessingRequest() in the database  """
	imager = current_app.config['IMAGING_ADMINS'][-1] 
	with test_client.session_transaction() as sess:
		sess['user'] = imager
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'nonadmin_manysamp_request' in response.data 

def test_microscope_column_correct(test_client,test_cleared_request_both_microscopes_nonadmin
	):
	""" Test that microscope column shows 'lavision & smartspim' if both requested
	"""
	imager = current_app.config['IMAGING_ADMINS'][-1] 
	with test_client.session_transaction() as sess:
		sess['user'] = imager
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'nonadmin_bothmicroscopes_request' in response.data
	assert b'lavision & smartspim' in response.data 


""" Tests for imaging entry form """

def test_imaging_batch_entry_form_GET(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_imager):
	""" Test a GET request to imaging batch entry form renders 
	"""

	response = test_client.get(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	
	""" Make sure all clearing and imaging notes
	that were left by the user for each sample
	show up in the sample section """
	assert b'Sample 1 clearing notes' in response.data
	assert b'Sample 2 clearing notes' in response.data
	assert b'Sample 3 clearing notes' in response.data
	assert b'Sample 1 imaging notes' in response.data
	assert b'Sample 2 imaging notes' in response.data
	assert b'Sample 3 imaging notes' not in response.data # Sample 3 is in imaging batch 2

	response = test_client.get(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=2),
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Make sure all clearing and imaging notes
	that were left by the user for each sample
	show up in the sample section """
	assert b'Sample 1 clearing notes' in response.data
	assert b'Sample 2 clearing notes' in response.data
	assert b'Sample 3 clearing notes' in response.data
	assert b'Sample 1 imaging notes' not in response.data # Only sample 3 is in imaging batch 2
	assert b'Sample 2 imaging notes' not in response.data # Only sample 3 is in imaging batch 2
	assert b'Sample 3 imaging notes' in response.data 

def test_imaging_batch_entry_form_single_sample(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_imager):
	""" Test the single sample section of the imaging batch entry form.

	First, test validation.

	Then, test adding/deleting channel

	Then, test changing image resolution

	Then, test that the subform submits.

	"""
	data_validation = {
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
	response_validation = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data_validation,
		follow_redirects=True)
	assert b'Tiling scheme must not exceed 2x2 for this resolution' in response_validation.data
	assert b'z_step must be a number between 2 and 1000 microns' in response_validation.data
	assert b'Tiling overlap must be a number between 0 and 1' in response_validation.data

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
			clearing_batch_number=1,
			imaging_request_number=1,
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

	""" Test that deleting a channel in an
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
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-channel_name':'790',
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-image_resolution':'1.3x',	
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-delete_channel_button':True,	
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
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Check that the sample1 channel entry was deleted in the db """
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 0

	""" Test that changing the image resolution in an
	individual sample section of the imaging entry form 
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
			clearing_batch_number=1,
			imaging_request_number=1,
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


	""" Now submit the form """

	data = {
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.1x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.1x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-z_step':10,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.1x',
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
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
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
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	
	""" Check contents of db were updated """
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.1x',
			channel_name='488')

	imaging_channel_contents_sample1= db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	number_of_z_planes = imaging_channel_contents_sample1.fetch1('number_of_z_planes')
	assert number_of_z_planes == 657
	rawdata_subfolder = imaging_channel_contents_sample1.fetch1('rawdata_subfolder')
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
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		follow_redirects=True)

	assert b'Sample has been imaged' in response2.data
	restrict_dict_resolution = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.1x')
	
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

def test_imaging_batch_entry_form_3p6x_smartspim(test_client,
	test_cleared_request_3p6x_smartspim_nonadmin,
	test_login_imager):
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
			clearing_batch_number=1,
			imaging_request_number=1,
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
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=sample_data,
		follow_redirects=True)
	assert b'Tiling scheme must not exceed 10x10 for this resolution' in sample_response.data
	assert b'z_step must be a number between 2 and 1000 microns' in sample_response.data
	assert b'Tiling overlap must be a number between 0 and 1' in sample_response.data

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
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=sample_data,
		follow_redirects=True)
	assert b'You entered that there should be 49500 raw files in rawdata folder' in sample_response.data

	""" Test that when the wrong number of rows in the tiling scheme is provided a validation error is raised.
	Correct tiling scheme is 3x5
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
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_scheme':'5x3',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-z_step':2.0,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-number_of_z_planes':3300,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'Ex_785_Em_3',
		'sample_forms-0-submit':True
		}
	sample_response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_3p6x_smartspim_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=sample_data,
		follow_redirects=True)
	assert b'You entered that there should be 49500 raw files in rawdata folder' in sample_response.data
	assert b"You entered that there should be 5 tiling row folders in rawdata folder, but found 3" in sample_response.data

	""" Test that when the correct number of rows but wrong number of columns in the tiling scheme
	are provided a validation error is raised.
	Correct tiling scheme is 3x5
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
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_scheme':'3x8',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-z_step':2.0,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-number_of_z_planes':3300,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'Ex_785_Em_3',
		'sample_forms-0-submit':True
		}
	sample_response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_3p6x_smartspim_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=sample_data,
		follow_redirects=True)
	assert b'You entered that there should be 79200 raw files in rawdata folder' in sample_response.data
	assert b"You entered that there should be 8 tiling column folders in each tiling row folder, but found 5" in sample_response.data

def test_changing_microscope_changes_channels(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_imager):
	""" Test that when the image resolution is changed
	to a new microscope, the available channels change
	because the two microscopes use different imaging channels.
	Tests both batch and single sample sections. 

	The test_cleared_multisample_multichannel_request_nonadmin
	comes with:
	Sample 1: 488 and 555 channels, 1.3x resolution
	Sample 2: 488 and 555 channels, 1.3x resolution
	Sample 3: 488 and 647 channels, 1.3x resolution
	"""

	""" Test changing resolution to new microscope at the batch level
	results in updated channel names 
	"""
	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-1-channel_name':'555',
		'image_resolution_batch_forms-0-channel_forms-1-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-new_image_resolution':'3.6x',
		'image_resolution_batch_forms-0-update_resolution_button':True,
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
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Check that the sample channel entries in the db were updated """
	restrict_dict_ch488 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			channel_name='488')
	restrict_dict_ch561 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			channel_name='561')
	imaging_channel_contents_ch488 = db_lightsheet.Request.ImagingChannel() & restrict_dict_ch488
	assert imaging_channel_contents_ch488.fetch1('image_resolution') == '3.6x'
	imaging_channel_contents_ch561 = db_lightsheet.Request.ImagingChannel() & restrict_dict_ch561
	assert imaging_channel_contents_ch561.fetch1('image_resolution') == '3.6x'

	""" Now check that the channel names in the form are correct """
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	batch_table_tag = parsed_html.find('table',
		attrs={'id':'batch_resolution_3.6x_table'})
	batch_table_rows = batch_table_tag.find_all('tr')
	ch561_row = batch_table_rows[2].find_all('td')
	ch561_channel_name = ch561_row[0].text[0:3]
	assert ch561_channel_name == '561'

	""" Now change image resolution of a single sample back to lavision """
	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'3.6x',
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'3.6x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'3.6x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'561',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'3.6x',
		'sample_forms-0-image_resolution_forms-0-new_image_resolution':'1.1x',
		'sample_forms-0-image_resolution_forms-0-update_resolution_button':True,
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'3.6x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'3.6x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'561',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'3.6x',
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
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

def test_apply_batch_parameters(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_imager):
	""" Test validation, changing image resolution, adding/deleting channel
	and submission of applying the batch 
	parameters to all samples """

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
			clearing_batch_number=1,
			imaging_request_number=1,
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
			clearing_batch_number=1,
			imaging_request_number=1,
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

	""" Test that deleting a channel in the batch
	section of the batch entry form results in all samples 
	also deleting this channel and the deleted channel no longer 
	appears in the sample forms.
	"""

	""" Check that originally there are ch647 entries for both samples """
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='647')
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 1
	restrict_dict_sample2 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-002',
			image_resolution='1.3x',
			channel_name='647')
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents_sample2) == 1

	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-1-channel_name':'647',
		'image_resolution_batch_forms-0-channel_forms-1-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-1-delete_channel_button':True,
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		}

	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
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
			clearing_batch_number=1,
			imaging_request_number=1,
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
	assert header_tag_sample1.text == '(1/1) Image resolution: 1.1x (LaVision microscope)'
	header_tag_sample2 = parsed_html.find('h3',
		attrs={'id':'sample_1_image_resolution_header_0'})
	assert header_tag_sample2.text == '(1/1) Image resolution: 1.1x (LaVision microscope)'


	""" Test that hitting the apply batch parameters button 
	updates the database for each sample in the batch and 
	the sample forms are correctly autofilled with the batch parameters
	"""
	data = {
		'image_resolution_batch_forms-0-image_resolution':'1.1x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.1x',
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
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.1x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.1x',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.1x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.1x',
		'apply_batch_parameters_button':True,
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Check that the sample channel entry in the db was updated """
	restrict_dict_ch488 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.1x',
			channel_name='488')
	restrict_dict_ch555 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.1x',
			channel_name='555')
	imaging_channel_contents_ch488 = db_lightsheet.Request.ImagingChannel() & restrict_dict_ch488
	assert imaging_channel_contents_ch488.fetch1('z_step') == 5.5
	imaging_channel_contents_ch555 = db_lightsheet.Request.ImagingChannel() & restrict_dict_ch555
	assert imaging_channel_contents_ch555.fetch1('z_step') == 7.5

def test_imaging_batch_entry_entire_form_submits(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_imager):
	""" Test that an imaging admin can submit the entire imaging entry form
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
			clearing_batch_number=1,
			imaging_request_number=1,
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
			clearing_batch_number=1,
			imaging_request_number=1,
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
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data3,
		follow_redirects=True)
	assert b'Imaging Entry Form' not in response3.data
	assert b'Imaging management GUI'  in response3.data

	restrict_dict = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1)
	imaging_batch_contents = db_lightsheet.Request.ImagingBatch() & restrict_dict
	assert imaging_batch_contents.fetch1('imaging_progress') == 'complete'

def test_add_ventral_up_channel_batch(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_imager):
	
	""" Test that clicking the button to add
	a ventral up channel in the batch section
	adds the ventral up channel both in the batch section
	and for all individual samples individual sample section of the imaging batch form 
	creates a duplicate channel row with a ventral up channel.
	"""
	# Initially make sure there is only 1 entry for channel 488 and it is dorsal up
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='488')
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 1
	ventral_up_initially_sample1 = imaging_channel_contents_sample1.fetch1('ventral_up')
	assert ventral_up_initially_sample1 == False
	restrict_dict_sample2 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-002',
			image_resolution='1.3x',
			channel_name='488')
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents_sample2) == 1
	ventral_up_initially_sample2 = imaging_channel_contents_sample2.fetch1('ventral_up')
	assert ventral_up_initially_sample2 == False

	""" Make sure the "add flipped channel" button appears in the sample table for channel 488 """
	response1 = test_client.get(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		follow_redirects=True)
	parsed_html = BeautifulSoup(response1.data,features="html.parser")
	table_tag_sample1 = parsed_html.find('table',
		attrs={'id':'batch_resolution_1.3x_table'})
	table_row_tags_sample1 = table_tag_sample1.find_all('tr')
	ch488_row_sample1 = table_row_tags_sample1[1].find_all('td')
	channel_name_ch488_sample1 = ch488_row_sample1[0]
	add_flipped_button = parsed_html.find('input',
		attrs={'id':'batch_add_flipped_channel_modal_res_1.3x_ch_488_ventral_up_0'})
	assert add_flipped_button != None

	""" POST request to hit the add ventral up batch channel button for channel 488 """
	data2 = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-add_flipped_channel_button':True,
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
	response2 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data2,
		follow_redirects=True)
	""" Check that there are now two channel 488 db entries for sample1 and sample2"""
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 2
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents_sample2) == 2
	""" Make sure ventral_up = 1 in these new entries """
	ventral_up_vals_sample1 = imaging_channel_contents_sample1.fetch('ventral_up')
	assert ventral_up_vals_sample1[0] == 0
	assert ventral_up_vals_sample1[1] == 1
	ventral_up_vals_sample2 = imaging_channel_contents_sample2.fetch('ventral_up')
	assert ventral_up_vals_sample2[0] == 0
	assert ventral_up_vals_sample2[1] == 1
	""" Now make sure the add flipped button is not in the original ch488 row
	of the batch table anymore
	We don't want this button there because the flipped channel has already been made! """
	parsed_html = BeautifulSoup(response2.data,features="html.parser")
	table_tag_sample1 = parsed_html.find('table',
		attrs={'id':'batch_resolution_1.3x_table'})
	table_row_tags_sample1 = table_tag_sample1.find_all('tr')
	ch488_row_sample1 = table_row_tags_sample1[1].find_all('td')
	channel_name_ch488_sample1 = ch488_row_sample1[0]
	add_flipped_button = parsed_html.find('input',
		attrs={'id':'batch_add_flipped_channel_modal_res_1.3x_ch_488_ventral_up_0'})
	assert add_flipped_button == None
	""" And make sure that the flipped channel displays 'Ventral' in the dorsal or ventral column """
	ch488_flipped_row_sample1 = table_row_tags_sample1[2].find_all('td')
	print(ch488_flipped_row_sample1)
	dorsal_or_ventral = ch488_flipped_row_sample1[3].find_all('div')[0].find_all('p')[0].text
	assert dorsal_or_ventral == 'Ventral'
	# """ POST request to delete the flipped channel """
	data3 = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-1-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-1-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-1-ventral_up':1,		
		'image_resolution_batch_forms-0-channel_forms-1-delete_channel_button':True,
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',		
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-image_resolution':'1.3x',	
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-2-channel_name':'555',
		'sample_forms-1-image_resolution_forms-0-channel_forms-2-image_resolution':'1.3x',
		}
	response3 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data3,
		follow_redirects=True)
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 1
	ventral_up_val_sample1 = imaging_channel_contents_sample1.fetch1('ventral_up')
	assert ventral_up_val_sample1 == 0
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents_sample2) == 1
	ventral_up_val_sample2 = imaging_channel_contents_sample2.fetch1('ventral_up')
	assert ventral_up_val_sample2 == 0

	# """ Test that if the image orientation is not horizontal for a channel
	# then clicking the add flipped channel button does not create 
	# a flipped channel and results in a validation error """
	data4 = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-1-channel_name':'555',
		'image_resolution_batch_forms-0-channel_forms-1-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-1-image_orientation':'sagittal',
		'image_resolution_batch_forms-0-channel_forms-1-add_flipped_channel_button':True,
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
	response4 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data4,
		follow_redirects=True)
	this_image_resolution = '1.3x'
	channel_name_to_flip = '555'
	error_str = (f"Can only add flipped imaging channel if "
				 "image orientation is horizontal in batch section for: "
				 f"image resolution: {this_image_resolution}, "
				 f"channel: {channel_name_to_flip}")
	assert error_str.encode('utf-8') in response4.data
	# """ Make sure no db entry was made for this flipped 555 channel """
	restrict_dict_sample1_ch555 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='555')
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1_ch555
	assert len(imaging_channel_contents_sample1) == 1
	ventral_up_ch555_sample1 = imaging_channel_contents_sample1.fetch1('ventral_up')
	assert ventral_up_ch555_sample1 == 0
	restrict_dict_sample2_ch555 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-002',
			image_resolution='1.3x',
			channel_name='555')
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2_ch555
	assert len(imaging_channel_contents_sample2) == 1
	ventral_up_ch555_sample2 = imaging_channel_contents_sample2.fetch1('ventral_up')
	assert ventral_up_ch555_sample2 == 0

	""" Finally re-add the flipped 488 channel and
	test that the sample submits with a flipped channel """
	data5 = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-add_flipped_channel_button':True,
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
	
	response5 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data5,
		follow_redirects=True)
	""" Check that there are now two channel 488 db entries for sample1 and sample2"""
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 2
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents_sample2) == 2
	""" POST request to apply batch parameters with the new flipped channel
	to make sure they propagate to the samples """
	data6 = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-image_orientation':'horizontal',
		'image_resolution_batch_forms-0-channel_forms-0-left_lightsheet_used':True,
		'image_resolution_batch_forms-0-channel_forms-0-tiling_overlap':0.2,
		'image_resolution_batch_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'image_resolution_batch_forms-0-channel_forms-0-z_step':3,
		'image_resolution_batch_forms-0-channel_forms-0-number_of_z_planes':657,
		'image_resolution_batch_forms-0-channel_forms-0-rawdata_subfolder':'test488',

		'image_resolution_batch_forms-0-channel_forms-1-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-1-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-1-image_orientation':'horizontal',
		'image_resolution_batch_forms-0-channel_forms-1-ventral_up':True,
		'image_resolution_batch_forms-0-channel_forms-1-left_lightsheet_used':True,
		'image_resolution_batch_forms-0-channel_forms-1-tiling_overlap':0.2,
		'image_resolution_batch_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'image_resolution_batch_forms-0-channel_forms-1-z_step':4,
		'image_resolution_batch_forms-0-channel_forms-1-number_of_z_planes':657,
		'image_resolution_batch_forms-0-channel_forms-1-rawdata_subfolder':'test488',

		'image_resolution_batch_forms-0-channel_forms-2-channel_name':'555',
		'image_resolution_batch_forms-0-channel_forms-2-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-2-image_orientation':'horizontal',
		'image_resolution_batch_forms-0-channel_forms-2-left_lightsheet_used':True,
		'image_resolution_batch_forms-0-channel_forms-2-tiling_overlap':0.2,
		'image_resolution_batch_forms-0-channel_forms-2-tiling_scheme':'1x1',
		'image_resolution_batch_forms-0-channel_forms-2-z_step':10,
		'image_resolution_batch_forms-0-channel_forms-2-number_of_z_planes':657,
		'image_resolution_batch_forms-0-channel_forms-2-rawdata_subfolder':'test555',

		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-ventral_up':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-image_resolution':'1.3x',		
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-ventral_up':True,
		'sample_forms-1-image_resolution_forms-0-channel_forms-2-channel_name':'555',
		'sample_forms-1-image_resolution_forms-0-channel_forms-2-image_resolution':'1.3x',
		'apply_batch_parameters_button':True,
	}
	response6 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data6,
		follow_redirects=True)	
	assert b"Batch parameters successfully applied to samples" in response6.data
	""" Make sure all samples were updated with these parameters in the db """

	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	# print(imaging_channel_contents_sample1.fetch(as_dict=True))
	contents_sample1_dorsal_up = imaging_channel_contents_sample1 & {'ventral_up':False}
	dorsal_up_z_step = contents_sample1_dorsal_up.fetch1('z_step')
	assert dorsal_up_z_step == 3
	contents_sample1_ventral_up = imaging_channel_contents_sample1 & {'ventral_up':True}
	ventral_up_z_step = contents_sample1_ventral_up.fetch1('z_step')
	assert ventral_up_z_step == 4
	""" Make sure a ProcessingResolutionRequest() entry was made for the 
	1.3x/ventral up combo """
	restrict_dict_sample1_res = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			ventral_up=1)
	processing_resolution_contents_sample1 = db_lightsheet.Request.ProcessingResolutionRequest() & restrict_dict_sample1_res
	assert len(processing_resolution_contents_sample1) == 1

def test_add_ventral_up_channel_individual_sample(test_client,
	test_cleared_multisample_multichannel_request_nonadmin,
	test_login_imager):
	
	""" Test that clicking the button to add
	a ventral up channel in an
	individual sample section of the imaging batch form 
	creates a duplicate channel row with a ventral up channel.
	"""

	""" Check that originally there is only 1 db entry for channel 488 """
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='488')
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 1

	""" Make sure the "add flipped channel" button appears in the sample table for channel 488 """
	response1 = test_client.get(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		follow_redirects=True)
	parsed_html = BeautifulSoup(response1.data,features="html.parser")
	table_tag_sample1 = parsed_html.find('table',
		attrs={'id':'sample_0_resolution_1.3x_table'})
	table_row_tags_sample1 = table_tag_sample1.find_all('tr')
	ch488_row_sample1 = table_row_tags_sample1[1].find_all('td')
	channel_name_ch488_sample1 = ch488_row_sample1[0]
	add_flipped_button = parsed_html.find('input',
		attrs={'id':'sample_forms-0-image_resolution_forms-0-channel_forms-0-add_flipped_channel_button'})
	assert add_flipped_button != None


	data2 = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-add_flipped_channel_button':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',		
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		}
	response2 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data2,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response2.data
	""" Check that there are now two channel 488 db entries for sample1 """
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 2
	""" Make sure ventral_up = 1 in this new entry """
	ventral_up_vals = imaging_channel_contents_sample1.fetch('ventral_up')
	assert ventral_up_vals[0] == 0
	assert ventral_up_vals[1] == 1
	""" Now make sure the add flipped button is not in the original ch488 row anymore
	We don't want this button there because the flipped channel has already been made! """
	parsed_html = BeautifulSoup(response2.data,features="html.parser")
	table_tag_sample1 = parsed_html.find('table',
		attrs={'id':'sample_0_resolution_1.3x_table'})
	table_row_tags_sample1 = table_tag_sample1.find_all('tr')
	ch488_row_sample1 = table_row_tags_sample1[1].find_all('td')
	channel_name_ch488_sample1 = ch488_row_sample1[0]
	add_flipped_button = parsed_html.find('input',
		attrs={'id':'sample_forms-0-image_resolution_forms-0-channel_forms-0-add_flipped_channel_button'})
	assert add_flipped_button == None
	""" And make sure that the flipped channel displays 'Ventral' in the dorsal or ventral column """
	ch488_flipped_row_sample1 = table_row_tags_sample1[4].find_all('td')
	print(ch488_flipped_row_sample1)
	dorsal_or_ventral = ch488_flipped_row_sample1[3].find_all('div')[0].find_all('p')[0].text
	assert dorsal_or_ventral == 'Ventral'
	""" Now make sure I can delete the flipped channel """
	data3 = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',		
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-ventral_up':1,		
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-delete_channel_button':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-image_resolution':'1.3x',	
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		}
	response3 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data3,
		follow_redirects=True)
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 1
	ventral_up_val = imaging_channel_contents_sample1.fetch1('ventral_up')
	assert ventral_up_val == 0

	""" Test that if the image orientation is not horizontal for a channel
	then clicking the add flipped channel button does not create 
	a flipped channel and results in a validation error """
	data4 = {
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
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_orientation':'sagittal',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-add_flipped_channel_button':True,
		}
	response4 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data4,
		follow_redirects=True)
	this_sample_name = 'sample-002'
	this_image_resolution = '1.3x'
	channel_name_to_flip = '555'
	error_str = (f"Can only add flipped imaging channel if "
				 "image orientation is horizontal for: "
				 f"sample_name: {this_sample_name}, "
				 f"image resolution: {this_image_resolution}, "
				 f"channel: {channel_name_to_flip}")
	assert error_str.encode('utf-8') in response4.data
	""" Make sure no db entry was made for this flipped 555 channel """
	restrict_dict_sample2 = dict(username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			sample_name='sample-002',
			image_resolution='1.3x',
			channel_name='555')
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert len(imaging_channel_contents_sample2) == 1
	ventral_up_ch55_sample2 = imaging_channel_contents_sample2.fetch1('ventral_up')
	assert ventral_up_ch55_sample2 == 0

	""" Finally re-add the flipped 488 channel and
	test that the sample submits with a flipped channel """
	data5 = {
		'image_resolution_batch_forms-0-image_resolution':'1.3x',
		'image_resolution_batch_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_batch_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-add_flipped_channel_button':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',		
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		}

	response5 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data5,
		follow_redirects=True)

	data6 = {
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
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-ventral_up':1,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-tiling_scheme':'1x1',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-z_step':10,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-number_of_z_planes':657,
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-rawdata_subfolder':'test488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-channel_name':'555',
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-tiling_scheme':'1x1',
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-z_step':10,
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-number_of_z_planes':657,
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-rawdata_subfolder':'test555',
		'sample_forms-0-notes_from_imaging':'some custom notes',
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-0-submit':True
	}
	response6 = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name='nonadmin_manysamp_request',
			clearing_batch_number=1,
			imaging_request_number=1,
			imaging_batch_number=1),
		data=data6,
		follow_redirects=True)	
	assert b"Imaging entry for sample sample-001 was successful" in response6.data

def test_imaging_batch_entry_form_new_imaging_request(test_client,
	test_new_imaging_request_nonadmin,
	test_login_imager):
	""" Test the single sample section of the imaging batch entry form.

	First, test validation.

	Then, test adding/deleting channel

	Then, test changing image resolution

	Then, test that the subform submits.

	"""
	imager = current_app.config['IMAGING_ADMINS'][-1] 

	with test_client.session_transaction() as sess:
		sess['user'] = imager

	request_name = 'nonadmin_manysamp_request'
	data_validation = {
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
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-2-sample_name':'sample-003',
		'sample_forms-2-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-2-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-2-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-2-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-2-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-0-submit':True
		}
	response_validation = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name=request_name,
			clearing_batch_number=1,
			imaging_request_number=2,
			imaging_batch_number=1),
		data=data_validation,
		follow_redirects=True)
	assert b'Tiling scheme must not exceed 2x2 for this resolution' in response_validation.data
	assert b'z_step must be a number between 2 and 1000 microns' in response_validation.data
	assert b'Tiling overlap must be a number between 0 and 1' in response_validation.data

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
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-new_channel_dropdown':'790',
		'sample_forms-0-image_resolution_forms-0-new_channel_purpose':'cell_detection',
		'sample_forms-0-image_resolution_forms-0-new_channel_button':True,
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-2-sample_name':'sample-003',
		'sample_forms-2-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-2-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-2-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-2-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-2-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name=request_name,
			clearing_batch_number=1,
			imaging_request_number=2,
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Check that the sample1 channel entry was added in the db """
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name=request_name,
			imaging_request_number=2,
			sample_name='sample-001',
			image_resolution='1.3x',
			channel_name='790')
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 1
	restrict_dict_sample2_ch790 = dict(username='lightserv-test',
			request_name=request_name,
			imaging_request_number=2,
			sample_name='sample-002',
			image_resolution='1.3x',
			channel_name='790')
	imaging_channel_contents_sample2_ch790 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2_ch790
	assert len(imaging_channel_contents_sample2_ch790) == 0
	restrict_dict_sample2_ch647 = dict(username='lightserv-test',
			request_name=request_name,
			imaging_request_number=2,
			sample_name='sample-002',
			image_resolution='1.3x',
			channel_name='647')
	imaging_channel_contents_sample2_ch647 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2_ch647
	assert len(imaging_channel_contents_sample2_ch647) == 1
	

	""" Now check that the new channel is shown in the sample resolution form """
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag_sample1 = parsed_html.find('table',
		attrs={'id':'sample_0_resolution_1.3x_table'})
	table_row_tags_sample1 = table_tag_sample1.find_all('tr')
	assert len(table_row_tags_sample1) == 11
	ch790_row_sample1 = table_row_tags_sample1[-4].find_all('td')
	channel_name_ch790_sample1 = ch790_row_sample1[0].text[0:3]
	assert channel_name_ch790_sample1 == '790'

	table_tag_sample2 = parsed_html.find('table',
		attrs={'id':'sample_1_resolution_1.3x_table'})
	table_row_tags_sample2 = table_tag_sample2.find_all('tr')
	assert len(table_row_tags_sample2) == 8
	ch647_row_sample2 = table_row_tags_sample2[-4].find_all('td')
	channel_name_ch647_sample2 = ch647_row_sample2[0].text[0:3]
	assert channel_name_ch647_sample2 == '647'

	""" Test that deleting a channel in an
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
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-channel_name':'790',
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-image_resolution':'1.3x',	
		'sample_forms-0-image_resolution_forms-0-channel_forms-2-delete_channel_button':True,	
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-2-sample_name':'sample-003',
		'sample_forms-2-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-2-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-2-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-2-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-2-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		}

	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name=request_name,
			clearing_batch_number=1,
			imaging_request_number=2,
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	""" Check that the sample1 channel entry was deleted in the db """
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert len(imaging_channel_contents_sample1) == 0

	""" Test that changing the image resolution in an
	individual sample section of the imaging entry form 
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
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-0-image_resolution_forms-0-new_image_resolution':'1.1x',
		'sample_forms-0-image_resolution_forms-0-update_resolution_button':True,
		'sample_forms-1-sample_name':'sample-002',
		'sample_forms-1-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-1-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-2-sample_name':'sample-003',
		'sample_forms-2-image_resolution_forms-0-image_resolution':'1.3x',
		'sample_forms-2-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-2-image_resolution_forms-0-channel_forms-0-image_resolution':'1.3x',
		'sample_forms-2-image_resolution_forms-0-channel_forms-1-channel_name':'647',
		'sample_forms-2-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		}
	response = test_client.post(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name=request_name,
			clearing_batch_number=1,
			imaging_request_number=2,
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	
	""" Check that the sample-001 image resolution was updated in the db 
	and that sample-001 image resolution was NOT updated in the db"""
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name=request_name,
			sample_name='sample-001',
			imaging_request_number=2,
			channel_name='488')
	restrict_dict_sample2 = dict(username='lightserv-test',
			request_name=request_name,
			sample_name='sample-002',
			imaging_request_number=2,
			channel_name='488')
	print(db_lightsheet.Request.ImagingChannel().fetch(as_dict=True))
	imaging_channel_contents_sample1 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	assert imaging_channel_contents_sample1.fetch1('image_resolution') == '1.1x'
	imaging_channel_contents_sample2 = db_lightsheet.Request.ImagingChannel() & restrict_dict_sample2
	assert imaging_channel_contents_sample2.fetch1('image_resolution') == '1.3x'


	""" Now submit the sample 1 form """

	data = {
		'sample_forms-0-sample_name':'sample-001',
		'sample_forms-0-image_resolution_forms-0-image_resolution':'1.1x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_resolution':'1.1x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-image_orientation':'horizontal',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-left_lightsheet_used':True,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_overlap':0.2,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-tiling_scheme':'1x1',
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-z_step':10,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-number_of_z_planes':657,
		'sample_forms-0-image_resolution_forms-0-channel_forms-0-rawdata_subfolder':'test488',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-image_resolution':'1.1x',
		'sample_forms-0-image_resolution_forms-0-channel_forms-1-channel_name':'647',
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
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-image_resolution':'1.3x',
		'sample_forms-1-image_resolution_forms-0-channel_forms-1-channel_name':'647',
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
			request_name=request_name,
			clearing_batch_number=1,
			imaging_request_number=2,
			imaging_batch_number=1),
		data=data,
		follow_redirects=True)
	assert b'Imaging Entry Form' in response.data
	
	""" Check contents of db were updated """
	restrict_dict_sample1 = dict(username='lightserv-test',
			request_name=request_name,
			sample_name='sample-001',
			image_resolution='1.1x',
			imaging_request_number=2,
			channel_name='488')

	imaging_channel_contents_sample1= db_lightsheet.Request.ImagingChannel() & restrict_dict_sample1
	number_of_z_planes = imaging_channel_contents_sample1.fetch1('number_of_z_planes')
	assert number_of_z_planes == 657
	rawdata_subfolder = imaging_channel_contents_sample1.fetch1('rawdata_subfolder')
	assert rawdata_subfolder == 'test488'
	imaging_request_restrict_dict = dict(username='lightserv-test',
			request_name=request_name,
			sample_name='sample-001',
			imaging_request_number=2)
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & imaging_request_restrict_dict
	assert imaging_request_contents.fetch1('imaging_progress') == "complete"
	
	""" Check that the sample subform is no longer available in the form upon reaccessing"""
	response2 = test_client.get(url_for('imaging.imaging_batch_entry',
			username='lightserv-test',
			request_name=request_name,
			clearing_batch_number=1,
			imaging_request_number=2,
			imaging_batch_number=1),
		follow_redirects=True)

	assert b'Sample has been imaged' in response2.data
	restrict_dict_resolution = dict(username='lightserv-test',
			request_name=request_name,
			sample_name='sample-001',
			image_resolution='1.1x')
	
	""" Check that notes from imaging for that sample were recorded in db """
	imaging_resolution_request_contents = db_lightsheet.Request.ImagingResolutionRequest() & \
		restrict_dict_resolution
	notes_from_imaging = imaging_resolution_request_contents.fetch1('notes_from_imaging')
	assert notes_from_imaging == 'some custom notes'
	
	""" Check that imaging progress and imaging performed date were updated """
	imaging_request_restrict_dict = restrict_dict_resolution = dict(username='lightserv-test',
			request_name=request_name,
			sample_name='sample-001',
			imaging_request_number=2)
	imaging_request_contents = db_lightsheet.Request.ImagingRequest() & \
		imaging_request_restrict_dict
	imaging_progress, imaging_performed_date = imaging_request_contents.fetch1(
		'imaging_progress','imaging_performed_date')
	assert imaging_progress == 'complete'
	assert imaging_performed_date == datetime.now().date()


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
	ventral_up=0
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
							ventral_up=ventral_up,
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

def test_raw_precomputed_pipeline_starts_ventral_up_imaging(test_client,
	test_imaged_request_dorsal_up_and_ventral_up_nonadmin,
	test_delete_spockadmin_db_contents):
	""" Test that the raw precomputed pipeline task runs through
	for a request with ventral up and dorsal up imaging,
	
	Uses a test script on spock which just returns
	job ids. Runs a celery task """
	from lightserv.imaging import tasks
	table_contents = db_spockadmin.RawPrecomputedSpockJob() 
	username='lightserv-test'
	request_name='nonadmin_request'
	sample_name='sample-001'
	imaging_request_number=1
	image_resolution='1.3x'
	channel_name='488'
	ventral_up=1
	channel_index=0
	number_of_z_planes=657
	left_lightsheet_used=True
	right_lightsheet_used=False
	z_step=10
	rawdata_subfolder='test488'
	precomputed_kwargs = dict(username=username,request_name=request_name,
							sample_name=sample_name,imaging_request_number=imaging_request_number,
							image_resolution=image_resolution,channel_name=channel_name,
							ventral_up=ventral_up,
							channel_index=channel_index,number_of_z_planes=number_of_z_planes,
							left_lightsheet_used=left_lightsheet_used,
							right_lightsheet_used=right_lightsheet_used,
							z_step=z_step,rawdata_subfolder=rawdata_subfolder)
	raw_viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
			 f"{request_name}/{sample_name}/"
			 f"imaging_request_{imaging_request_number}/viz/raw")

	if ventral_up:
		channel_viz_dir = os.path.join(raw_viz_dir,f'channel_{channel_name}_ventral_up')
		raw_data_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
						request_name,sample_name,
						f"imaging_request_{imaging_request_number}","rawdata",
						f"resolution_{image_resolution}_ventral_up",f"{rawdata_subfolder}")
		layer_name = f'channel{channel_name}_raw_left_lightsheet_ventral_up'
	else:
		channel_viz_dir = os.path.join(raw_viz_dir,f'channel_{channel_name}')
		raw_data_dir = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],username,
						request_name,sample_name,
						f"imaging_request_{imaging_request_number}","rawdata",
						f"resolution_{image_resolution}",f"{rawdata_subfolder}")	
		layer_name = f'channel{channel_name}_raw_left_lightsheet'
	
	this_viz_dir = os.path.join(channel_viz_dir,'left_lightsheet')
	precomputed_kwargs['lightsheet'] = 'left'
	precomputed_kwargs['viz_dir'] = this_viz_dir
	
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
	test_login_imager):
	""" Test that the imaging table page loads properly for an imaged request """
	from lightserv import db_lightsheet
	
	response = test_client.get(url_for('imaging.imaging_table',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		follow_redirects=True)
	assert b'Imaging Log' in response.data

def test_imaging_table_redirects_incomplete_imaging_nonadmin(test_client,test_cleared_request_nonadmin,
	test_login_imager):
	""" Test that the imaging table page redirects to request_overview
	when imaging request is not yet complete """
	from lightserv import db_lightsheet
	
	response = test_client.get(url_for('imaging.imaging_table',
			username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
			imaging_request_number=1),
		follow_redirects=True)
	assert b'Imaging Log' not in response.data
	assert b'Request overview:' in response.data


""" Tests for new_imaging_request form """

def test_new_imaging_request(test_client,
	test_multisample_multichannel_request_nonadmin):
	""" Make sure I can submit a new imaging request for a request that
	has already been submitted.

	Makes a new imaging request with 2 imaging batches.
	Make sure they are inserted correctly """	
	with test_client.session_transaction() as sess:
		username = sess['user']
	request_name = "nonadmin_manysamp_request"
	response = test_client.post(
		url_for('imaging.new_imaging_request',username=username,
			request_name=request_name,),data={
			'species':'mouse',
			'number_of_samples':3,
			'imaging_samples-0-sample_name':'sample-001',
			'imaging_samples-0-reimaging_this_sample':True,
			'imaging_samples-0-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-0-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-0-image_resolution_forsetup':'1.3x',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-cell_detection':True,
			'imaging_samples-0-image_resolution_forms-0-channel_forms-1-channel_name':'647',
			'imaging_samples-1-sample_name':'sample-002',
			'imaging_samples-1-reimaging_this_sample':True,
			'imaging_samples-1-image_resolution_forms-0-image_resolution':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-1-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-1-image_resolution_forsetup':'1.3x',
			'imaging_samples-1-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-1-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-1-image_resolution_forms-0-channel_forms-1-cell_detection':True,
			'imaging_samples-1-image_resolution_forms-0-channel_forms-1-channel_name':'647',
			'imaging_samples-2-sample_name':'sample-003',
			'imaging_samples-2-reimaging_this_sample':True,
			'imaging_samples-2-image_resolution_forms-0-image_resolution':'3.6x',
			'imaging_samples-2-image_resolution_forms-0-atlas_name':'allen_2017',
			'imaging_samples-2-image_resolution_forms-0-final_orientation':'sagittal',
			'imaging_samples-2-image_resolution_forsetup':'1.3x',
			'imaging_samples-2-image_resolution_forms-0-channel_forms-0-registration':True,
			'imaging_samples-2-image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'imaging_samples-2-image_resolution_forms-0-channel_forms-1-cell_detection':True,
			'imaging_samples-2-image_resolution_forms-0-channel_forms-1-channel_name':'647',
			'submit':True
			},content_type='multipart/form-data',
			follow_redirects=True
		)	

	assert b"core facility requests" in response.data
	assert b"This is a demo request" in response.data
	assert b"New Request Form" not in response.data

	""" Make sure clearing and imaging batches were assigned correctly
	by checking the db contents """

	imaging_batch_1_restrict_dict = {'username':username,
		'request_name':request_name,
		'imaging_request_number':2,
		'clearing_batch_number':1,
		'imaging_batch_number':1}
	imaging_batch_1_contents = db_lightsheet.Request().ImagingBatch() & imaging_batch_1_restrict_dict
	number_of_samples_in_imaging_batch_1 = imaging_batch_1_contents.fetch1('number_in_imaging_batch')
	assert number_of_samples_in_imaging_batch_1 == 2
	imaging_batch_1_sample_contents = db_lightsheet.Request().ImagingBatchSample() & imaging_batch_1_restrict_dict
	samples_in_imaging_batch_1 = imaging_batch_1_sample_contents.fetch('sample_name')
	assert 'sample-003' not in samples_in_imaging_batch_1

	imaging_batch_2_restrict_dict = {'username':username,
		'request_name':request_name,
		'imaging_request_number':2,
		'clearing_batch_number':1,
		'imaging_batch_number':2}
	imaging_batch_2_contents = db_lightsheet.Request().ImagingBatch() & imaging_batch_2_restrict_dict
	number_of_samples_in_imaging_batch_2 = imaging_batch_2_contents.fetch1('number_in_imaging_batch')
	assert number_of_samples_in_imaging_batch_2 == 1
	imaging_batch_2_sample_contents = db_lightsheet.Request().ImagingBatchSample() & imaging_batch_2_restrict_dict
	sample_in_imaging_batch_2 = imaging_batch_2_sample_contents.fetch1('sample_name')
	assert sample_in_imaging_batch_2 == 'sample-003'

	""" Make sure ImagingRequest() table properly inserted """
	imaging_request_restrict_dict = {'username':username,
		'request_name':request_name,
		'imaging_request_number':2}
	imaging_request_contents = db_lightsheet.Request().ImagingRequest() & imaging_request_restrict_dict
	assert len(imaging_request_contents) == 3

	""" Make sure ImagingResolutionRequest() table properly inserted """
	imaging_resolution_1p3x_request_restrict_dict = {'username':username,
		'request_name':request_name,
		'imaging_request_number':2,
		'image_resolution':'1.3x'}
	imaging_resolution_1p3x_request_contents = db_lightsheet.Request().ImagingResolutionRequest() & \
		imaging_resolution_1p3x_request_restrict_dict 
	assert len(imaging_resolution_1p3x_request_contents) == 2
	samples_1p3x_resolution = imaging_resolution_1p3x_request_contents.fetch('sample_name') 
	assert 'sample-001' in samples_1p3x_resolution
	assert 'sample-002' in samples_1p3x_resolution

	imaging_resolution_3p6x_request_restrict_dict = {'username':username,
		'request_name':request_name,
		'imaging_request_number':2,
		'image_resolution':'3.6x'}
	imaging_resolution_3p6x_request_contents = db_lightsheet.Request().ImagingResolutionRequest() & \
		imaging_resolution_3p6x_request_restrict_dict 
	assert len(imaging_resolution_3p6x_request_contents) == 1
	sample_3p6x_resolution = imaging_resolution_3p6x_request_contents.fetch('sample_name') 
	assert sample_3p6x_resolution == 'sample-003'

	""" Make sure ImagingChannel() table properly inserted """
	imaging_channel_1p3x_request_restrict_dict = {'username':username,
		'request_name':request_name,
		'imaging_request_number':2,
		'image_resolution':'1.3x'}
	imaging_channel_1p3x_request_contents = db_lightsheet.Request().ImagingChannel() & \
		imaging_channel_1p3x_request_restrict_dict 
	assert len(imaging_channel_1p3x_request_contents) == 4

	imaging_channel_3p6x_request_restrict_dict = {'username':username,
		'request_name':request_name,
		'imaging_request_number':2,
		'image_resolution':'3.6x'}
	imaging_channel_3p6x_request_contents = db_lightsheet.Request().ImagingChannel() & \
		imaging_channel_3p6x_request_restrict_dict 
	assert len(imaging_channel_3p6x_request_contents) == 2

	""" Make sure ProcessingRequest() table properly inserted """
	processing_request_restrict_dict = {'username':username,
		'request_name':request_name,
		'imaging_request_number':2}
	processing_request_contents = db_lightsheet.Request().ProcessingRequest() & processing_request_restrict_dict
	assert len(processing_request_contents) == 3

	""" Make sure ProcessingResolutionRequest() table properly inserted """
	processing_resolution_1p3x_request_restrict_dict = {'username':username,
		'request_name':request_name,
		'imaging_request_number':2,
		'image_resolution':'1.3x'}
	processing_resolution_1p3x_request_contents = db_lightsheet.Request().ProcessingResolutionRequest() & \
		processing_resolution_1p3x_request_restrict_dict 
	assert len(processing_resolution_1p3x_request_contents) == 2
	samples_1p3x_resolution = processing_resolution_1p3x_request_contents.fetch('sample_name') 
	assert 'sample-001' in samples_1p3x_resolution
	assert 'sample-002' in samples_1p3x_resolution

	processing_resolution_3p6x_request_restrict_dict = {'username':username,
		'request_name':request_name,
		'imaging_request_number':2,
		'image_resolution':'3.6x'}
	processing_resolution_3p6x_request_contents = db_lightsheet.Request().ProcessingResolutionRequest() & \
		processing_resolution_3p6x_request_restrict_dict 
	assert len(processing_resolution_3p6x_request_contents) == 1
	sample_3p6x_resolution = processing_resolution_3p6x_request_contents.fetch('sample_name') 
	assert sample_3p6x_resolution == 'sample-003'