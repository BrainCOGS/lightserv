from flask import url_for
import tempfile
import webbrowser
from lightserv import db_lightsheet
from bs4 import BeautifulSoup 
from datetime import datetime

def test_raw_data_setup_form_loads(test_client,precomputed_raw_complete_viz_nonadmin):
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
	# assert is_archival == "yes"

