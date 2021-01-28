from flask import url_for, current_app
import tempfile
import webbrowser
from lightserv import db_lightsheet
from bs4 import BeautifulSoup 
from datetime import datetime, date, timedelta
from lightserv.clearing.utils import (retrieve_clearing_calendar_entry,
	delete_clearing_calendar_entry)
import lorem # lorem ipsum generator

""" Testing clearing_manager() """

def test_ll3_access_clearing_manager(test_client,test_single_sample_request_nonadmin,test_single_sample_request_ahoag,test_login_ll3):
	""" Test that Laura (ll3, a clearing admin) can access the clearing task manager
	and see entries made by multiple users """
	response = test_client.get(url_for('clearing.clearing_manager')
		, follow_redirects=True)
	assert b'Clearing management GUI' in response.data
	assert b'admin_request' in response.data 
	assert b'nonadmin_request' in response.data 

def test_nonadmin_access_clearing_manager(test_client,test_single_sample_request_ahoag,test_single_sample_request_nonadmin):
	""" Test that Manuel (lightserv-test, a nonadmin) can access the clearing task manager
	but cannot see his entry because he did not designate himself as the clearer
	and cannot see ahoag's entry because he is a not a clearing admin. """
	response = test_client.get(url_for('clearing.clearing_manager')
		, follow_redirects=True)
	assert b'Clearing management GUI' in response.data
	assert b'nonadmin_request' not in response.data 
	assert b'admin_request' not in response.data 

def test_nonadmin_can_see_self_clearing_request(test_client,test_self_clearing_and_imaging_request):
	""" Test that lightserv-test, a nonadmin can see 
	their entry because they designated themselves as the clearer
	"""
	response = test_client.get(url_for('clearing.clearing_manager')
		, follow_redirects=True)
	assert b'Clearing management GUI' in response.data
	assert b'self_clearing_and_imaging_request' in response.data 

def test_sort_clearing_manager_all_columns(test_client,test_two_requests_ahoag):
	""" Check that sorting all columns of all requests table works 

	Uses the test_two_requests_ahoag fixture
	to insert a two requests into the database as ahoag. 
	"""

	for column_name in ['datetime_submitted','expected_handoff_date','clearing_protocol','antibody1','antibody2',
	'username','request_name','clearer','species']:
		response = test_client.get(
			url_for('clearing.clearing_manager',sort=column_name,direction='desc'),
			follow_redirects=True)
		assert b'Clearing management GUI' in response.data

""" Testing clearing_entry() """

def test_abbreviated_clearing_entry_form(test_client,
	test_single_sample_request_nonadmin,test_login_ll3):
	""" Test that ll3 can access a clearing entry form  """
	response = test_client.get(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="nonadmin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
			follow_redirects=True,
		)	
	assert b'Clearing Entry Form' in response.data
	assert b'Protocol: iDISCO abbreviated clearing' in response.data

	""" Test that ll3 can submit a clearing entry form 
	and it redirects her back to the clearing task manager  """
	# response = test_client.get(url_for('requests.all_requests'))
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)
	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="nonadmin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	
	
	assert b'Clearing management GUI' in response.data
	
	""" Make sure clearing_progress is now updated """
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & 'username="lightserv-test"' & \
	'request_name="nonadmin_request"' & 'clearing_protocol="iDISCO abbreviated clearing"' & \
			'antibody1=""' & 'antibody2=""'
	clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
	assert clearing_progress == 'complete'
	
	""" Make sure the clearing batch is now in the correct table in the manager """
	parsed_html = BeautifulSoup(response.data,features="html.parser")
	table_tag = parsed_html.body.find('table',attrs={'id':'horizontal_already_cleared_table'})
	table_row_tag = [1] # the 0th row is the headers
	table_rows = table_tag.find_all('tr')
	header_row = table_rows[0].find_all('th')
	data_row = table_rows[1].find_all('td')
	for ii,col in enumerate(header_row):
		if col.text == 'clearing protocol':
			clearing_protocol_column_index = ii
		elif col.text == 'antibody1':
			antibody1_column_index = ii
		elif col.text == 'antibody2':
			antibody2_column_index = ii
		elif col.text == 'request name':
			request_name_column_index = ii
	clearing_protocol_retrieved = data_row[clearing_protocol_column_index].text
	antibody1_retrieved = data_row[antibody1_column_index].text
	antibody2_retrieved = data_row[antibody2_column_index].text
	request_name_retrieved = data_row[request_name_column_index].text
	assert clearing_protocol_retrieved == "iDISCO abbreviated clearing"
	assert antibody1_retrieved == ""
	assert antibody2_retrieved == ""
	assert request_name_retrieved == "nonadmin_request"

