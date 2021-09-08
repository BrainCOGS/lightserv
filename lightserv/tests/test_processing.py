from flask import url_for, current_app
import tempfile
import webbrowser
from PIL import Image
from lightserv import db_lightsheet, db_admin, db_spockadmin
from bs4 import BeautifulSoup 
from datetime import datetime
import os, glob
import lorem
import pickle

""" Tests for Processing Manager """

def test_access_processing_manager(test_client,
	test_imaged_request_nonadmin):
	""" Test that lightserv-test, a nonadmin can access the processing task manager
	and can see his entry because everyone is by default the processor for their requests """
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	response = test_client.get(url_for('processing.processing_manager')
		, follow_redirects=True)
	assert b'Processing management GUI' in response.data
	assert b'nonadmin_request' in response.data 

	""" Test that an admin can 
	and can see the nonadmin's processing request 
	"""
	imager = current_app.config['IMAGING_ADMINS'][-1] 
	with test_client.session_transaction() as sess:
		sess['user'] = imager
	response = test_client.get(url_for('processing.processing_manager')
		, follow_redirects=True)
	assert b'Processing management GUI' in response.data
	assert b'nonadmin_request' in response.data 

	""" Test that a different user, a nonadmin, cannot see the entry
	of the other nonadmin """
	with test_client.session_transaction() as sess:
		sess['user'] = 'oostland'
	response = test_client.get(url_for('processing.processing_manager')
		, follow_redirects=True)
	assert b'Processing management GUI' in response.data
	assert b'nonadmin_request' not in response.data 
	
""" Tests for processing entry form """

def test_processing_entry_form(test_client,test_imaged_request_nonadmin):
	""" Test that an admin cannot access the processing entry form
	for lightserv-test request. This is to avoid a conflict between user and admin 
	submission for the same processing request"""
	imager = current_app.config['IMAGING_ADMINS'][-1] 
	with test_client.session_transaction() as sess:
		sess['user'] = imager
	response = test_client.get(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		, follow_redirects=True)
	assert b'The processor has already been assigned for this entry and you are not them' in response.data
	assert b'Welcome to the Brain Registration and Histology Core Facility' in response.data 

	""" Test that lightserv-test can access the processing entry form
	for his request"""
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	response = test_client.get(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		, follow_redirects=True)
	assert b'Processing Entry Form' in response.data
	assert b'nonadmin_request' in response.data 

	""" Test that a nonadmin can submit the processing entry form
	for a test sample """
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-ventral_up':0,
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-ventral_up':0,
		'image_resolution_forms-0-atlas_name':'allen_2017',
		'image_resolution_forms-0-image_resolution':'1.3x',
		'submit':True
		}

	username = "lightserv-test"
	request_name = "nonadmin_request"
	sample_name = "sample-001"
	imaging_request_number = 1
	processing_request_number = 1
	response = test_client.post(url_for('processing.processing_entry',
			username=username,request_name=request_name,sample_name=sample_name,
			imaging_request_number=imaging_request_number,
			processing_request_number=processing_request_number),
		data=data,
		follow_redirects=True)
	assert b"core facility requests" in response.data
	assert b"Processing entry form" not in response.data

	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
			f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' & \
			f'processing_request_number="{processing_request_number}"'
	processing_progress = processing_request_contents.fetch1('processing_progress')
	assert processing_progress == 'running'

	""" Test that the processing entry form shows a flash message 
	that it is read only if the processing request has already been submitted
	"""
	response = test_client.get(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		, follow_redirects=True)

	assert b'Processing Entry Form' in response.data
	assert b'nonadmin_request' in response.data 
	warning_message = ("Processing is running for this sample. "
			"This page is read only and hitting submit will do nothing")
	assert warning_message.encode('utf-8') in response.data 

	""" Test that the processing entry form redirects 
	to the processing manager if a post request is received and the entry 
	form has already been submitted in the past. 
	"""
	response = test_client.post(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1),
		data = {
			'image_resolution_forms-0-image_resolution':'1.3x',
			'image_resolution_forms-0-channel_forms-0-channel_name':'488',
			'image_resolution_forms-0-atlas_name':'allen_2017',
			'image_resolution_forms-0-image_resolution':'1.3x',
			'submit':True
		}, follow_redirects=True)

	assert b'Processing management GUI' in response.data
	warning_message = ("Processing is running for this sample.  " 
                       "It cannot be re-processed. To open a new processing request, " 
                       "see your request page") 
	assert warning_message.encode('utf-8') in response.data

