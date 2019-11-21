# config.py
""" This file contains the setup for the app,
for both testing and deployment """

import os

# The default config
class Config(object):
	SECRET_KEY = os.environ.get('SECRET_KEY')
	MAIL_SERVER = 'smtp.googlemail.com'
	MAIL_PORT = 587
	MAIL_USE_TLS = True
	MAIL_USERNAME = os.environ.get('EMAIL_USER')
	MAIL_PASSWORD = os.environ.get('EMAIL_PASS')
	IMAGING_MODES = ['registration','injection_detection','probe_detection','cell_detection']
	RAWDATA_ROOTPATH = '/jukebox/LightSheetData/lightserv_testing'
	IMAGING_CHANNELS = ['488','555','647','790']

	# APPLICATION_ROOT = "/v01"


class BaseConfig(object):
	DEBUG = False
	SECRET_KEY = os.environ.get('SECRET_KEY')

class TestConfig(BaseConfig):
	DEBUG = True
	TESTING = True
	WTF_CSRF_ENABLED = False
	

# The configuration for the lightserv demo for presentation purposes
class DemoConfig(BaseConfig):
	DEBUG = True
	TESTING = True
	# WTF_CSRF_ENABLED = False
	SQLALCHEMY_DATABASE_URI = 'sqlite:///demo_app.db'
	# SQLALCHEMY_DATABASE_URI = 'sqlite:///test_app.db'	

class DevelopmentConfig(BaseConfig):
	DEBUG = True

class ProductionConfig(BaseConfig):
	DEBUG = False