def test_all_mouse_clearing_entry_forms(test_client,
	test_request_all_mouse_clearing_protocols_ahoag,test_login_ll3):
	""" Test that the "Push date to calendar" buttons on the clearing entry form
	actually push to a test calendar.

	Uses the test_cleared_request_nonadmin fixture to insert and clear 
	a request with username='ahoag' and clearer='ll3'  """
	username = 'ahoag'

	today = date.today()
	yesterday = today-timedelta(days=1)
	tomorrow = today+timedelta(days=1)
	today_proper_format = today.strftime('%Y-%m-%d')
	data = dict(pbs_date=today_proper_format,
		pbs_date_submit=True)
	response = test_client.post(url_for('clearing.clearing_entry',username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data=data,
		follow_redirects=True
	)
	assert b'Event added to Clearing Calendar. Check the calendar.' in response.data
	''' Now check that the event was really added to the calendar '''
	event = retrieve_clearing_calendar_entry(calendar_id=current_app.config['CLEARING_CALENDAR_ID'])
	event_summary = event['summary']
	assert event_summary == 'ahoag iDISCO abbreviated clearing pbs'
	event_id = event['id']
	delete_clearing_calendar_entry(calendar_id=current_app.config['CLEARING_CALENDAR_ID'],
		event_id=event_id)


	""" Test that ll3 can ACCESS each of the 
	clearing entry forms
	for the various mouse clearing protocols  """

	response_abbreviated_clearing = test_client.get(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
			follow_redirects=True,
		)	
	assert b'Clearing Entry Form' in response_abbreviated_clearing.data
	assert b'Protocol: iDISCO abbreviated clearing' in response_abbreviated_clearing.data

	response_idiscoplus_immuno_clearing = test_client.get(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO+_immuno",
			antibody1="test antibody for immunostaining",antibody2="",
			clearing_batch_number=2),
			follow_redirects=True,
		)	
	assert b'Clearing Entry Form' in response_idiscoplus_immuno_clearing.data
	assert b'Protocol: iDISCO+_immuno' in response_idiscoplus_immuno_clearing.data

	response_udisco_clearing = test_client.get(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="uDISCO",
			antibody1="",antibody2="",
			clearing_batch_number=3),
			follow_redirects=True,
		)	
	assert b'Clearing Entry Form' in response_udisco_clearing.data
	assert b'Protocol: uDISCO' in response_udisco_clearing.data

	response_idisco_edu_clearing = test_client.get(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO_EdU",
			antibody1="",antibody2="",
			clearing_batch_number=4),
			follow_redirects=True,
		)	
	assert b'Clearing Entry Form' in response_idisco_edu_clearing.data
	assert b'Protocol: iDISCO_EdU' in response_idisco_edu_clearing.data

	""" Test that ll3 can hit the update buttons in the clearing entry forms
	for all mouse clearing protocols and the database is actually updated and the 
	form is re-loaded with the updated field auto-filled """
	now = datetime.now()
	now_proper_format = now.strftime('%Y-%m-%dT%H:%M')
	data_abbreviated_clearing = dict(time_pbs_wash1=now_proper_format,time_pbs_wash1_submit=True)
	
	""" iDISCO abbreviated """
	response_abbreviated_clearing = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
			follow_redirects=True,
		data=data_abbreviated_clearing
		)	
	assert b'Clearing Entry Form' in response_abbreviated_clearing.data
	assert b'Protocol: iDISCO abbreviated clearing' in response_abbreviated_clearing.data
	assert now_proper_format.encode('utf-8') in response_abbreviated_clearing.data

	""" iDISCO+ immunostaining """
	data_idiscoplus_immuno_clearing = dict(time_dehydr_pbs_wash1=now_proper_format,time_dehydr_pbs_wash1_submit=True)
	response_idiscoplus_immuno_clearing = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO+_immuno",
			antibody1="test antibody for immunostaining",antibody2="",
			clearing_batch_number=2),
			follow_redirects=True,
		data=data_idiscoplus_immuno_clearing
		)	
	assert b'Clearing Entry Form' in response_idiscoplus_immuno_clearing.data
	assert b'Protocol: iDISCO+_immuno' in response_idiscoplus_immuno_clearing.data
	assert now_proper_format.encode('utf-8') in response_idiscoplus_immuno_clearing.data

	""" update a second field in the same form """
	data_idiscoplus_immuno_clearing2 = dict(antibody1_lot='abc-123',antibody1_lot_submit=True)
	response_idiscoplus_immuno_clearing2 = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO+_immuno",
			antibody1="test antibody for immunostaining",antibody2="",
			clearing_batch_number=2),
			follow_redirects=True,
		data=data_idiscoplus_immuno_clearing2
		)	
	assert b'Clearing Entry Form' in response_idiscoplus_immuno_clearing2.data
	assert b'Protocol: iDISCO+_immuno' in response_idiscoplus_immuno_clearing2.data
	assert b"abc-123" in response_idiscoplus_immuno_clearing2.data

	""" uDISCO """

	data_udisco_clearing = dict(time_dehydr_pbs_wash1=now_proper_format,time_dehydr_pbs_wash1_submit=True)
	response_udisco_clearing = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="uDISCO",
			antibody1="",antibody2="",
			clearing_batch_number=3),
			follow_redirects=True,
		data=data_udisco_clearing
		)	
	assert b'Clearing Entry Form' in response_udisco_clearing.data
	assert b'Protocol: uDISCO' in response_udisco_clearing.data
	assert now_proper_format.encode('utf-8') in response_udisco_clearing.data

	""" iDISCO_EdU """
	data_idisco_edu_clearing = dict(time_dehydr_pbs_wash1=now_proper_format,time_dehydr_pbs_wash1_submit=True)
	response_idisco_edu_clearing = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO_EdU",
			antibody1="",antibody2="",
			clearing_batch_number=4),
			follow_redirects=True,
		data=data_idisco_edu_clearing
		)	
	assert b'Clearing Entry Form' in response_idisco_edu_clearing.data
	assert b'Protocol: iDISCO_EdU' in response_idisco_edu_clearing.data
	assert now_proper_format.encode('utf-8') in response_idisco_edu_clearing.data

	""" Test that ll3 can submit the clearing forms
	for each of the mouse clearing protocols
	and each time it redirects her back to the clearing task manager  """

	""" iDISCO abbreviated """
	now = datetime.now()
	data = dict(time_pbs_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_pbs_wash1_notes='some notes',submit=True)
	response = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	
	
	assert b'Clearing management GUI' in response.data
	
	""" Make sure clearing_progress is now updated """
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'username="{username}"' & \
	'request_name="All_mouse_clearing_protocol_request"' & 'clearing_protocol="iDISCO abbreviated clearing"' & \
			'antibody1=""' & 'antibody2=""'
	clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
	assert clearing_progress == 'complete'
	

	""" iDISCO+ immunostaining """
	data_idiscoplus_immuno_clearing = dict(time_dehydr_pbs_wash1=now_proper_format,
		dehydr_pbs_wash1_notes='some notes',submit=True)
	response_idiscoplus_immuno_clearing = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO+_immuno",
			antibody1="test antibody for immunostaining",antibody2="",
			clearing_batch_number=2),
			follow_redirects=True,
		data=data_idiscoplus_immuno_clearing
		)	
	assert b'Clearing management GUI' in response.data
	
	""" Make sure clearing_progress is now updated """
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'username="{username}"' & \
	'request_name="All_mouse_clearing_protocol_request"' & 'clearing_protocol="iDISCO+_immuno"' & \
			'antibody1="test antibody for immunostaining"' & 'antibody2=""'
	clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
	assert clearing_progress == 'complete'
	
	""" uDISCO """
	data_udisco_clearing = dict(time_dehydr_pbs_wash1=now_proper_format,
		dehydr_pbs_wash1_notes='some notes',submit=True)
	response_idiscoplus_immuno_clearing = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="uDISCO",
			antibody1="",antibody2="",
			clearing_batch_number=3),
			follow_redirects=True,
		data=data_udisco_clearing
		)	
	assert b'Clearing management GUI' in response.data
	
	# """ Make sure clearing_progress is now updated """
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'username="{username}"' & \
	'request_name="All_mouse_clearing_protocol_request"' & 'clearing_protocol="uDISCO"' & \
			'antibody1=""' & 'antibody2=""'
	clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
	assert clearing_progress == 'complete'

	""" iDISCO_EdU """
	data_idisco_edu_clearing = dict(time_dehydr_pbs_wash1=now_proper_format,
		dehydr_pbs_wash1_notes='some notes',submit=True)
	response_idiscoplus_immuno_clearing = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO_EdU",
			antibody1="",antibody2="",
			clearing_batch_number=4),
			follow_redirects=True,
		data=data_idisco_edu_clearing
		)	
	assert b'Clearing management GUI' in response.data
	
	# """ Make sure clearing_progress is now updated """
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'username="{username}"' & \
	'request_name="All_mouse_clearing_protocol_request"' & 'clearing_protocol="iDISCO_EdU"' & \
			'antibody1=""' & 'antibody2=""'
	clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
	assert clearing_progress == 'complete'