def test_multichannel_processing_entry_form_submits(test_client,test_imaged_multichannel_request_ahoag):
	""" Test that the multi-channel imaging request with different 
	tiling schemes for channels 488 and 555 get split into two parameter 
	dictionaries and therefore two spock jobs """
	# print(db_lightsheet.request.Sample())
	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-ventral_up':0,
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-ventral_up':0,
		'image_resolution_forms-0-atlas_name':'allen_2017',
		'image_resolution_forms-0-channel_forms-1-channel_name':'555',
		'submit':True
		}
	username = "ahoag"
	request_name = "admin_multichannel_request"
	sample_name = "sample-001"
	imaging_request_number = 1
	processing_request_number = 1
	response = test_client.post(url_for('processing.processing_entry',
			username=username,request_name=request_name,sample_name=sample_name,
			imaging_request_number=imaging_request_number,
			processing_request_number=processing_request_number),
		data=data,
		follow_redirects=True)
	assert b"core facility requests" in response.data
	assert b"Processing entry form" not in response.data

	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
			f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' & \
			f'processing_request_number="{processing_request_number}"'
	processing_progress = processing_request_contents.fetch1('processing_progress')
	assert processing_progress == 'running'
	# print(db_admin.SpockJobManager())
	# assert b'Your data processing has begun. You will receive an email when the first steps are completed.' in response.data	

	# imaging_progress = (db_lightsheet.Request.ImagingRequest() & 'request_name="admin_request"' & \
	# 	'username="ahoag"' & 'sample_name="sample-001"' & 'imaging_request_number=1').fetch1('imaging_progress')
	# assert imaging_progress == 'complete'

def test_submit_processing_entry_generic_imaging_nonadmin(test_client,test_imaged_request_generic_imaging_nonadmin):
	""" Test that the processing entry form submits for a generic 
	imaging request (i.e. one with no registration) """
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'

	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-ventral_up':0,
		'image_resolution_forms-0-channel_forms-0-channel_name':'555',
		'image_resolution_forms-0-channel_forms-0-ventral_up':0,
		'image_resolution_forms-0-atlas_name':'allen_2017',
		'image_resolution_forms-0-image_resolution':'1.3x',
		'submit':True
		}
	username='lightserv-test'
	request_name='nonadmin_request'
	sample_name='sample-001'
	imaging_request_number=1
	processing_request_number=1
	response = test_client.post(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		,data=data,
		follow_redirects=True)
	
	assert b"core facility requests" in response.data
	assert b"Processing entry form" not in response.data

	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
			f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' & \
			f'processing_request_number="{processing_request_number}"'
	processing_progress = processing_request_contents.fetch1('processing_progress')
	assert processing_progress == 'running'

