# config.py
""" This file contains the setup for the app,
for both testing and deployment """

import os

# The default config
class Config(object):
	SECRET_KEY = os.environ.get('SECRET_KEY')
	SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI')
	MAIL_SERVER = 'smtp.googlemail.com'
	MAIL_PORT = 587
	MAIL_USE_TLS = True
	MAIL_USERNAME = os.environ.get('EMAIL_USER')
	MAIL_PASSWORD = os.environ.get('EMAIL_PASS')
	# APPLICATION_ROOT = "/v01"


class BaseConfig(object):
	DEBUG = False
	# shortened for readability
	SECRET_KEY = '\xbf\xb0\x11\xb1\xcd\xf9\xba\x8bp\x0c...'
	SQLALCHEMY_DATABASE_URI = 'sqlite:///site.db'
	SQLALCHEMY_TRACK_MODIFICATIONS = False # to turn that annoying warning off

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