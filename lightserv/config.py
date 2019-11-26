# config.py
""" This file contains the setup for the app,
for both testing and deployment """

import os

# Base class which I will inherit for use with DEV and TEST configs
class BaseConfig(object):
	DEBUG = True
	SECRET_KEY = os.environ.get('SECRET_KEY')
	IMAGING_ADMINS = ['ahoag','jduva','zmd']
	PROCESSING_ADMINS = ['ahoag','jduva','zmd']
	CLEARING_ADMINS = ['ahoag','ll3','zmd']
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

# The default config
class Config(BaseConfig):
	SECRET_KEY = os.environ.get('SECRET_KEY')
	MAIL_SERVER = 'smtp.googlemail.com'
	MAIL_PORT = 587
	MAIL_USE_TLS = True
	MAIL_USERNAME = os.environ.get('EMAIL_USER')
	MAIL_PASSWORD = os.environ.get('EMAIL_PASS')
	
class TestConfig(BaseConfig):
	TESTING = True
	WTF_CSRF_ENABLED = False # disables the csrf token validation in forms
	