def test_dorsal_up_and_ventral_up_processing(test_client,
	test_imaged_request_dorsal_up_and_ventral_up_nonadmin):
	""" Test that a request which has both dorsal up and ventral up imaging 
	has a dorsal up section and a separate ventral up section in the processing entry form
	"""
	response = test_client.get(url_for('processing.processing_entry',
		username='lightserv-test',request_name='nonadmin_request',sample_name='sample-001',
		imaging_request_number=1,processing_request_number=1)
		, follow_redirects=True)

	assert b'Processing Entry Form' in response.data
	assert b'nonadmin_request' in response.data 
	assert b'(1/2) Image resolution: 1.3x' in response.data 
	assert b'(2/2) Image resolution: 1.3x_ventral_up' in response.data 
	assert b'Channel: 488_ventral_up' in response.data 


	""" Test that submitting the processing entry form for a request 
	which has both dorsal up and ventral up imaging 
	launches a separate job for the single dorsal up 488 channel
	and a separate job for the the ventral up 488 channel  
	"""

	data = {
		'image_resolution_forms-0-image_resolution':'1.3x',
		'image_resolution_forms-0-ventral_up':0,
		'image_resolution_forms-0-channel_forms-0-channel_name':'488',
		'image_resolution_forms-0-channel_forms-0-ventral_up':0,
		'image_resolution_forms-0-atlas_name':'allen_2017',
		'image_resolution_forms-1-image_resolution':'1.3x_ventral_up',
		'image_resolution_forms-1-ventral_up':1,
		'image_resolution_forms-1-channel_forms-0-channel_name':'488',
		'image_resolution_forms-1-channel_forms-0-ventral_up':1,
		'image_resolution_forms-1-atlas_name':'allen_2017',
		'submit':True
		}

	username = "lightserv-test"
	request_name = "nonadmin_request"
	sample_name = "sample-001"
	imaging_request_number = 1
	processing_request_number = 1
	response = test_client.post(url_for('processing.processing_entry',
			username=username,request_name=request_name,sample_name=sample_name,
			imaging_request_number=imaging_request_number,
			processing_request_number=processing_request_number),
		data=data,
		follow_redirects=True)
	assert b"core facility requests" in response.data
	assert b"Processing entry form" not in response.data

	processing_request_contents = db_lightsheet.Request.ProcessingRequest() & \
			f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"' & \
			f'imaging_request_number="{imaging_request_number}"' & \
			f'processing_request_number="{processing_request_number}"'
	processing_progress = processing_request_contents.fetch1('processing_progress')
	assert processing_progress == 'running'

""" Tests for smartspim stitching """
def test_smartspim_stitching_works(test_client,
	smartspim_stitched_request):
	""" Test that stitching task runs and db is updated """
	with test_client.session_transaction() as sess:
		sess['user'] = 'lightserv-test'
	stitching_contents = db_lightsheet.Request.SmartspimStitchedChannel()
	stitching_results = stitching_contents.fetch1()
	assert len(stitching_contents) == 1
	assert stitching_results['request_name'] == 'nonadmin_3p6x_smartspim_request'
	assert stitching_results['smartspim_stitching_spock_job_progress'] == 'COMPLETED'

""" Tests for pystripe manager """

def test_access_pystripe_manager(test_client,
	smartspim_stitched_request):
	""" Test that sg3271, an imaging admin can access the pystripe task manager
	and see the stitched channel that needs to be corrected with pystripe """

	with test_client.session_transaction() as sess:
		sess['user'] = 'sg3271'
	
	response = test_client.get(url_for('processing.pystripe_manager')
		, follow_redirects=True)
	assert b'Pystripe management GUI' in response.data
	assert b'nonadmin_3p6x_smartspim_request' in response.data

""" Tests for pystripe_entry """

def test_get_pystripe_entry(test_client,
	smartspim_stitched_request):
	""" Test that sg3271, an imaging admin can access the pystripe_entry
	route and see the stitched channel that needs to be corrected with pystripe """
	with test_client.session_transaction() as sess:
		sess['user'] = 'sg3271'
	username='lightserv-test'
	request_name = 'nonadmin_3p6x_smartspim_request'
	sample_name = 'sample-001'
	imaging_request_number=1
	kwargs = dict(username=username,
		request_name=request_name,
		sample_name=sample_name,
		imaging_request_number=imaging_request_number)
	response = test_client.get(url_for('processing.pystripe_entry',
		**kwargs)
		, follow_redirects=True)
	assert b'Pystripe Setup Form' in response.data
	assert b'488' in response.data
	assert request_name.encode('utf-8') in response.data
	assert sample_name.encode('utf-8') in response.data
	assert b'Start pystripe' in response.data
	