def test_all_rat_clearing_entry_forms(test_client,
	test_request_all_rat_clearing_protocols_ahoag,test_login_ll3):
	""" Test that ll3 can ACCESS the clearing entry form
	for the rat clearing protocol  """
	username = 'ahoag'

	""" iDISCO abbreviated clearing (rat) """
	response_abbreviated_clearing = test_client.get(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_rat_clearing_protocol_request",
			clearing_protocol="iDISCO abbreviated clearing (rat)",
			antibody1="",antibody2="",
			clearing_batch_number=1),
			follow_redirects=True,
		)	
	assert b'Clearing Entry Form' in response_abbreviated_clearing.data
	assert b'Protocol: iDISCO abbreviated clearing (rat)' in response_abbreviated_clearing.data

	""" uDISCO (rat) """
	response_udisco_clearing = test_client.get(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_rat_clearing_protocol_request",
			clearing_protocol="uDISCO (rat)",
			antibody1="",antibody2="",
			clearing_batch_number=2),
			follow_redirects=True,
		)	
	assert b'Clearing Entry Form' in response_udisco_clearing.data
	assert b'Protocol: uDISCO (rat)' in response_udisco_clearing.data

	""" Test that ll3 can hit the update buttons in the clearing entry forms
	for all mouse clearing protocols and the database is actually updated and the 
	form is re-loaded with the updated field auto-filled """
	
	""" iDISCO abbreviated clearing (rat) """
	now = datetime.now()
	now_proper_format = now.strftime('%Y-%m-%dT%H:%M')
	data_abbreviated_clearing = dict(time_pbs_wash1=now_proper_format,time_pbs_wash1_submit=True)
	
	response_abbreviated_clearing = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_rat_clearing_protocol_request",
			clearing_protocol="iDISCO abbreviated clearing (rat)",
			antibody1="",antibody2="",
			clearing_batch_number=1),
			follow_redirects=True,
		data=data_abbreviated_clearing
		)	
	assert b'Clearing Entry Form' in response_abbreviated_clearing.data
	assert b'Protocol: iDISCO abbreviated clearing (rat)' in response_abbreviated_clearing.data
	assert now_proper_format.encode('utf-8') in response_abbreviated_clearing.data

	""" uDISCO (rat) """
	now = datetime.now()
	now_proper_format = now.strftime('%Y-%m-%dT%H:%M')
	data_udisco_clearing = dict(time_dehydr_pbs_wash1=now_proper_format,
		time_dehydr_pbs_wash1_submit=True)
	
	response_udisco_clearing = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_rat_clearing_protocol_request",
			clearing_protocol="uDISCO (rat)",
			antibody1="",antibody2="",
			clearing_batch_number=2),
			follow_redirects=True,
		data=data_udisco_clearing
		)	
	assert b'Clearing Entry Form' in response_udisco_clearing.data
	assert b'Protocol: uDISCO (rat)' in response_udisco_clearing.data
	assert now_proper_format.encode('utf-8') in response_udisco_clearing.data

	""" Test that rat clearing forms submit """
	""" iDISCO abbreviated clearing (rat) """
	now = datetime.now()
	data = dict(time_dehydr_methanol_20percent_wash1=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_methanol_20percent_wash1_notes='some notes',submit=True)
	response = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_rat_clearing_protocol_request",
			clearing_protocol="iDISCO abbreviated clearing (rat)",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	
	
	assert b'Clearing management GUI' in response.data
	
	# """ Make sure clearing_progress is now updated """
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'username="{username}"' & \
	'request_name="All_rat_clearing_protocol_request"' & 'clearing_protocol="iDISCO abbreviated clearing (rat)"' 
	clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
	assert clearing_progress == 'complete'

	""" uDISCO (rat) """
	now = datetime.now()
	data = dict(time_dehydr_butanol_30percent=now.strftime('%Y-%m-%dT%H:%M'),
		dehydr_butanol_30percent_notes='some notes',submit=True)
	response = test_client.post(url_for('clearing.clearing_entry',
			username=username,
			request_name="All_rat_clearing_protocol_request",
			clearing_protocol="uDISCO (rat)",
			antibody1="",antibody2="",
			clearing_batch_number=2),
		data = data,
		follow_redirects=True,
		)	
	
	assert b'Clearing management GUI' in response.data
	
	# """ Make sure clearing_progress is now updated """
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'username="{username}"' & \
	'request_name="All_rat_clearing_protocol_request"' & 'clearing_protocol="uDISCO (rat)"' 
	clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
	assert clearing_progress == 'complete'
	
