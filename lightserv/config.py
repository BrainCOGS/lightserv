# config.py
""" This file contains the setup for the app,
for both testing and deployment """

import os
import datajoint as dj
from datetime import timedelta

# Base class which I will inherit for use with DEV and TEST configs
class BaseConfig(object):
	SECRET_KEY = os.environ.get('SECRET_KEY')
	IMAGING_ADMINS = ['ahoag','jduva','zmd']
	PROCESSING_ADMINS = ['ahoag','jduva','zmd']
	CLEARING_ADMINS = ['ahoag','ll3','jduva','zmd']
	IMAGING_MODES = ['registration','injection_detection','probe_detection','cell_detection','generic_imaging']
	IMAGING_CHANNELS = ['488','555','647','790']
	ADMINS_TO_EMAIL = ['ahoag'] # for problems with requests/spock jobs
	WTF_CSRF_TIME_LIMIT = 24*3600 # seconds (24 hours)
	# WTF_CSRF_TIME_LIMIT = 1 #
	ATLAS_NAME_FILE_DICTIONARY = {
	'allen_2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/average_template_25_sagittal_forDVscans.tif',
	'allen_pre2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/average_template_25_sagittal_forDVscans.tif',
	'princeton_mouse_atlas':'/jukebox/LightSheetTransfer/atlas/sagittal_atlas_20um_iso.tif'}
	ATLAS_ANNOTATION_FILE_DICTIONARY = {
	'allen_2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/annotation_2017_25um_sagittal_forDVscans_16bit.tif',
	'allen_pre2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/annotation_template_25_sagittal_forDVscans.tif',
	'princeton_mouse_atlas':'/jukebox/LightSheetTransfer/atlas/annotation_sagittal_atlas_20um_iso_16bit.tif'
	}
	PROCESSING_CODE_DIR = '/jukebox/wang/ahoag/brainpipe'
	dj.config['safemode'] = True 
	

class DevConfig(BaseConfig):
	DEBUG = True
	CLEARING_CALENDAR_ID = os.environ.get("TEST_CALENDAR_URL") # the test calendar for the time being
	SECRET_KEY = os.environ.get('SECRET_KEY')
	DATA_BUCKET_ROOTPATH = '/jukebox/LightSheetData/lightserv_pnilsadmin_testing'
	NG_VIEWER_EXPIRE_SECONDS = 60 # seconds (1 minute) time that a neuroglancer viewer and its cloudvolumes are allowed to stay up 
	SPOCK_LSADMIN_USERNAME = 'lightserv-test'
	CELERYBEAT_SCHEDULE = {
		# 'processing_job_status_checker': {
		# 'task': 'lightserv.processing.tasks.processing_job_status_checker',
		# 'schedule': timedelta(seconds=30)
		# },
		# 'processing_job_status_checker_noreg': {
		# 'task': 'lightserv.processing.tasks.processing_job_status_checker_noreg',
		# 'schedule': timedelta(seconds=15)
		# },
		# 'stitchedprecomp_job_ready_checker': {
		# 'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_stitched_data',
		# 'schedule': timedelta(seconds=5)
		# },
		# 'stitchedprecomp_job_status_checker': {
		# 'task': 'lightserv.processing.tasks.stitched_precomputed_job_status_checker',
		# 'schedule': timedelta(seconds=7)
		# },
		# 'ng_viewer_cleanser': {
		# 'task': 'lightserv.neuroglancer.tasks.ng_viewer_checker',
		# 'schedule': timedelta(minutes=2)
		# },
		# 'rawprecomp_job_status_checker': {
		# 'task': 'lightserv.imaging.tasks.check_raw_precomputed_statuses',
		# 'schedule': timedelta(seconds=15)
		# },
		# 'blendedprecomp_job_ready_checker': {
		# 'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_blended_data',
		# 'schedule': timedelta(seconds=30)
		# },
		# 'blendedprecomp_job_status_checker': {
		# 'task': 'lightserv.processing.tasks.blended_precomputed_job_status_checker',
		# 'schedule': timedelta(minutes=1)
		# },
		# 'downsizedprecomp_job_ready_checker': {
		# 'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_downsized_data',
		# 'schedule': timedelta(seconds=35)
		# },
		# 'downsizedprecomp_job_status_checker': {
		# 'task': 'lightserv.processing.tasks.downsized_precomputed_job_status_checker',
		# 'schedule': timedelta(minutes=1)
		# },
		'registeredprecomp_job_ready_checker': {
		'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_registered_data',
		'schedule': timedelta(seconds=3)
		},
		'registeredprecomp_job_status_checker': {
		'task': 'lightserv.processing.tasks.registered_precomputed_job_status_checker',
		'schedule': timedelta(seconds=10)
		},
		
	}
	