def test_post_pystripe_entry(test_client,
	smartspim_stitched_request):
	""" Test that sg3271, an imaging admin can post the pystripe task manager
	and see the stitched channel that needs to be corrected with pystripe """
	with test_client.session_transaction() as sess:
		sess['user'] = 'sg3271'
	username='lightserv-test'
	request_name = 'nonadmin_3p6x_smartspim_request'
	sample_name = 'sample-001'
	imaging_request_number=1
	kwargs = dict(username=username,
		request_name=request_name,
		sample_name=sample_name,
		imaging_request_number=imaging_request_number)

	data = {
	'channel_forms-0-username':username,
	'channel_forms-0-request_name':request_name,
	'channel_forms-0-sample_name':sample_name,
	'channel_forms-0-imaging_request_number':imaging_request_number,
	'channel_forms-0-image_resolution':'3.6x',
	'channel_forms-0-channel_name':'488',
	'channel_forms-0-ventral_up':0,
	'channel_forms-0-pystripe_started':False,
	'channel_forms-0-flat_name':'flat.tiff',
	'channel_forms-0-start_pystripe':True,
	}
	response = test_client.post(url_for('processing.pystripe_entry',
		**kwargs),
		data=data
		, follow_redirects=True)
	assert b'Pystripe Setup Form' not in response.data
	assert b'Pystripe management GUI' in response.data
	# Make sure a db entry was made in the SmartspimPystripeChannel() table
	pystripe_contents = db_lightsheet.Request.SmartspimPystripeChannel()
	assert len(pystripe_contents) == 1
	pystripe_result = pystripe_contents.fetch1()
	assert pystripe_result['request_name'] == request_name
	assert pystripe_result['pystripe_performed'] == False


""" Tests for processing_table """

def test_ahoag_access_processing_table(test_client,processing_request_ahoag):
	""" Test that ahoag can access their processing table route
	after request has been processed"""
	with test_client.session_transaction() as sess:
		sess['user'] = "ahoag"
	username = "ahoag"
	request_name = "admin_request"
	sample_name = "sample-001"
	imaging_request_number = 1
	processing_request_number = 1
	response = test_client.get(url_for('processing.processing_table',
		username=username,request_name=request_name,sample_name=sample_name,
		imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number),
		follow_redirects=True)
	
	assert b"Processing Log" in response.data
	assert b"Processed channels:" in response.data

""" Tests for processing utils """

def test_determine_status_code():
	""" Test that the new processing request route validates when
	the form is submitted with bad data

	Uses test_single_sample_request_nonadmin to make a single request with a single 
	sample for setup

	"""
	from lightserv.processing.utils import determine_status_code

	# if all are same then return the one code that is duplicated
	status_codes1 = ['COMPLETED','COMPLETED']
	status_code1 = determine_status_code(status_codes1)
	assert status_code1 == 'COMPLETED'
	# if none have failed but all are not the same then status should be RUNNING
	status_codes2 = ['PENDING','PENDING','RUNNING','COMPLETED']
	status_code2 = determine_status_code(status_codes2)
	assert status_code2 == 'RUNNING'
	# if any are problematic, return failed
	status_codes3 = ['PENDING','PENDING','RUNNING','CANCELLED']
	status_code3 = determine_status_code(status_codes3)
	assert status_code3 == 'FAILED'
	# if only 1 status code then just return that value
	status_codes4 = ['PENDING']
	status_code4 = determine_status_code(status_codes4)
	assert status_code4 == 'PENDING'
	# if CANCELLED by {UID} is the status code then just return CANCELLED
	status_codes5 = ['CANCELLED by 1234']
	status_code5 = determine_status_code(status_codes5)
	assert status_code5 == 'CANCELLED'

""" Test for processing tasks """

def test_lightsheet_pipeline_starts(test_client,
	test_imaged_request_viz_nonadmin,
	test_delete_spockadmin_db_contents):
	""" Test that the light sheet pipeline starts,
	given the correct input. Uses a test script on spock which just returns
	job ids. Runs a celery task synchronously """
	from lightserv.processing import tasks
	import time
	username='lightserv-test'
	request_name='viz_processed'
	sample_name='viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	kwargs = dict(username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number)
	all_channel_contents = db_lightsheet.Request.ImagingChannel() & f'username="{username}"' \
		& f'request_name="{request_name}"'  & f'sample_name="{sample_name}"' & \
		f'imaging_request_number="{imaging_request_number}"'
	# print(all_channel_contents)
	tasks.run_lightsheet_pipeline.run(**kwargs)
	""" make sure entries were made in ProcessingPipelineSpockJob()
	and ProcessingChannel() """
	table_contents = db_spockadmin.ProcessingPipelineSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0
	status_step0 = table_contents.fetch1('status_step0')
	assert status_step0 == 'SUBMITTED'
	processing_channel_contents = db_lightsheet.Request.ProcessingChannel()
	assert len(processing_channel_contents) == 2
	""" Make sure ProcessingResolutionRequest() entry was updated
	to have jobid and progress """
	processing_resolution_contents = db_lightsheet.Request.ProcessingResolutionRequest()
	spock_job_progress = processing_resolution_contents.fetch1('lightsheet_pipeline_spock_job_progress')
	assert spock_job_progress == 'SUBMITTED'
	spock_jobid = int(processing_resolution_contents.fetch1('lightsheet_pipeline_spock_jobid'))
	assert spock_jobid > 0

