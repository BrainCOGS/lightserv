from flask import redirect, url_for
from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
									  iDiscoAbbreviatedRatForm, uDiscoForm, iDiscoEduForm,
									  experimentalForm)
from lightserv.clearing.tables import (IdiscoPlusTable,IdiscoAbbreviatedTable,
							  IdiscoAbbreviatedRatTable,UdiscoTable,
							  IdiscoEdUTable)
from lightserv import db_lightsheet
import os.path
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime,timedelta
	

def determine_clearing_form(clearing_protocol,existing_form):
	if clearing_protocol == 'iDISCO abbreviated clearing':
		form = iDiscoAbbreviatedForm(existing_form)
	elif clearing_protocol == 'iDISCO abbreviated clearing (rat)':
		form = iDiscoAbbreviatedRatForm(existing_form)
	elif clearing_protocol == 'uDISCO':
		form = uDiscoForm(existing_form)
	elif clearing_protocol == 'iDISCO+_immuno':
		form = iDiscoPlusImmunoForm(existing_form)
	elif clearing_protocol == 'iDISCO_EdU':
		form = iDiscoEduForm()
	elif clearing_protocol == 'experimental':
		form = experimentalForm()

	return form

def determine_clearing_dbtable(clearing_protocol):
	if clearing_protocol == 'iDISCO+_immuno': 
		dbtable = db_lightsheet.Request.IdiscoPlusClearing
	elif clearing_protocol == 'iDISCO abbreviated clearing':
		dbtable = db_lightsheet.Request.IdiscoAbbreviatedClearing
	elif clearing_protocol == 'iDISCO abbreviated clearing (rat)':
		dbtable = db_lightsheet.Request.IdiscoAbbreviatedRatClearing
	elif clearing_protocol == 'uDISCO':
		dbtable = db_lightsheet.Request.UdiscoClearing
	elif clearing_protocol == 'iDISCO_EdU':
		dbtable = db_lightsheet.Request.IdiscoEdUClearing
	elif clearing_protocol == 'experimental':
		dbtable = db_lightsheet.Request.ExperimentalClearing

	return dbtable

def determine_clearing_table(clearing_protocol):
	if clearing_protocol == 'iDISCO+_immuno': 
		table = IdiscoPlusTable
	elif clearing_protocol == 'iDISCO abbreviated clearing':
		table = IdiscoAbbreviatedTable
	elif clearing_protocol == 'iDISCO abbreviated clearing (rat)':
		table = IdiscoAbbreviatedRatTable
	elif clearing_protocol == 'uDISCO':
		table = UdiscoTable
	elif clearing_protocol == 'iDISCO_EdU':
		table = IdiscoEdUTable
	return table	

def add_clearing_calendar_entry(date,summary,calendar_id):
	SCOPES = ['https://www.googleapis.com/auth/calendar.events']
	date = str(date)
	all_day_event = {
	  'summary': summary,
	  'location': '',
	  'description': '',
	  'start': {
		'date': date,
		'timeZone': 'America/New_York',
	  },
	  'end': {
		'date': date,
		'timeZone': 'America/New_York',
	  },
	  'attendees': [
	  ],
	  'reminders': {
		'useDefault': False,
		'overrides': [
		  {'method': 'email', 'minutes': 24 * 60},
		  {'method': 'popup', 'minutes': 10},
		],
	  },
	}
	
	with open('token.pickle', 'rb') as token:
		creds = pickle.load(token)

	service = build('calendar', 'v3', credentials=creds)

	# Call the Calendar API
	events_result = service.events().insert(calendarId=calendar_id, 
											  body=all_day_event).execute()
	return

def retrieve_clearing_calendar_entry(calendar_id):
	""" Retrieves the first clearing calendar event.
	Used for testing only """
	SCOPES = ['https://www.googleapis.com/auth/calendar.events']
	
	creds = None
	# The file token.pickle stores the user's access and refresh tokens, and is
	# created automatically when the authorization flow completes for the first
	# time.
	with open('token.pickle', 'rb') as token:
		creds = pickle.load(token)
	
	service = build('calendar', 'v3', credentials=creds)

	# Call the Calendar API
	now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
	events_result = service.events().list(calendarId=calendar_id,
										maxResults=1, singleEvents=True,
										orderBy='startTime').execute()
	events = events_result.get('items', [])
	event = events[0]
	return event

def delete_clearing_calendar_entry(calendar_id,event_id):
	""" Deletes a clearing calendar event given a calendar id and event id
	Used for testing only """
	SCOPES = ['https://www.googleapis.com/auth/calendar.events']
	
	creds = None
	# The file token.pickle stores the user's access and refresh tokens, and is
	# created automatically when the authorization flow completes for the first
	# time.
	with open('token.pickle', 'rb') as token:
		creds = pickle.load(token)


	service = build('calendar', 'v3', credentials=creds)

	# Call the Calendar API
	service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

	return