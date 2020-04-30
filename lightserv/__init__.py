import os,sys
from flask import Flask, session, flash, request, redirect, url_for, render_template
from flask_wtf.csrf import CSRFProtect
from lightserv.config import Config
import datajoint as dj
from datajoint.table import Log
import socket
from celery import Celery
from flask_wtf.csrf import CSRFError
import smtplib
import types

try:
	print("RUNNING IN FLASK_MODE:",os.environ['FLASK_MODE'])
except KeyError:
	print("WARNING. FLASK_MODE environmental variable not found. WARNING")

""" Connect to gmail smtp server """

""" Subclass the send_message method of smtplib.SMTP to NOT send 
the email if FLASK_MODE=='TEST' """
def send_message_conditional(self,message): 
	"self is the smtp_server"
	if os.environ['FLASK_MODE'] == 'TEST': 
		print("not sending email because this is a test") 
	else: 
		print("sending email")
		smtplib.SMTP.send_message(self,message) 
		print("sent email")
funcType = types.MethodType
def smtp_connect():
	# Instantiate a connection object...
	print("Making SMTP connection")
	smtpObj = smtplib.SMTP('smtp.gmail.com',587)
	smtpObj.ehlo()
	smtpObj.starttls()
	smtpObj.login(os.environ.get('EMAIL_USER'),os.environ.get('EMAIL_PASS'))
	smtpObj.send_message = funcType(send_message_conditional,smtpObj)
	print("SMTP connection ready to send message")
	return smtpObj

''' Allow writing python objects to db as blob '''
dj.config["enable_python_native_blobs"] = True

def set_celery_db():
	if os.environ['FLASK_MODE'] == 'DEV':
		cel = Celery(__name__,broker='redis://redis:6379/0',
			backend='redis://redis:6379/0')
	elif os.environ['FLASK_MODE'] == 'TEST':
		cel = Celery(__name__,broker='redis://redis:6379/0',
			backend='redis://redis:6379/0')
	elif os.environ['FLASK_MODE'] == 'PROD':
		cel = Celery(__name__,broker='redis://redis:6379/0',
			backend='redis://redis:6379/0')
	return cel
cel = set_celery_db()

''' Initialize all the extensions outside of our app so 
we can use them for multiple apps if we want. Don't want to tie 
them to a single app in the create_app() function below '''


def set_schema():
	if os.environ['FLASK_MODE'] == 'PROD':
		dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
		dj.config['database.user'] = os.environ['DJ_DB_USER']
		dj.config['database.password'] = os.environ['DJ_DB_PASS']
		db_lightsheet = dj.create_virtual_module('lightsheet','u19lightserv_lightsheet',create_schema=True) # creates the schema if it does not already exist. Can't add tables from within the app because create_schema=False
		db_admin = dj.create_virtual_module('admin','u19lightserv_appcore',create_schema=True)
		db_spockadmin = dj.create_virtual_module('spockadmin','ahoag_spockadmin_demo',create_schema=True)
		db_microscope = dj.create_virtual_module('microscope_demo','ahoag_microscope_demo',create_schema=True)
		db_subject = dj.create_virtual_module('subject','u19_subject',create_schema=False)
		# db_microscope = None
		# db_admin = dj.create_virtual_module('admin','u19lightserv_appcore',create_schema=True)
		# db_logger = Log(dj.conn(), database='ahoag_lightsheet_demo') # Initialize logger
	if os.environ['FLASK_MODE'] == 'DEV':
		dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
		dj.config['database.user'] = os.environ['DJ_DB_USER']
		dj.config['database.password'] = os.environ['DJ_DB_PASS']
		# db_lightsheet = dj.create_virtual_module('lightsheet','u19lightserv_lightsheet',create_schema=True) # creates the schema if it does not already exist. Can't add tables from within the app because create_schema=False
		db_lightsheet = dj.create_virtual_module('lightsheet','ahoag_lightsheet_demo',create_schema=True) # creates the schema if it does not already exist. Can't add tables from within the app because create_schema=False
		db_admin = dj.create_virtual_module('admin','ahoag_admin_demo',create_schema=True)
		db_spockadmin = dj.create_virtual_module('spockadmin','ahoag_spockadmin_demo',create_schema=True)
		db_microscope = dj.create_virtual_module('microscope_demo','ahoag_microscope_demo',create_schema=True)
		db_subject = dj.create_virtual_module('subject','u19_subject',create_schema=False)
		# db_microscope = None
		# db_admin = dj.create_virtual_module('admin','u19lightserv_appcore',create_schema=True)
		# db_logger = Log(dj.conn(), database='ahoag_lightsheet_demo') # Initialize logger
	elif os.environ['FLASK_MODE'] == 'TEST':
		print("Setting up schemas in TEST mode")
		# test_schema = create_test_schema() 
		from schemas import admin,lightsheet,subject
		dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
		dj.config['database.user'] = os.environ['DJ_DB_TEST_USER']
		dj.config['database.password'] = os.environ['DJ_DB_TEST_PASS']
		db_lightsheet = dj.create_virtual_module('ahoag_lightsheet_test','ahoag_lightsheet_test')
		db_microscope = dj.create_virtual_module('ahoag_microscope_test','ahoag_microscope_test',create_schema=True)
		db_admin = dj.create_virtual_module('ahoag_admin_test','ahoag_admin_test',create_schema=True)
		db_spockadmin = dj.create_virtual_module('ahoag_spockadmin_test','ahoag_spockadmin_test',create_schema=True)
		db_subject = dj.create_virtual_module('ahoag_subject_test','ahoag_subject_test',create_schema=True)

	return db_lightsheet,db_microscope,db_admin,db_spockadmin,db_subject

db_lightsheet,db_microscope,db_admin,db_spockadmin,db_subject = set_schema()

def create_app(config_class=Config):
	""" Create the flask app instance"""
	app = Flask(__name__)
	
	# Initialize external libs
	csrf = CSRFProtect(app)
	app.config.from_object(config_class)
	cel.conf.update(app.config)

	# Blueprints
	from lightserv.requests.routes import requests
	from lightserv.main.routes import main
	from lightserv.clearing.routes import clearing
	from lightserv.imaging.routes import imaging
	from lightserv.processing.routes import processing
	from lightserv.taskmanager.routes import taskmanager
	from lightserv.microscope.routes import microscope
	from lightserv.neuroglancer.routes import neuroglancer
	from lightserv.errors.handlers import errors

	app.register_blueprint(requests)
	app.register_blueprint(main)
	app.register_blueprint(clearing)
	app.register_blueprint(imaging)
	app.register_blueprint(processing)
	app.register_blueprint(taskmanager)
	app.register_blueprint(neuroglancer)
	app.register_blueprint(microscope)
	app.register_blueprint(errors)

	@app.errorhandler(CSRFError)
	def handle_csrf_error(e):
		""" If there is an CSRF Error anywhere in the application,
		this function will handle it - brings the user to a 500 error 
		page """
		if e.description =='The CSRF token has expired.':
			csrf_time_limit_seconds = app.config['WTF_CSRF_TIME_LIMIT']
			csrf_time_limit_hours = csrf_time_limit_seconds/3600.
			flash(f"The form expired after {csrf_time_limit_hours} hours. "
			      f"Please continue completing the form within the next {csrf_time_limit_hours} hours.","warning")
		else:
			return render_template('errors/500.html')
		next_url = os.path.join('/',*request.url.split('?')[0].split('/')[3:])
		return redirect(next_url)

	return app