def test_lightsheet_pipeline_starts_dorsal_up_ventral_up(test_client,
	processing_form_submitted_dorsal_up_ventral_up,
	test_delete_spockadmin_db_contents):
	""" Test that the light sheet pipeline starts two jobs
	for a request that has dorsal up and ventral up imaging.

	Make sure that the finalorientation gets a "-2","1","0"
	due to the flipping of the brain. 
	Uses a test script on spock which just returns
	job ids. Runs a celery task synchronously """
	from lightserv.processing import tasks
	import time
	username='lightserv-test'
	request_name='nonadmin_request'
	sample_name='sample-001'
	imaging_request_number=1
	processing_request_number=1
	kwargs = dict(username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number)
	tasks.run_lightsheet_pipeline.run(**kwargs)
	table_contents = db_spockadmin.ProcessingPipelineSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0
	pickle_file = os.path.join('/jukebox/LightSheetData/lightserv_testing',
		username,request_name,sample_name,f'imaging_request_{imaging_request_number}',
	'output',f'processing_request_{processing_request_number}',
	'resolution_1.3x_ventral_up/param_dict.p')
	with open(pickle_file,'rb') as pkl:
		data = pickle.load(pkl)
	print("HERE!")
	print("")
	print("")
	print(data)
	assert data['finalorientation'] == ("-2","1","-0")

def test_stitched_precomputed_pipeline_starts(test_client,
	test_delete_spockadmin_db_contents):
	""" Test that the stitched precomputed pipeline task runs through,
	given the correct input. Uses a test script on spock which just returns
	job ids. Runs a celery task """
	from lightserv.processing import tasks
	import time
	username='lightserv-test'
	request_name='tracing_test'
	sample_name='tracing_test-001'
	imaging_request_number=1
	processing_request_number=1
	image_resolution='4x'
	channel_name='647'
	ventral_up=0
	channel_index=0
	number_of_z_planes=682
	lightsheet='left'
	left_lightsheet_used=True
	right_lightsheet_used=False
	z_step=2
	rawdata_subfolder='test647'
	processing_pipeline_jobid_step0=12345678 # just some dummy number
	stitched_viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
							 f"{request_name}/{sample_name}/"
							 f"imaging_request_{imaging_request_number}/viz/"
							 f"processing_request_{processing_request_number}/"
							 f"stitched_raw")
	channel_viz_dir = os.path.join(stitched_viz_dir,f'channel_{channel_name}')
	this_viz_dir = os.path.join(channel_viz_dir,'left_lightsheet')

	precomputed_kwargs = dict(
				username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number,
				image_resolution=image_resolution,channel_name=channel_name,
				channel_index=channel_index,
				ventral_up=ventral_up,
				rawdata_subfolder=rawdata_subfolder,
				left_lightsheet_used=left_lightsheet_used,
				right_lightsheet_used=right_lightsheet_used,
				processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
				z_step=z_step,lightsheet='left',viz_dir=this_viz_dir)
	
	tasks.make_precomputed_stitched_data.run(**precomputed_kwargs) 
	table_contents = db_spockadmin.StitchedPrecomputedSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0

