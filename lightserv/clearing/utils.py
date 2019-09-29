from flask import redirect, url_for
from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
									  uDiscoForm, iDiscoPlusForm, iDiscoEduForm )
import os.path
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

def determine_clearing_route(clearing_protocol,experiment_id):

	if clearing_protocol == 'iDISCO+_immuno':
		return redirect(url_for('clearing.iDISCOplus_entry',experiment_id=experiment_id))
	else:
		return redirect(url_for('main.home'))

def determine_clearing_form(clearing_protocol,existing_form):
	if clearing_protocol == 'iDISCO+': 
		form = iDiscoPlusForm(existing_form)
	elif clearing_protocol == 'iDISCO abbreviated clearing':
		form = iDiscoAbbreviatedForm(existing_form)
	elif clearing_protocol == 'uDISCO':
		form = uDiscoForm(existing_form)
	elif clearing_protocol == 'iDISCO+_immuno':
		form = iDiscoPlusImmunoForm(existing_form)
	elif clearing_protocol == 'iDISCO_EdU':
		form = iDiscoEduForm()
	return form

def add_clearing_calendar_entry(date,summary):
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
	creds = None
	# The file token.pickle stores the user's access and refresh tokens, and is
	# created automatically when the authorization flow completes for the first
	# time.
	if os.path.exists('token.pickle'):
		with open('token.pickle', 'rb') as token:
			creds = pickle.load(token)
	# If there are no (valid) credentials available, let the user log in.
	if not creds or not creds.valid:
		if creds and creds.expired and creds.refresh_token:
			creds.refresh(Request())
		else:
			flow = InstalledAppFlow.from_client_secrets_file(
				'credentials.json', SCOPES)
			creds = flow.run_local_server(port=0)
		# Save the credentials for the next run
		with open('token.pickle', 'wb') as token:
			pickle.dump(creds, token)

	service = build('calendar', 'v3', credentials=creds)

	# Call the Calendar API
	# print('Getting the upcoming 10 events')
	events_result = service.events().insert(calendarId='primary', 
										  body=all_day_event).execute()