def test_validate_clearing_form(test_client,test_single_sample_request_nonadmin,test_login_ll3):
	""" Test that hitting the "Push date to calendar" without putting anything in 
	results in a flash message and a redirect to the same page

	Uses the test_cleared_request_nonadmin fixture to insert and clear 
	a request with username='ahoag' and clearer='ll3'  """
	data = dict(pbs_date='',
		pbs_date_submit=True)
	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="nonadmin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data=data,
		follow_redirects=True
	)
	assert b'Please enter a valid date to push to the Clearing Calendar' in response.data
	assert b'Clearing Entry Form' in response.data

	""" Test that providing invalid parameters to the clearing entry route 
	will result in a redirect to the requests.all_requests() route """

	response = test_client.get(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="bad_request_name",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
			follow_redirects=True,
		)	
	assert b'Clearing Entry Form' not in response.data
	assert b'core facility requests' in response.data

	""" Test that hitting the "update" buttton in a previous 
	clearing form entry saved the data and that data are pre-filled 
	in a new session. """

	""" First issue a POST request to update the form """
	now = datetime.now()
	now_proper_format = now.strftime('%Y-%m-%dT%H:%M')
	data_abbreviated_clearing = dict(time_pbs_wash1=now_proper_format,time_pbs_wash1_submit=True)
	response_post = test_client.post(url_for('clearing.clearing_entry',
			username="lightserv-test",
			request_name="nonadmin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
			follow_redirects=True,
		data=data_abbreviated_clearing
		)	

	""" Now a GET request to check that the field is auto-filled """
	response_get = test_client.get(url_for('clearing.clearing_entry',
			username="lightserv-test",
			request_name="nonadmin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1)
		)	
	assert now_proper_format.encode('utf-8') in response_get.data

	""" Test that if one of the buttons in the form has a bad name (or a bad or malicious post request happens),
	the form does not submit and a redirect to the 500 error page occurs.

	Uses the test_cleared_request_nonadmin fixture to insert and clear 
	a request with username='ahoag' and clearer='ll3'  """
	data = dict(bad_button_submit=True)
	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="nonadmin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data=data,
		follow_redirects=True
	)
	assert b'Something went wrong (500)' in response.data

	""" Test that if user enters too much text for one of the notes fields
	they get a validation error

	Uses the test_cleared_request_nonadmin fixture to insert and clear 
	a request with username='ahoag' and clearer='ll3'  """
	data = dict(dehydr_methanol_20percent_wash1_notes=lorem.text(),
		dehydr_methanol_20percent_wash1_notes_submit=True) # the lorem ipsum text is longer than this notes field will accept
	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="nonadmin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data=data,
		follow_redirects=True
	)
	assert b'Field cannot be longer than 250 characters.' in response.data