def test_blended_precomputed_pipeline_starts(test_client,
	test_delete_spockadmin_db_contents):
	""" Test that the blended precomputed pipeline task runs through,
	given the correct input. Uses a test script on spock which just returns
	job ids. Runs a celery task """
	from lightserv.processing import tasks
	import time
	username='lightserv-test'
	request_name='viz_processed'
	sample_name='viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	image_resolution='1.3x'
	channel_name='488'
	ventral_up=0
	channel_index=0
	left_lightsheet_used=True
	right_lightsheet_used=False
	z_step=5
	rawdata_subfolder='test488'
	processing_pipeline_jobid_step0=12345679 # just some dummy number
	data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
	channel_index_padded = '0'*(2-len(str(channel_index)))+str(channel_index) # "01", e.g.
	blended_data_path = os.path.join(data_bucket_rootpath,username,
					 request_name,sample_name,
					 f"imaging_request_{imaging_request_number}",
					 "output",
					 f"processing_request_{processing_request_number}",
					 f"resolution_{image_resolution}",
					 "full_sizedatafld",
					 f"{rawdata_subfolder}_ch{channel_index_padded}")
	blended_viz_dir = (f"{current_app.config['DATA_BUCKET_ROOTPATH']}/{username}/"
							 f"{request_name}/{sample_name}/"
							 f"imaging_request_{imaging_request_number}/viz/"
							 f"processing_request_{processing_request_number}/"
							 f"blended")
	channel_viz_dir = os.path.join(blended_viz_dir,f'channel_{channel_name}')
	precomputed_kwargs = dict(
				username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number,
				image_resolution=image_resolution,channel_name=channel_name,
				channel_index=channel_index,
				ventral_up=ventral_up,
				processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
				z_step=z_step,blended_data_path=blended_data_path)

	precomputed_kwargs['viz_dir'] = channel_viz_dir
	tasks.make_precomputed_blended_data.run(**precomputed_kwargs)
	table_contents = db_spockadmin.BlendedPrecomputedSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0

def test_downsized_precomputed_pipeline_starts(test_client,
	test_delete_spockadmin_db_contents):
	""" Test that the downsized precomputed pipeline task runs through,
	given the correct input. Uses a test script on spock which just returns
	job ids. Runs a celery task """
	from lightserv.processing import tasks
	import time
	username='lightserv-test'
	request_name='viz_processed'
	sample_name='viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	image_resolution='1.3x'
	channel_name='488'
	channel_index=0
	ventral_up=0
	left_lightsheet_used=True
	right_lightsheet_used=False
	z_step=5
	rawdata_subfolder='test488'
	processing_pipeline_jobid_step0=12345680 # just some dummy number
	data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
	atlas_name='princeton_mouse_atlas'
	downsized_data_path = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "output",
							 f"processing_request_{processing_request_number}",
							 f"resolution_{image_resolution}")
	precomputed_kwargs = dict(
				username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number,
				processing_request_number=processing_request_number,
				image_resolution=image_resolution,channel_name=channel_name,
				channel_index=channel_index,rawdata_subfolder=rawdata_subfolder,
				ventral_up=ventral_up,
				processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
				downsized_data_path=downsized_data_path,atlas_name=atlas_name)
	downsized_viz_dir = os.path.join(data_bucket_rootpath,username,
					 request_name,sample_name,
					 f"imaging_request_{imaging_request_number}",
					 "viz",
					 f"processing_request_{processing_request_number}",
					 "downsized")
	channel_viz_dir = os.path.join(downsized_viz_dir,
				f'channel_{channel_name}')
	precomputed_kwargs['viz_dir'] = channel_viz_dir
	tasks.make_precomputed_downsized_data.run(**precomputed_kwargs)
	table_contents = db_spockadmin.DownsizedPrecomputedSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0

