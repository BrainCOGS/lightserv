# config.py
""" This file contains the setup for the app,
for both testing and deployment """

import os
import datajoint as dj
from datetime import timedelta

# Base class which I will inherit for use with DEV and TEST configs
class BaseConfig(object):
	MASTER_ADMINS = ['ahoag']
	SECRET_KEY = os.environ.get('SECRET_KEY')
	CLEARING_ADMINS = ['ahoag','ll3','sg3271']
	IMAGING_ADMINS = ['ahoag','ll3','lightserv','sg3271']
	PROCESSING_ADMINS = ['ahoag']
	LAVISION_RESOLUTIONS = ["1.1x","1.3x","2x","4x"]
	SMARTSPIM_RESOLUTIONS = ["3.6x"]
	RESOLUTIONS_NO_PROCESSING = ["2x","3.6x","15x"] # resolutions we are not able to process
	IMAGING_MODES = ['registration','injection_detection','probe_detection','cell_detection','generic_imaging']
	LAVISION_IMAGING_CHANNELS = ['488','555','647','790']
	SMARTSPIM_IMAGING_CHANNELS = ['488','561','642','785']
	ADMINS_TO_EMAIL = ['ahoag'] # for problems with requests/spock jobs
	WTF_CSRF_TIME_LIMIT = None # never expire
	# WTF_CSRF_TIME_LIMIT = 5 # seconds 
	# WTF_CSRF_TIME_LIMIT = 1 #
	ATLAS_NAME_FILE_DICTIONARY = {
	'allen_2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/average_template_25_sagittal_forDVscans.tif',
	'allen_pre2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/average_template_25_sagittal_forDVscans.tif',
	'princeton_mouse_atlas':'/jukebox/LightSheetTransfer/atlas/sagittal_atlas_20um_iso.tif',
	'paxinos':'/jukebox/LightSheetTransfer/atlas/kim_atlas/KimRef_tissue_volume_4brainpipe.tif'
	}
	ATLAS_ANNOTATION_FILE_DICTIONARY = {
	'allen_2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/annotation_2017_25um_sagittal_forDVscans_16bit.tif',
	'allen_pre2017':'/jukebox/LightSheetTransfer/atlas/allen_atlas/annotation_template_25_sagittal_forDVscans.tif',
	'princeton_mouse_atlas':'/jukebox/LightSheetTransfer/atlas/annotation_sagittal_atlas_20um_iso_16bit.tif',
	'paxinos':'/jukebox/LightSheetTransfer/atlas/kim_atlas/KimRef_annotation_volume_4brainpipe.tif'
	}
	PROCESSING_CODE_DIR = '/jukebox/wang/ahoag/brainpipe'
	DJ_SAFEMODE = True
	dj.config['safemode'] = DJ_SAFEMODE
	CELERY_ENABLE_UTC = False
	CELERY_TIMEZONE = os.environ['TZ']


class DevConfig(BaseConfig):
	DEBUG = True
	CLEARING_CALENDAR_ID = os.environ.get("TEST_CALENDAR_URL") # the test calendar for the time being
	SECRET_KEY = os.environ.get('SECRET_KEY')
	DATA_BUCKET_ROOTPATH = '/jukebox/LightSheetData/lightserv_pnilsadmin_testing'
	NG_VIEWER_EXPIRE_SECONDS = 5*60 # seconds time that a neuroglancer viewer and its cloudvolumes are allowed to stay up 
	SPOCK_LSADMIN_USERNAME = 'lightserv-test'
	CELERY_ACKS_LATE = True
	CELERYBEAT_SCHEDULE = {
		# 'processing_job_status_checker': {
		# 'task': 'lightserv.processing.tasks.processing_job_status_checker',
		# 'schedule': timedelta(seconds=5)
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
		'smartspim_stitching_job_status_checker': {
		'task': 'lightserv.processing.tasks.smartspim_stitching_job_status_checker',
		'schedule': timedelta(seconds=30)
		},
		'ng_viewer_cleanser': {
		'task': 'lightserv.neuroglancer.tasks.ng_viewer_checker',
		'schedule': timedelta(minutes=5)
		},
		# 'rawprecomp_job_status_checker': {
		# 'task': 'lightserv.imaging.tasks.check_raw_precomputed_statuses',
		# 'schedule': timedelta(seconds=15)
		# },
		# 'blendedprecomp_job_ready_checker': {
		# 'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_blended_data',
		# 'schedule': timedelta(seconds=5)
		# },
		# 'blendedprecomp_job_status_checker': {
		# 'task': 'lightserv.processing.tasks.blended_precomputed_job_status_checker',
		# 'schedule': timedelta(seconds=5)
		# },
		# 'downsizedprecomp_job_ready_checker': {
		# 'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_downsized_data',
		# 'schedule': timedelta(seconds=15)
		# },
		# 'downsizedprecomp_job_status_checker': {
		# 'task': 'lightserv.processing.tasks.downsized_precomputed_job_status_checker',
		# 'schedule': timedelta(seconds=25)
		# },
		# 'registeredprecomp_job_ready_checker': {
		# 'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_registered_data',
		# 'schedule': timedelta(seconds=15)
		# },
		# 'registeredprecomp_job_status_checker': {
		# 'task': 'lightserv.processing.tasks.registered_precomputed_job_status_checker',
		# 'schedule': timedelta(seconds=25)
		# },
		
	}
	
