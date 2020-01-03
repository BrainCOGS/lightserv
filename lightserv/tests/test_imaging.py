from flask import url_for
import tempfile
import webbrowser
from lightserv import db_lightsheet
from bs4 import BeautifulSoup 
from datetime import datetime

def test_ahoag_access_imaging_manager(test_client,test_cleared_request_ahoag):
	""" Test that ahoag can access the imaging task manager
	and see the single entry made and cleared by ahoag  """
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'Admin request' in response.data 

def test_nonadmin_access_imaging_manager(test_client,test_cleared_request_ahoag,test_login_nonadmin):
	""" Test that Manuel (ms81, a nonadmin) can access the clearing task manager
	but cannot see his entry because he did not designate himself as the clearer
	and cannot see ahoag's entry because he is a not a clearing admin. """
	response = test_client.get(url_for('clearing.clearing_manager')
		, follow_redirects=True)
	assert b'Clearing management GUI' in response.data
	assert b'Nonadmin request' not in response.data 
	# assert b'Admin request' not in response.data 

def test_zmd_access_imaging_manager(test_client,test_cleared_request_ahoag,
	test_cleared_request_nonadmin,test_login_zmd):
	""" Test that Zahra (zmd, an imaging admin) can access the imaging task manager
	and see entries made by multiple users """
	response = test_client.get(url_for('imaging.imaging_manager')
		, follow_redirects=True)
	assert b'Imaging management GUI' in response.data
	assert b'Admin request' in response.data 
	assert b'Nonadmin request' in response.data 

# def test_abbreviated_clearing_entry_form_loads(test_client,test_single_request_nonadmin,test_login_ll3):
# 	""" Test that ll3 can access a clearing entry form  """
# 	# response = test_client.get(url_for('requests.all_requests'))
# 	response = test_client.get(url_for('clearing.clearing_entry',username="ms81",
# 			request_name="Nonadmin request",
# 			clearing_protocol="iDISCO abbreviated clearing",
# 			antibody1="",antibody2="",
# 			clearing_batch_number=1),
# 			follow_redirects=True,
# 		)	
# 	assert b'Clearing Entry Form' in response.data
# 	assert b'Protocol: iDISCO abbreviated clearing' in response.data
 
# def test_abbreviated_clearing_entry_form_submits(test_client,test_single_request_nonadmin,test_login_ll3):
# 	""" Test that ll3 can submit a clearing entry form 
# 	and it redirects her back to the clearing task manager  """
# 	# response = test_client.get(url_for('requests.all_requests'))
# 	now = datetime.now()
# 	print(now)
# 	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
# 		dehydr_pbs_wash1_notes='some notes',submit=True)
# 	response = test_client.post(url_for('clearing.clearing_entry',username="ms81",
# 			request_name="Nonadmin request",
# 			clearing_protocol="iDISCO abbreviated clearing",
# 			antibody1="",antibody2="",
# 			clearing_batch_number=1),
# 		data = data,
# 		follow_redirects=True,
# 		)	
	
# 	assert b'Clearing management GUI' in response.data
	
# 	""" Make sure clearing_progress is now updated """
# 	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & 'username="ms81"' & \
# 	'request_name="Nonadmin request"' & 'clearing_protocol="iDISCO abbreviated clearing"' & \
# 			'antibody1=""' & 'antibody2=""'
# 	clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
# 	assert clearing_progress == 'complete'
	
# 	""" Make sure the clearing batch is now in the correct table in the manager """
# 	parsed_html = BeautifulSoup(response.data,features="html.parser")
# 	table_tag = parsed_html.body.find('table',attrs={'id':'horizontal_already_cleared_table'})
# 	table_row_tag = table_tag.find_all('tr')[1] # the 0th row is the headers
# 	td_tags = table_row_tag.find_all('td')
# 	assert td_tags[1].text == "iDISCO abbreviated clearing" and \
# 	td_tags[2].text == "" and td_tags[3].text == "" and td_tags[4].text == 'Nonadmin request'

# def test_mouse_clearing_entry_forms_load(test_client,test_request_all_mouse_clearing_protocols_ahoag,test_login_ll3):
# 	""" Test that ll3 can access the clearing entry forms
# 	for all mouse clearing protocols  """

# 	response_abbreviated_clearing = test_client.get(url_for('clearing.clearing_entry',
# 			username="ahoag",
# 			request_name="All mouse clearing protocol request",
# 			clearing_protocol="iDISCO abbreviated clearing",
# 			antibody1="",antibody2="",
# 			clearing_batch_number=1),
# 			follow_redirects=True,
# 		)	
# 	assert b'Clearing Entry Form' in response_abbreviated_clearing.data
# 	assert b'Protocol: iDISCO abbreviated clearing' in response_abbreviated_clearing.data

# 	response_idiscoplus_immuno_clearing = test_client.get(url_for('clearing.clearing_entry',
# 			username="ahoag",
# 			request_name="All mouse clearing protocol request",
# 			clearing_protocol="iDISCO+_immuno",
# 			antibody1="test antibody for immunostaining",antibody2="",
# 			clearing_batch_number=2),
# 			follow_redirects=True,
# 		)	
# 	assert b'Clearing Entry Form' in response_idiscoplus_immuno_clearing.data
# 	assert b'Protocol: iDISCO+_immuno' in response_idiscoplus_immuno_clearing.data

# 	response_udisco_clearing = test_client.get(url_for('clearing.clearing_entry',
# 			username="ahoag",
# 			request_name="All mouse clearing protocol request",
# 			clearing_protocol="uDISCO",
# 			antibody1="",antibody2="",
# 			clearing_batch_number=3),
# 			follow_redirects=True,
# 		)	
# 	assert b'Clearing Entry Form' in response_udisco_clearing.data
# 	assert b'Protocol: uDISCO' in response_udisco_clearing.data

