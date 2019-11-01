import os,sys
from flask import Flask, session
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from lightserv.config import Config
import datajoint as dj
from lightserv.tests.make_test_schemata import create_test_schema
import socket
from celery import Celery


cel = Celery(__name__,broker='amqp://localhost//',
	backend='db+mysql+pymysql://ahoag:p@sswd@localhost:3306/ahoag_celery')

dj.config['database.user'] = 'ahoag'
if socket.gethostname() == 'braincogs00.pni.princeton.edu':
	dj.config['database.password'] = 'gaoha'
else:
	dj.config['database.password'] = 'p@sswd'

''' Initialize all the extensions outside of our app so 
we can use them for multiple apps if we want. Don't want to tie 
them to a single app in the create_app() function below '''

print("RUNNING IN FLASK_MODE:",os.environ['FLASK_MODE'])
def set_schema():
	if os.environ['FLASK_MODE'] == 'DEV':
		db_lightsheet = dj.create_virtual_module('lightsheet_demo','ahoag_lightsheet_demo',create_schema=True) # creates the schema if it does not already exist. Can't add tables from within the app because create_schema=False
		db_microscope = dj.create_virtual_module('microscope_demo','ahoag_microscope_demo',create_schema=True)
		# db = dj.create_virtual_module('ahoag_lightsheet_test','ahoag_lightsheet_test')
	elif os.environ['FLASK_MODE'] == 'TEST':
		test_schema = create_test_schema() 
		db_lightsheet = dj.create_virtual_module('ahoag_lightsheet_test','ahoag_lightsheet_test')
		db_microscope = dj.create_virtual_module('ahoag_microscope_test','ahoag_microscope_test',create_schema=True)

	return db_lightsheet,db_microscope
db_lightsheet,db_microscope = set_schema()

# bcrypt = Bcrypt()
# login_manager = LoginManager()
# login_manager.login_view = 'users.login' # function name - like the url_for() argument. 
# This is how the login manager knows where to redirect us when a page requires a login
# login_manager.login_message_category = 'info' # bootstrap class - a blue alert
mail = Mail()

def create_app(config_class=Config):
	""" Create the flask app instance"""
	app = Flask(__name__)
	csrf = CSRFProtect(app)
	app.config.from_object(config_class)
	cel.conf.update(app.config)
	# db.init_app(app)
	# login_manager.init_app(app)
	mail.init_app(app)
	# from lightserv.users.routes import users
	from lightserv.experiments.routes import experiments
	from lightserv.main.routes import main
	from lightserv.ontology.routes import ontology
	from lightserv.clearing.routes import clearing
	from lightserv.microscope.routes import microscope
	from lightserv.errors.handlers import errors

	# app.register_blueprint(users)
	app.register_blueprint(experiments)
	app.register_blueprint(main)
	app.register_blueprint(ontology)
	app.register_blueprint(clearing)
	app.register_blueprint(microscope)
	app.register_blueprint(errors)
	return app