class ProdConfig(BaseConfig):
	DEBUG = False
	# CLEARING_CALENDAR_ID = '8kvbhcbo0smdg394f79eh45gfc@group.calendar.google.com' # the real clearing calendar
	CLEARING_CALENDAR_ID = os.environ.get("CLEARING_CALENDAR_URL") # the test calendar for the time being
	SECRET_KEY = os.environ.get('SECRET_KEY')
	DATA_BUCKET_ROOTPATH = '/jukebox/LightSheetData/lightserv'
	NG_VIEWER_EXPIRE_SECONDS = 43200 # 6 hours - time that a neuroglancer viewer and its cloudvolumes are allowed to stay up 
	SPOCK_LSADMIN_USERNAME = 'lightserv-test'

	CELERYBEAT_SCHEDULE = {
		'processing_job_status_checker': {
		'task': 'lightserv.processing.tasks.processing_job_status_checker',
		'schedule': timedelta(minutes=10)
		},
		'processing_job_status_checker_noreg': {
		'task': 'lightserv.processing.tasks.processing_job_status_checker_noreg',
		'schedule': timedelta(minutes=30)
		},
		'stitchedprecomp_job_ready_checker': {
		'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_stitched_data',
		'schedule': timedelta(minutes=11)
		},
		'stitchedprecomp_job_status_checker': {
		'task': 'lightserv.processing.tasks.stitched_precomputed_job_status_checker',
		'schedule': timedelta(minutes=12)
		},
		'ng_viewer_cleanser': {
		'task': 'lightserv.neuroglancer.tasks.ng_viewer_checker',
		'schedule': timedelta(hours=1)
		},
		'rawprecomp_job_status_checker': {
		'task': 'lightserv.imaging.tasks.check_raw_precomputed_statuses',
		'schedule': timedelta(minutes=10)
		},
		'blendedprecomp_job_ready_checker': {
		'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_blended_data',
		'schedule': timedelta(minutes=11)
		},
		'blendedprecomp_job_status_checker': {
		'task': 'lightserv.processing.tasks.blended_precomputed_job_status_checker',
		'schedule': timedelta(minutes=12)
		},
		# 'downsizedprecomp_job_ready_checker': {
		# 'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_downsized_data',
		# 'schedule': timedelta(minutes=15)
		# },
		# 'downsizedprecomp_job_status_checker': {
		# 'task': 'lightserv.processing.tasks.downsized_precomputed_job_status_checker',
		# 'schedule': timedelta(minutes=10)
		# },
		'registeredprecomp_job_ready_checker': {
		'task': 'lightserv.processing.tasks.check_for_spock_jobs_ready_for_making_precomputed_registered_data',
		'schedule': timedelta(minutes=11)
		},
		'registeredprecomp_job_status_checker': {
		'task': 'lightserv.processing.tasks.registered_precomputed_job_status_checker',
		'schedule': timedelta(minutes=12)
		},
		'smartspim_stitching_job_status_checker': {
		'task': 'lightserv.processing.tasks.smartspim_stitching_job_status_checker',
		'schedule': timedelta(minutes=10)
		},
		
	}

class TestConfig(BaseConfig):
	TESTING = True
	WTF_CSRF_ENABLED = False # disables the csrf token validation in forms
	DJ_SAFEMODE = False
	dj.config['safemode'] = DJ_SAFEMODE
	DATA_BUCKET_ROOTPATH = '/jukebox/LightSheetData/lightserv_testing'
	SPOCK_LSADMIN_USERNAME = 'lightserv-test'
	CLEARING_CALENDAR_ID = 'skq68osl830f13tfgv6i0kq750@group.calendar.google.com' # the test calendar for the time being
	# CELERY_BROKER_URL='amqp://localhost//',
	# CELERY_RESULT_BACKEND=f'db+mysql+pymysql://ahoag:p@sswd@localhost:3307/ahoag_celery_test'
	MAIL_USERNAME = os.environ.get('EMAIL_USER')
	MAIL_PASSWORD = os.environ.get('EMAIL_PASS')
	CELERY_ALWAYS_EAGER = True # Forces celery tasks to be run synchronously -- will not spawn a separate process