def test_completed_clearing_form_is_readonly(test_client,test_cleared_request_ahoag):
	""" Test that a POST request via an "update" button to a previously
	completed clearing entry form produces a flash message saying read only 
	and does not update the db """
	
	""" First issue a POST request to submit the form """
	data_abbreviated_clearing = dict(dehydr_methanol_20percent_wash1_notes='notes for 20 percent methanol',
		dehydr_methanol_20percent_wash1_notes_submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',
			username="ahoag",
			request_name="admin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
			follow_redirects=True,
			data=data_abbreviated_clearing
		)	
	assert b'This page is read only' in response.data
	assert b'notes for 20 percent methanol' not in response.data

	""" Test that a POST request to submit the entire form 
	produces a flash message saying read only 
	and does not update the db """

	data_abbreviated_clearing = dict(dehydr_methanol_20percent_wash1_notes='notes for 20 percent methanol',
		submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',
			username="ahoag",
			request_name="admin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
			follow_redirects=True,
			data=data_abbreviated_clearing
		)
			
	assert b'This page is read only' in response.data
	assert b'notes for 20 percent methanol' not in response.data

def test_clearing_entry_experimental_rat_nonadmin(test_client,test_experimental_clearing_request_nonadmin,
	test_login_ll3,test_delete_request_db_contents):
	""" Clears the single request by 'lightserv-test' (with clearer='ll3') 
	using the "experimental" clearing method for a rat 
	
	Runs test_login_ll3 next so that 'll3' gets logged in and can do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""
	now = datetime.now()
	data = dict(link_to_clearing_spreadsheet='https://docs.google.com/spreadsheets/d/1A83HVyy1bEhctqArwt4EiT637M8wBxTFodobbt1jrXI/edit#gid=895577002',
		submit=True)

	response = test_client.post(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="nonadmin_experimental_request",
			clearing_protocol="experimental",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		data = data,
		follow_redirects=True,
		)	
	assert b'Clearing management GUI' in response.data
	
	""" Make sure clearing_progress is now updated """
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & 'username="lightserv-test"' & \
	'request_name="nonadmin_experimental_request"' & 'clearing_protocol="experimental"' & \
			'antibody1=""' & 'antibody2=""'
	clearing_progress = clearing_batch_contents.fetch1('clearing_progress')
	assert clearing_progress == 'complete'
	
def test_clearing_notes_appear_in_clearing_entry_form(test_client,test_multisample_request_nonadmin_clearing_notes,
	test_login_ll3,test_delete_request_db_contents):
	""" Clears the request with multiple samples by 'lightserv-test' (with clearer='ll3')  
	
	Runs test_login_ll3 next so that 'll3' gets logged in and can do the clearing

	Uses the test_delete_request_db_contents fixture, which means that 
	all db entries are deleted upon teardown of this fixture
	"""

	response = test_client.get(url_for('clearing.clearing_entry',username="lightserv-test",
			request_name="nonadmin_request_clearing_notes",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		follow_redirects=True)
	assert b'Clearing Entry Form' in response.data
	assert b'sample 1 notes' in response.data
	assert b'sample 2 notes' in response.data
	
""" Test clearing_table() """

def test_mouse_clearing_tables_have_db_content(test_client,test_cleared_all_mouse_clearing_protocols_ahoag):
	""" Test that ahoag can access the clearing table
	and see the contents of a single clearing entry 

	Uses the test_cleared_request_ahoag fixture to insert and clear 
	a request with username='ahoag' and clearer='ahoag'  """
	response_abbreviated = test_client.get(url_for('clearing.clearing_table',username="ahoag",
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1)
	)

	assert b'Clearing Log' in response_abbreviated.data
	assert b'some notes' in response_abbreviated.data
	assert datetime.now().strftime('%Y-%m-%d %H').encode('utf-8') in response_abbreviated.data 

	response_idiscoplus = test_client.get(url_for('clearing.clearing_table',
			username="ahoag",
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO+_immuno",
			antibody1="test antibody for immunostaining",antibody2="",
			clearing_batch_number=2),
		follow_redirects=True,
		)	

	assert b'Clearing Log' in response_idiscoplus.data
	assert b'some notes' in response_idiscoplus.data
	assert datetime.now().strftime('%Y-%m-%d %H').encode('utf-8') in response_idiscoplus.data 

	response_udisco = test_client.get(url_for('clearing.clearing_table',username="ahoag",
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="uDISCO",
			antibody1="",antibody2="",
			clearing_batch_number=3)
	)

	assert b'Clearing Log' in response_udisco.data
	assert b'some notes' in response_udisco.data
	assert datetime.now().strftime('%Y-%m-%d %H').encode('utf-8') in response_udisco.data 

	response_idisco_edu = test_client.get(url_for('clearing.clearing_table',username="ahoag",
			request_name="All_mouse_clearing_protocol_request",
			clearing_protocol="iDISCO_EdU",
			antibody1="",antibody2="",
			clearing_batch_number=4)
	)

	assert b'Clearing Log' in response_idisco_edu.data
	assert b'some notes' in response_idisco_edu.data
	assert datetime.now().strftime('%Y-%m-%d %H').encode('utf-8') in response_idisco_edu.data 

def test_clearing_table_no_access_nonadmin(test_client,test_cleared_request_ahoag,test_login_nonadmin):
	""" Test that Manuel (lightserv-test, a nonadmin) cannot access the clearing table 
	for contents for which he is not the clearer. Instead he should get 
	redirected to the welcome page.

	Uses the test_cleared_request_ahoag fixture to insert and clear 
	a request with username='ahoag' and clearer='ahoag'  """
	response = test_client.get(url_for('clearing.clearing_table',username="ahoag",
			request_name="admin_request",
			clearing_protocol="iDISCO abbreviated clearing",
			antibody1="",antibody2="",
			clearing_batch_number=1),
		follow_redirects=True
	)
	assert b'Welcome to the Brain Registration and Histology Core Facility' in response.data
	assert b'Clearing Log' not in response.data

def test_rat_clearing_table_has_db_content(test_client,test_cleared_rat_request):
	""" Test that ahoag can access the clearing table
	and see the contents of a single clearing entry 

	Uses the test_cleared_request_ahoag fixture to insert and clear 
	a request with username='ahoag' and clearer='ahoag'  """
	response_abbreviated = test_client.get(url_for('clearing.clearing_table',username="lightserv-test",
			request_name="Nonadmin_rat_request",
			clearing_protocol="iDISCO abbreviated clearing (rat)",
			antibody1="",antibody2="",
			clearing_batch_number=1)
	)

	assert b'Clearing Log' in response_abbreviated.data
	assert b'some rat notes' in response_abbreviated.data
	assert datetime.now().strftime('%Y-%m-%d %H').encode('utf-8') in response_abbreviated.data 


""" Test clearing_table() """

def test_antibody_table_access(test_client,test_delete_request_db_contents):
	""" Test that ll3 can see all entries
	to the antibody table """
	date = '2021-01-02'
	date_corr_format = datetime.strptime(date,'%Y-%m-%d')
	""" Make some inserts first """
	insert_dict1 = {
	'username':'ejdennis',
	'request_name':'test_antibody1',
	'date':date_corr_format,	
	'brief_descriptor': 'test rat antibody request', 
	'animal_model':  'rat',
	'primary_antibody':  'some primary',
	'primary_order_info':  '',
	'secondary_antibody':  'some seconary',
	'primary_concentration':  '1:100',
	'secondary_concentration':  '1:50',
	'secondary_order_info':  '',
	'notes':  'Here are the notes'
	}
	insert_dict2 = {
	'username':'diamanti',
	'request_name':'test_antibody2',
	'date':date_corr_format,	
	'brief_descriptor': 'test mouse antibody request', 
	'animal_model':  'mouse',
	'primary_antibody':  'some primary',
	'primary_order_info':  '',
	'secondary_antibody':  'some seconary',
	'primary_concentration':  '1:100',
	'secondary_concentration':  '1:50',
	'secondary_order_info':  '',
	'notes':  'Here are the notes'
	}
	insert_list = [insert_dict1,insert_dict2]
	db_lightsheet.AntibodyHistory().insert(insert_list)
	""" Log in as ll3 """
	with test_client.session_transaction() as sess:
		sess['user'] = 'll3'
	response = test_client.get(url_for('clearing.antibody_history'),
	)
	assert b'Antibody Testing History' in response.data

	assert b'ejdennis' in response.data
	assert b'diamanti' in response.data

	""" Make sure a nonadmin cannot see the antibody history entry for a different user """
	""" Log in as lightserv-test """
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	response = test_client.get(url_for('clearing.antibody_history'),
	)
	assert b'ejdennis' not in response.data
	assert b'diamanti' not in response.data
	
	""" Now make sure ejdennis can her entry but not mika's """
	""" Log in as ejdennis """
	with test_client.session_transaction() as sess:
		sess['user'] = 'ejdennis'
	response = test_client.get(url_for('clearing.antibody_history'),
	)
	assert b'ejdennis' in response.data
	assert b'diamanti' not in response.data

	""" Make sure ejdennis can edit her entry """
	kwargs = insert_dict1.copy()
	kwargs['date'] = date
	response = test_client.post(url_for('clearing.edit_antibody_entry',
		**kwargs),data={
		'notes':'updated notes!',
		'submit':True
	},follow_redirects=True,
	)
	assert b'Antibody entry successfully updated' in response.data
	assert b'Antibody Testing History' in response.data
	assert b'updated notes!' in response.data

