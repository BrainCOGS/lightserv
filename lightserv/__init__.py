import os,sys
from flask import Flask, session, flash, request, redirect
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from lightserv.config import Config
import datajoint as dj
from datajoint.table import Log
import socket
from celery import Celery
from flask_wtf.csrf import CSRFError

''' Allow writing python objects to db as blob '''
dj.config["enable_python_native_blobs"] = True
cel = Celery(__name__,broker='amqp://localhost//',
	backend=f'db+mysql+pymysql://ahoag:p@sswd@localhost:3307/ahoag_celery_test')

''' Initialize all the extensions outside of our app so 
we can use them for multiple apps if we want. Don't want to tie 
them to a single app in the create_app() function below '''

try:
	print("RUNNING IN FLASK_MODE:",os.environ['FLASK_MODE'])
except KeyError:
	print("WARNING. FLASK_MODE environmental variable not found. WARNING")
def set_schema():
	try:
		if os.environ['FLASK_MODE'] == 'DEV':
			dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
			dj.config['database.user'] = os.environ['DJ_DB_USER']
			dj.config['database.password'] = os.environ['DJ_DB_PASS']
			db_lightsheet = dj.create_virtual_module('lightsheet','u19lightserv_lightsheet',create_schema=True) # creates the schema if it does not already exist. Can't add tables from within the app because create_schema=False
			# db_microscope = dj.create_virtual_module('microscope_demo','ahoag_microscope_demo',create_schema=True)
			db_microscope = None
			db_admin = dj.create_virtual_module('admin','u19lightserv_appcore',create_schema=True)
			# db_logger = Log(dj.conn(), database='ahoag_lightsheet_demo') # Initialize logger
		elif os.environ['FLASK_MODE'] == 'TEST':
			print("Setting up schemas in TEST mode")
			# test_schema = create_test_schema() 
			from schemas import lightsheet
			from schemas import admin
			dj.config['database.host'] = '127.0.0.1'
			dj.config['database.user'] = os.environ['DJ_DB_TEST_USER']
			dj.config['database.password'] = os.environ['DJ_DB_TEST_PASS']
			db_lightsheet = dj.create_virtual_module('ahoag_lightsheet_test','ahoag_lightsheet_test')
			db_microscope = dj.create_virtual_module('ahoag_microscope_test','ahoag_microscope_test',create_schema=True)
			db_admin = dj.create_virtual_module('ahoag_admin_test','ahoag_admin_test',create_schema=True)
	except KeyError:
		return None,None,None
	return db_lightsheet,db_microscope,db_admin

db_lightsheet,db_microscope,db_admin = set_schema()

mail = Mail()

def create_app(config_class=Config):
	""" Create the flask app instance"""
	app = Flask(__name__)
	csrf = CSRFProtect(app)
	app.config.from_object(config_class)
	cel.conf.update(app.config)
	# login_manager.init_app(app)

	mail.init_app(app)
	# from lightserv.users.routes import users
	from lightserv.requests.routes import requests
	from lightserv.main.routes import main
	from lightserv.ontology.routes import ontology
	from lightserv.clearing.routes import clearing
	from lightserv.imaging.routes import imaging
	from lightserv.processing.routes import processing
	from lightserv.taskmanager.routes import taskmanager
	from lightserv.microscope.routes import microscope
	from lightserv.errors.handlers import errors

	# app.register_blueprint(users)
	app.register_blueprint(requests)
	app.register_blueprint(main)
	app.register_blueprint(ontology)
	app.register_blueprint(clearing)
	app.register_blueprint(imaging)
	app.register_blueprint(processing)
	app.register_blueprint(taskmanager)

	app.register_blueprint(microscope)
	app.register_blueprint(errors)

	@app.errorhandler(CSRFError)
	def handle_csrf_error(e):
		csrf_time_limit_seconds = app.config['WTF_CSRF_TIME_LIMIT']
		csrf_time_limit_hours = csrf_time_limit_seconds/3600.
		flash(f"The form expired after {csrf_time_limit_hours} hours. "
		       "Please continue completing the form within the next {csrf_time_limit_hours} hours .","warning")
		next_url = os.path.join('/',*request.url.split('?')[0].split('/')[3:])
		return redirect(next_url)

	return app