def test_registered_precomputed_pipeline_starts(test_client,
	test_delete_spockadmin_db_contents):
	""" Test that the downsized precomputed pipeline task runs through,
	given the correct input. Uses a test script on spock which just returns
	job ids. Runs a celery task """
	from lightserv.processing import tasks
	import time
	username='lightserv-test'
	request_name='viz_processed'
	sample_name='viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	image_resolution='1.3x'
	channel_name='488'
	channel_index=0
	ventral_up=0
	lightsheet_channel_str='regch'	
	z_step=5
	rawdata_subfolder='test488'
	processing_pipeline_jobid_step0=12345684 # just some dummy number
	data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
	atlas_name='princeton_mouse_atlas'
	
	registered_data_path = os.path.join(data_bucket_rootpath,username,
							 request_name,sample_name,
							 f"imaging_request_{imaging_request_number}",
							 "output",
							 f"processing_request_{processing_request_number}",
							 f"resolution_{image_resolution}",
							 "elastix")

	""" number of z planes could be altered in the case of tiling due to terastitcher 
	so we will calculate it on the fly when doing the precomputed steps """
	precomputed_kwargs = dict(
		username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number,
		image_resolution=image_resolution,channel_name=channel_name,
		channel_index=channel_index,
		lightsheet_channel_str=lightsheet_channel_str,
		rawdata_subfolder=rawdata_subfolder,
		atlas_name=atlas_name,
		ventral_up=ventral_up,
		processing_pipeline_jobid_step0=processing_pipeline_jobid_step0,
		registered_data_path=registered_data_path)

	registered_viz_dir = os.path.join(data_bucket_rootpath,username,
					 request_name,sample_name,
					 f"imaging_request_{imaging_request_number}",
					 "viz",
					 f"processing_request_{processing_request_number}",
					 "registered")
	channel_viz_dir = os.path.join(registered_viz_dir,
		f'channel_{channel_name}_{lightsheet_channel_str}')
	precomputed_kwargs['viz_dir'] = channel_viz_dir
	layer_name = f'channel{channel_name}_registered'
	precomputed_kwargs['layer_name'] = layer_name

	tasks.make_precomputed_registered_data.run(**precomputed_kwargs)
	table_contents = db_spockadmin.RegisteredPrecomputedSpockJob() 
	print(table_contents)
	assert len(table_contents) > 0


def test_job_status_checker_sends_email(test_client,
	test_imaged_request_viz_nonadmin,
	test_delete_spockadmin_db_contents):
	"""
	Test that the processing job status checker works 
	and that it sends an email when all processing requests 
	in a given request are complete """

	""" 
	Makes an entry into the spockadmin db for a previous run
	where I know the result was complete """
	print('----------Setup lightsheet_pipeline_complete fixture----------')

	from lightserv.processing import tasks
	import datajoint as dj

	username='lightserv-test'
	request_name='viz_processed'
	sample_name='viz_processed-001'
	imaging_request_number=1
	processing_request_number=1
	kwargs = dict(username=username,request_name=request_name,
		sample_name=sample_name,imaging_request_number=imaging_request_number,
		processing_request_number=processing_request_number)
	all_channel_contents = db_lightsheet.Request.ImagingChannel() & f'username="{username}"' \
		& f'request_name="{request_name}"'  & f'sample_name="{sample_name}"' & \
		f'imaging_request_number="{imaging_request_number}"'
	# tasks.run_lightsheet_pipeline.run(**kwargs)
	job_insert_dict = {
	'jobid_step0':20915092,
	'jobid_step1':20915093,
	'jobid_step2':20915094,
	'jobid_step3':20915095,
	'status_step0':'SUBMITTED',
	'status_step1':'SUBMITTED',
	'status_step2':'SUBMITTED',
	'status_step3': 'SUBMITTED',
	'stitching_method':'blending',
	'username':'lightserv-test'
	}
	db_spockadmin.ProcessingPipelineSpockJob().insert1(job_insert_dict) 
	""" Update ProcessingResolutionRequest() to point to this jobid """
	processing_resolution_content = db_lightsheet.Request.ProcessingResolutionRequest() & {
		'username':username,
		'request_name':request_name
	}
	assert len(processing_resolution_content) == 1
	processing_resolution_update_dict = processing_resolution_content.fetch1()

	processing_resolution_update_dict['lightsheet_pipeline_spock_job_progress'] = 'SUBMITTED'
	processing_resolution_update_dict['lightsheet_pipeline_spock_jobid'] = 20915095   
	db_lightsheet.Request.ProcessingResolutionRequest().update1(processing_resolution_update_dict)
	""" Now do job status checker and make sure it gets updated to COMPLETED """
	tasks.processing_job_status_checker.run()
	spock_table_contents = db_spockadmin.ProcessingPipelineSpockJob() & \
		{'username':'lightserv-test'}
	most_recent_contents = dj.U('jobid_step0','username',).aggr(
		spock_table_contents,timestamp='max(timestamp)')*spock_table_contents
	print(most_recent_contents)
	status_step3 = most_recent_contents.fetch1('status_step3')
	assert status_step3 == 'COMPLETED'
	""" Make sure processing email was sent """
	request_contents = db_lightsheet.Request() & \
		{'username':username,'request_name':request_name}
	sent_email = request_contents.fetch1('sent_processing_email')
	assert sent_email == 1
