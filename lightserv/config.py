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
	ATLAS_NAME_FILE_DICTIONARY = {
	'allen_2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/average_template_25_sagittal_forDVscans.tif',
	'allen_pre2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/average_template_25_sagittal_forDVscans.tif',
	'princeton_mouse_atlas:':'/jukebox/LightSheetTransfer/atlas/sagittal_atlas_20um_iso.tif'}
	ATLAS_ANNOTATION_FILE_DICTIONARY = {
	'allen_2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/annotation_2017_25um_sagittal_forDVscans_16bit.tif',
	'allen_pre2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/annotation_template_25_sagittal_forDVscans.tif',
	'princeton_mouse_atlas:':'/jukebox/LightSheetTransfer/atlas/annotation_sagittal_atlas_20um_iso_16bit.tif'
	}
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