# 	response_idisco_edu_clearing = test_client.get(url_for('clearing.clearing_entry',
# 			username="ahoag",
# 			request_name="All mouse clearing protocol request",
# 			clearing_protocol="iDISCO_EdU",
# 			antibody1="",antibody2="",
# 			clearing_batch_number=4),
# 			follow_redirects=True,
# 		)	
# 	assert b'Clearing Entry Form' in response_idisco_edu_clearing.data
# 	assert b'Protocol: iDISCO_EdU' in response_idisco_edu_clearing.data

# def test_mouse_clearing_entry_forms_update(test_client,test_request_all_mouse_clearing_protocols_ahoag,test_login_ll3):
# 	""" Test that ll3 can hit the update buttons in the clearing entry forms
# 	for all mouse clearing protocols and the database is actually updated and the 
# 	form is re-loaded with the updated field auto-filled """
# 	now = datetime.now()
# 	now_proper_format = now.strftime('%Y-%m-%dT%H:%M')
# 	data_abbreviated_clearing = dict(time_pbs_wash1=now_proper_format,time_pbs_wash1_submit=True)
	
# 	response_abbreviated_clearing = test_client.post(url_for('clearing.clearing_entry',
# 			username="ahoag",
# 			request_name="All mouse clearing protocol request",
# 			clearing_protocol="iDISCO abbreviated clearing",
# 			antibody1="",antibody2="",
# 			clearing_batch_number=1),
# 			follow_redirects=True,
# 		data=data_abbreviated_clearing
# 		)	
# 	assert b'Clearing Entry Form' in response_abbreviated_clearing.data
# 	assert b'Protocol: iDISCO abbreviated clearing' in response_abbreviated_clearing.data
# 	assert now_proper_format.encode('utf-8') in response_abbreviated_clearing.data

# 	data_idiscoplus_immuno_clearing = dict(time_dehydr_pbs_wash1=now_proper_format,time_dehydr_pbs_wash1_submit=True)
# 	response_idiscoplus_immuno_clearing = test_client.post(url_for('clearing.clearing_entry',
# 			username="ahoag",
# 			request_name="All mouse clearing protocol request",
# 			clearing_protocol="iDISCO+_immuno",
# 			antibody1="test antibody for immunostaining",antibody2="",
# 			clearing_batch_number=2),
# 			follow_redirects=True,
# 		data=data_idiscoplus_immuno_clearing
# 		)	
# 	assert b'Clearing Entry Form' in response_idiscoplus_immuno_clearing.data
# 	assert b'Protocol: iDISCO+_immuno' in response_idiscoplus_immuno_clearing.data
# 	assert now_proper_format.encode('utf-8') in response_idiscoplus_immuno_clearing.data

# 	data_udisco_clearing = dict(time_dehydr_pbs_wash1=now_proper_format,time_dehydr_pbs_wash1_submit=True)
# 	response_udisco_clearing = test_client.post(url_for('clearing.clearing_entry',
# 			username="ahoag",
# 			request_name="All mouse clearing protocol request",
# 			clearing_protocol="uDISCO",
# 			antibody1="",antibody2="",
# 			clearing_batch_number=3),
# 			follow_redirects=True,
# 		data=data_udisco_clearing
# 		)	
# 	assert b'Clearing Entry Form' in response_udisco_clearing.data
# 	assert b'Protocol: uDISCO' in response_udisco_clearing.data
# 	assert now_proper_format.encode('utf-8') in response_udisco_clearing.data

# 	data_idisco_edu_clearing = dict(time_dehydr_pbs_wash1=now_proper_format,time_dehydr_pbs_wash1_submit=True)
# 	response_idisco_edu_clearing = test_client.post(url_for('clearing.clearing_entry',
# 			username="ahoag",
# 			request_name="All mouse clearing protocol request",
# 			clearing_protocol="iDISCO_EdU",
# 			antibody1="",antibody2="",
# 			clearing_batch_number=4),
# 			follow_redirects=True,
# 		data=data_idisco_edu_clearing
# 		)	
# 	assert b'Clearing Entry Form' in response_idisco_edu_clearing.data
# 	assert b'Protocol: iDISCO_EdU' in response_idisco_edu_clearing.data
# 	assert now_proper_format.encode('utf-8') in response_idisco_edu_clearing.data

# 	# response_udisco_clearing = test_client.get(url_for('clearing.clearing_entry',
# 	# 		username="ahoag",
# 	# 		request_name="All mouse clearing protocol request",
# 	# 		clearing_protocol="uDISCO",
# 	# 		antibody1="",antibody2="",
# 	# 		clearing_batch_number=3),
# 	# 		follow_redirects=True,
# 	# 	)	
# 	# assert b'Clearing Entry Form' in response_udisco_clearing.data
# 	# assert b'Protocol: uDISCO' in response_udisco_clearing.data

# 	# response_idisco_edu_clearing = test_client.get(url_for('clearing.clearing_entry',
# 	# 		username="ahoag",
# 	# 		request_name="All mouse clearing protocol request",
# 	# 		clearing_protocol="iDISCO_EdU",
# 	# 		antibody1="",antibody2="",
# 	# 		clearing_batch_number=4),
# 	# 		follow_redirects=True,
# 	# 	)	
# 	# assert b'Clearing Entry Form' in response_idisco_edu_clearing.data
# 	# assert b'Protocol: iDISCO_EdU' in response_idisco_edu_clearing.data
