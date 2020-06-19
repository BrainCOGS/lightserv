from flask import url_for
import tempfile
import webbrowser
from lightserv import db_lightsheet
from bs4 import BeautifulSoup 
from datetime import datetime

""" tests for raw_data_setup() """

def test_raw_data_setup_form_loads(test_client,
	precomputed_raw_complete_viz_nonadmin):
	""" Test that the raw data setup form loads
	for a request where precomputed raw pipelines 
	are complete for all imaging channels in this request """
	username = 'lightserv-test'
	request_name = 'viz_processed'
	sample_name = 'viz_processed-001'
	imaging_request_number=1
	response = test_client.get(url_for('neuroglancer.raw_data_setup',
		username=username,
		request_name=request_name,sample_name=sample_name,
		imaging_request_number=imaging_request_number),
			follow_redirects=True)
	assert b'Raw Data Visualization Setup Form' in response.data 

	""" Now make sure that there are 3 rows in the second table,
	which is the one that has the checkboxes for the user
	to fill out which channels/light sheets they want to display in Neuroglancer
	"""
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tags = parsed_html.find_all('table')
	assert len(table_tags) == 2
	checkbox_table = table_tags[1]
	row_tags = checkbox_table.find_all('tr')
	assert len(row_tags) == 3

	""" Make sure that the left light sheet td in both content rows
	has a checkbox and the right light sheet td in both content rows 
	has "N/A" """

	header_row = row_tags[0].find_all('th')
	# data_row = table_row_tags[1].find_all('td')
	for ii,col in enumerate(header_row):
		if col.text == 'Left lightsheet':
			left_lightsheet_column_index = ii
			right_lightsheet_column_index = ii+1
			break
	ch488_row = row_tags[1].find_all('td')
	ch647_row = row_tags[2].find_all('td')
	ch488_left_lightsheet_td = ch488_row[left_lightsheet_column_index]
	checkboxes_in_left_lightsheet_td = ch488_left_lightsheet_td.find_all('input',attrs={'type':'checkbox'})
	assert len(checkboxes_in_left_lightsheet_td) == 1
	
	ch488_right_lightsheet_td = ch488_row[right_lightsheet_column_index]
	assert ch488_right_lightsheet_td.text.strip() == "N/A" # strip() needed to get rid of newlines on either end

def test_raw_data_setup_form_submits(test_client,
	precomputed_raw_complete_viz_nonadmin,test_take_down_cloudv_and_ng_containers):
	""" Test that the I can submit a POST request to the 
	raw data setup form to generate a Neuroglancer link.

	"""
	username = 'lightserv-test'
	request_name = 'viz_processed'
	sample_name = 'viz_processed-001'
	imaging_request_number=1
	response = test_client.post(url_for('neuroglancer.raw_data_setup',
		username=username,
		request_name=request_name,sample_name=sample_name,
		imaging_request_number=imaging_request_number),
			data = {'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'image_resolution_forms-0-channel_forms-0-viz_left_lightsheet':True,
			'image_resolution_forms-0-channel_forms-1-channel_name':'647',
			'image_resolution_forms-0-channel_forms-1-viz_left_lightsheet':True,
			},
			follow_redirects=True)
	assert b'Raw Data Visualization Setup Form' not in response.data 
	assert b'Links to view your raw data in neuroglancer' in response.data

	

def test_general_data_setup_form_loads_with_just_raw(test_client,
	precomputed_raw_complete_viz_nonadmin):
	""" Test that the general data setup form loads
	for a request where only the precomputed raw pipelines 
	are complete for all imaging channels in this request """
	username = 'lightserv-test'
	request_name = 'viz_processed'
	sample_name = 'viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	response = test_client.get(url_for('neuroglancer.general_data_setup',
		username=username,
		request_name=request_name,sample_name=sample_name,
		imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number),
			follow_redirects=True)
	assert b'Data Visualization Setup Form' in response.data 

	""" Now make sure that there are 3 rows in the second table,
	the raw data setup table 
	"""
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tags = parsed_html.find_all('table')
	assert len(table_tags) == 2
	checkbox_table = table_tags[1]
	row_tags = checkbox_table.find_all('tr')
	assert len(row_tags) == 3

	""" Make sure that the left light sheet td in both content rows
	has a checkbox and the right light sheet td in both content rows 
	has "N/A" """

	header_row = row_tags[0].find_all('th')
	for ii,col in enumerate(header_row):
		if col.text == 'Visualize Left lightsheet?':
			left_lightsheet_column_index = ii
			right_lightsheet_column_index = ii+1
			break
	ch488_row = row_tags[1].find_all('td')
	ch647_row = row_tags[2].find_all('td')
	ch488_left_lightsheet_td = ch488_row[left_lightsheet_column_index]
	checkboxes_in_left_lightsheet_td = ch488_left_lightsheet_td.find_all('input',attrs={'type':'checkbox'})
	assert len(checkboxes_in_left_lightsheet_td) == 1

	ch488_right_lightsheet_td = ch488_row[right_lightsheet_column_index]
	assert ch488_right_lightsheet_td.text.strip() == "N/A" # strip() needed to get rid of newlines on either end

def test_general_data_setup_form_loads_with_raw_and_blended(test_client,
	precomputed_single_tile_pipeline_raw_and_blended_viz_nonadmin):
	""" Test that the general data setup form loads
	for a request where the precomputed raw and blended pipelines 
	are complete for all imaging channels in this request. """
	username = 'lightserv-test'
	request_name = 'viz_processed'
	sample_name = 'viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	response = test_client.get(url_for('neuroglancer.general_data_setup',
		username=username,
		request_name=request_name,sample_name=sample_name,
		imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number),
			follow_redirects=True)
	assert b'Data Visualization Setup Form' in response.data 

	""" Now make sure that there are 3 rows in the second table,
	the raw data setup table 
	"""
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tags = parsed_html.find_all('table')
	""" Make sure there are 3 total tables - the overview, raw table and blended table """
	assert len(table_tags) == 3

def test_general_data_setup_form_loads_with_all_pipelines_single_tile(test_client,
	precomputed_single_tile_pipeline_complete_viz_nonadmin):
	""" Test that the general data setup form loads
	for a request where all of the precomputed pipelines 
	for single tile imaging are completed for all imaging channels in this request.
	This includes raw, blended, downsized and registered pipelines. """
	username = 'lightserv-test'
	request_name = 'viz_processed'
	sample_name = 'viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	response = test_client.get(url_for('neuroglancer.general_data_setup',
		username=username,
		request_name=request_name,sample_name=sample_name,
		imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number),
			follow_redirects=True)
	assert b'Data Visualization Setup Form' in response.data 

	""" Now make sure that there are 3 rows in the second table,
	the raw data setup table 
	"""
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tags = parsed_html.find_all('table')
	""" Make sure there are 5 total tables - the overview, raw table,
	blended table, downsampled table and registered table """
	assert len(table_tags) == 5