class ProdConfig(BaseConfig):
	DEBUG = False
	# CLEARING_CALENDAR_ID = '8kvbhcbo0smdg394f79eh45gfc@group.calendar.google.com' # the real clearing calendar
	CLEARING_CALENDAR_ID = os.environ.get("CLEARING_CALENDAR_URL") # the test calendar for the time being
	SECRET_KEY = os.environ.get('SECRET_KEY')
	DATA_BUCKET_ROOTPATH = '/jukebox/LightSheetData/lightserv'
	NG_VIEWER_EXPIRE_SECONDS = 21600 # 6 hours - time that a neuroglancer viewer and its cloudvolumes are allowed to stay up 
	SPOCK_LSADMIN_USERNAME = 'lightserv-test'

	CELERYBEAT_SCHEDULE = {
		'processing_job_status_checker': {
		'task': 'lightserv.processing.tasks.processing_job_status_checker',
		'schedule': timedelta(minutes=2)
		},
		'processing_job_status_checker_noreg': {
		'task': 'lightserv.processing.tasks.processing_job_status_checker_noreg',
		'schedule': timedelta(minutes=3)
		},
		'stitchedprecomp_job_ready_checker': {
		'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_stitched_data',
		'schedule': timedelta(minutes=5)
		},
		'stitchedprecomp_job_status_checker': {
		'task': 'lightserv.processing.tasks.stitched_precomputed_job_status_checker',
		'schedule': timedelta(minutes=3)
		},
		'ng_viewer_cleanser': {
		'task': 'lightserv.neuroglancer.tasks.ng_viewer_checker',
		'schedule': timedelta(minutes=5)
		},
		'rawprecomp_job_status_checker': {
		'task': 'lightserv.imaging.tasks.check_raw_precomputed_statuses',
		'schedule': timedelta(minutes=3)
		},
		'blendedprecomp_job_ready_checker': {
		'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_blended_data',
		'schedule': timedelta(minutes=5)
		},
		'blendedprecomp_job_status_checker': {
		'task': 'lightserv.processing.tasks.blended_precomputed_job_status_checker',
		'schedule': timedelta(minutes=3)
		},
		'downsizedprecomp_job_ready_checker': {
		'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_downsized_data',
		'schedule': timedelta(minutes=5)
		},
		'downsizedprecomp_job_status_checker': {
		'task': 'lightserv.processing.tasks.downsized_precomputed_job_status_checker',
		'schedule': timedelta(minutes=3)
		},
		'registeredprecomp_job_ready_checker': {
		'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_registered_data',
		'schedule': timedelta(minutes=5)
		},
		'registeredprecomp_job_status_checker': {
		'task': 'lightserv.processing.tasks.registered_precomputed_job_status_checker',
		'schedule': timedelta(minutes=3)
		},
		
	}
class TestConfig(BaseConfig):
	TESTING = True
	WTF_CSRF_ENABLED = False # disables the csrf token validation in forms
	dj.config['safemode'] = False
	DATA_BUCKET_ROOTPATH = '/jukebox/LightSheetData/lightserv_testing'
	CLEARING_CALENDAR_ID = 'skq68osl830f13tfgv6i0kq750@group.calendar.google.com' # the test calendar for the time being
	# CELERY_BROKER_URL='amqp://localhost//',
	# CELERY_RESULT_BACKEND=f'db+mysql+pymysql://ahoag:p@sswd@localhost:3307/ahoag_celery_test'
	MAIL_USERNAME = os.environ.get('EMAIL_USER')
	MAIL_PASSWORD = os.environ.get('EMAIL_PASS')
