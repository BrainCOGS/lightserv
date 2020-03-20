# config.py
""" This file contains the setup for the app,
for both testing and deployment """

import os
import datajoint as dj
from datetime import timedelta

# Base class which I will inherit for use with DEV and TEST configs
class BaseConfig(object):
	DEBUG = True
	SECRET_KEY = os.environ.get('SECRET_KEY')
	# SQLALCHEMY_DATABASE_URI = 'db+mysql+pymysql://ahoag:gaoha@localhost:3306/ahoag_lightsheet_admin'
	IMAGING_ADMINS = ['ahoag','jduva','zmd']
	PROCESSING_ADMINS = ['ahoag','jduva','zmd']
	CLEARING_ADMINS = ['ahoag','ll3','jduva','zmd']
	IMAGING_MODES = ['registration','injection_detection','probe_detection','cell_detection','generic_imaging']
	DATA_BUCKET_ROOTPATH = '/jukebox/LightSheetData/lightserv_testing'
	IMAGING_CHANNELS = ['488','555','647','790']
	WTF_CSRF_TIME_LIMIT = 24*3600 # seconds (24 hours)
	# WTF_CSRF_TIME_LIMIT = 1 #
	ATLAS_NAME_FILE_DICTIONARY = {
	'allen_2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/average_template_25_sagittal_forDVscans.tif',
	'allen_pre2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/average_template_25_sagittal_forDVscans.tif',
	'princeton_mouse_atlas:':'/jukebox/LightSheetTransfer/atlas/sagittal_atlas_20um_iso.tif'}
	ATLAS_ANNOTATION_FILE_DICTIONARY = {
	'allen_2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/annotation_2017_25um_sagittal_forDVscans_16bit.tif',
	'allen_pre2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/annotation_template_25_sagittal_forDVscans.tif',
	'princeton_mouse_atlas:':'/jukebox/LightSheetTransfer/atlas/annotation_sagittal_atlas_20um_iso_16bit.tif'
	}
	PROCESSING_CODE_DIR = '/jukebox/wang/ahoag/lightsheet_py3'
	# CLEARING_CALENDAR_ID = '8kvbhcbo0smdg394f79eh45gfc@group.calendar.google.com' # the real clearing calendar
	CLEARING_CALENDAR_ID = 'skq68osl830f13tfgv6i0kq750@group.calendar.google.com' # the test calendar for the time being
	dj.config['safemode'] = True 
	# CELERY_BROKER_URL='amqp://localhost//',
	# CELERY_RESULT_BACKEND=f'db+mysql+pymysql://ahoag:p@sswd@localhost:3307/ahoag_celery_test'
	# BROKER_USE_SSL = True
	

# The default config
class Config(BaseConfig):
	SECRET_KEY = os.environ.get('SECRET_KEY')
	CELERYBEAT_SCHEDULE = {
		'processsing_job_status_checker': {
		'task': 'lightserv.processing.tasks.processing_job_status_checker',
		'schedule': timedelta(seconds=5)
		},
		# 'ng_viewer_cleanser': {
		# 'task': 'lightserv.neuroglancer.routes.ng_viewer_checker',
		# 'schedule': timedelta(seconds=15)
		# },
		# 'rawprecomp_job_status_checker': {
		# 'task': 'lightserv.imaging.tasks.check_raw_precomputed_statuses',
		# 'schedule': timedelta(seconds=15)
		# },
	}
	
class TestConfig(BaseConfig):
	TESTING = True
	WTF_CSRF_ENABLED = False # disables the csrf token validation in forms
	dj.config['safemode'] = False
	CLEARING_CALENDAR_ID = 'skq68osl830f13tfgv6i0kq750@group.calendar.google.com' # the test calendar for the time being
	CELERY_BROKER_URL='amqp://localhost//',
	CELERY_RESULT_BACKEND=f'db+mysql+pymysql://ahoag:p@sswd@localhost:3307/ahoag_celery_test'
	MAIL_USERNAME = os.environ.get('EMAIL_USER')
	MAIL_PASSWORD = os.environ.get('EMAIL_PASS')
