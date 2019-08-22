import os,sys
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from lightserv.config import Config
import datajoint as dj
from lightserv.test_schemata import create_test_schema

dj.config['database.user'] = 'ahoag'
dj.config['database.password'] = 'p@sswd'


''' Initialize all the extensions outside of our app so 
we can use them for multiple apps if we want. Don't want to tie 
them to a single app in the create_app() function below '''
# db = SQLAlchemy()

print("RUNNING IN FLASK_MODE:",os.environ['FLASK_MODE'])
def set_schema():
	if os.environ['FLASK_MODE'] == 'DEV':
		db = dj.create_virtual_module('lightsheet_demo','ahoag_lightsheet_demo',create_schema=True) # creates the schema if it does not already exist. Can't add tables from within the app because create_schema=False
	elif os.environ['FLASK_MODE'] == 'TEST':
		test_schema = create_test_schema() 
		db = dj.create_virtual_module('ahoag_lightsheet_test','ahoag_lightsheet_test')
	return db
db = set_schema()

bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'users.login' # function name - like the url_for() argument. 
# This is how the login manager knows where to redirect us when a page requires a login
login_manager.login_message_category = 'info' # bootstrap class - a blue alert
mail = Mail()

def create_app(config_class=Config):
	""" Create the flask app instance"""
	app = Flask(__name__)
	app.config.from_object(config_class)

	# db.init_app(app)
	bcrypt.init_app(app)
	login_manager.init_app(app)
	mail.init_app(app)
	from lightserv.users.routes import users
	from lightserv.experiments.routes import experiments
	from lightserv.main.routes import main
	from lightserv.errors.handlers import errors

	app.register_blueprint(users)
	app.register_blueprint(experiments)
	app.register_blueprint(main)
	app.register_blueprint(errors)
	return app
