from flask import session,request,url_for,redirect, flash, current_app
from functools import wraps
import os,time
from lightserv import db_lightsheet, db_admin
import datajoint as dj

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/main_utils.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

def table_sorter(dic,sort_key):
    if type(dic[sort_key]) == str:
        return dic[sort_key].lower()
    else:
	    return (dic[sort_key] is None, dic[sort_key])

def log_http_requests(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		try:
			current_user = session['user']
		except:
			current_user = 'logged out user'
		logstr = '{0} {1} request to route: "{2}()" in {3}'.\
			format(current_user,request.method,f.__name__,f.__module__)
		user_agent = request.user_agent
		browser_name = user_agent.browser # e.g. chrome
		browser_version = user_agent.version # e.g. '78.0.3904.108'
		platform = user_agent.platform # e.g. linux
		
		insert_dict = {'browser_name':browser_name,'browser_version':browser_version,
					   'event':logstr,'platform':platform}

		db_admin.UserActionLog().insert1(insert_dict)
		return f(*args, **kwargs)
	return decorated_function

def logged_in(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'user' in session:
			return f(*args, **kwargs)
		else:
			next_url = request.url
			login_url = '%s?next=%s' % (url_for('main.login'), next_url)
			return redirect(login_url)
	return decorated_function

def request_exists(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		
		username = kwargs['username']
		request_name = kwargs['request_name']
		request_contents = db_lightsheet.Request() & \
		f'request_name="{request_name}"' & f'username="{username}"'
		if len(request_contents) == 0:
			flash("That request does not exist","danger")
			return redirect(url_for('requests.all_requests'))
		else:
			return f(*args, **kwargs)
	return decorated_function

def logged_in_as_clearer(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'user' in session: # user is logged in 
			current_user = session['user']
			request_name = kwargs['request_name']
			username = kwargs['username']
			clearing_protocol = kwargs['clearing_protocol']
			antibody1 = kwargs['antibody1']
			antibody2 = kwargs['antibody2']
			clearing_batch_number = kwargs['clearing_batch_number']

			clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & \
				f'request_name="{request_name}"' & f'username="{username}"' & \
				f'clearing_protocol="{clearing_protocol}"' & \
				f'antibody1="{antibody1}"' & f'antibody2="{antibody2}"' & \
				f'clearing_batch_number={clearing_batch_number}'
			if len(clearing_batch_contents) == 0:
				flash("No clearing batch exists with those parameters. Please try again.","danger")
				logger.debug("No clearing batch exists with those parameters. Redirecting to all requests page")
				return redirect(url_for('requests.all_requests'))
			clearer = clearing_batch_contents.fetch1('clearer')
			''' check to see if user assigned themself as clearer '''
			if clearer == None:
				logger.info("Clearing entry form accessed with clearer not yet assigned. ")
				''' now check to see if user is a designated clearer ''' 
				if current_user in current_app.config['CLEARING_ADMINS']: # 
					# logger.info(f"Current user: {current_user} is a designated clearer and is now assigned as the clearer")
					dj.Table._update(clearing_batch_contents,'clearer',current_user)
					logger.info(f"Current user: {current_user} is a designated clearer and is now assigned as the clearer")
					return f(*args, **kwargs)
				else: # user is not a designated clearer and did not self assign
					logger.info(f"""Current user: {current_user} is not a designated clearer and did not specify themselves
					 as the clearer when submitting request. Denying them access""")
					flash('''You do not have permission to access the clearing form for this experiment. 
						Please email us at lightservhelper@gmail.com if you think there has been a mistake.''','warning')
					return redirect(url_for('main.welcome'))
			else: # clearer is assigned - only allow access to clearing entry to them
				if current_user == clearer:
					logger.info(f"{current_user} is the rightful clearer and accessed the clearing entry form")
					return f(*args, **kwargs)
				else:
					logger.info(f"Current user: {current_user} is not the clearer, who has already been assigned."
					             "Denying them access")
					flash(f'''The clearer has already been assigned for this entry and you, {current_user}, are not them.  
						Please email us at lightservhelper@gmail.com if you think there has been a mistake.''','warning')
					return redirect(url_for('main.welcome'))
		else:
			next_url = request.url
			login_url = '%s?next=%s' % (url_for('main.login'), next_url)
			return redirect(login_url)
	return decorated_function

def logged_in_as_processor(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'user' in session: # user is logged in 
			current_user = session['user']
			request_name = kwargs['request_name']
			sample_name = kwargs['sample_name']
			username = kwargs['username']
			imaging_request_number = kwargs['imaging_request_number']
			processing_request_number = kwargs['processing_request_number']
			
			processing_request_contents = db_lightsheet.Request.ProcessingRequest() & f'request_name="{request_name}"' & \
			 	f'username="{username}"' & f'sample_name="{sample_name}"' & \
			 	f'imaging_request_number="{imaging_request_number}"' & \
			 	f'processing_request_number="{processing_request_number}"'
			processor = processing_request_contents.fetch1('processor')
			# ''' check to see if user assigned themself as processor '''
			if current_user != processor:
				flash(("The processor has already been assigned for this entry "
							  "and you are not them. Please email us at lightservhelper@gmail.com "  
						      "if you think there has been a mistake."),'warning')
				return redirect(url_for('processing.processing_manager'))
			else:
				next_url = request.url
				login_url = '%s?next=%s' % (url_for('main.login'), next_url)
				return redirect(login_url)
		else:
			next_url = request.url
			login_url = '%s?next=%s' % (url_for('main.login'), next_url)
			return redirect(login_url)
	return decorated_function

def logged_in_as_clearing_manager(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'user' in session: # user is logged in 
			current_user = session['user']
			if current_user in current_app.config['CLEARING_ADMINS']: # the clearing managers and admins
				logger.info(f"Current user: {current_user} is a clearing manager. Allowing them access.")
				return f(*args, **kwargs)
			else:
				logger.info(f"""Current user: {current_user} is not a clearing manager. Denying them access""")
				flash('''You do not have access to this page.  
					Please email us at lightservhelper@gmail.com if you think there has been a mistake.''',
					'warning')
				return redirect(url_for('main.welcome'))
		else:
			next_url = request.url
			login_url = '%s?next=%s' % (url_for('main.login'), next_url)
			return redirect(login_url)
	return decorated_function

def logged_in_as_imager(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):

		if 'user' in session: # user is logged in 
			current_user = session['user']
			logger.debug(f"User is logged in as: {current_user}")
			username = kwargs['username']
			request_name = kwargs['request_name']
			sample_name = kwargs['sample_name']
			imaging_request_number = kwargs['imaging_request_number']
			imaging_request_contents = db_lightsheet.Request.ImagingRequest() & f'request_name="{request_name}"' & \
			 	f'username="{username}"' & f'sample_name="{sample_name}"' & \
			 	f'imaging_request_number="{imaging_request_number}"'
			if len(imaging_request_contents) == 0:
				flash("No imaging request exists with those parameters. Please try again.","danger")
				logger.debug("No imaging request exists with those parameters. Redirecting to all requests page")
				return redirect(url_for('requests.all_requests'))
			imager = imaging_request_contents.fetch1('imager')
			logger.debug(f"Imager is: {imager}")
			''' check to see if user assigned themself as imager '''
			if imager == None: # not yet assigned
				logger.info("Imaging entry form accessed with imager not yet assigned. ")
				''' now check to see if user is a designated imager ''' 
				if current_user in  current_app.config['IMAGING_ADMINS']: # 
					dj.Table._update(imaging_request_contents,'imager',current_user)
					logger.info(f"{current_user} is a designated imager and is now assigned as the imager")
					return f(*args, **kwargs)
				else: # user is not a designated imager and did not self assign
					logger.info(f"""Current user: {current_user} is not a designated imager and did not specify themselves
					 as the imager when submitting request. Denying them access""")
					flash('''You do not have permission to access the imaging form for this experiment. 
						Please email us at lightservhelper@gmail.com if you think there has been a mistake.''','warning')
					return redirect(url_for('main.welcome'))
			else: # imager is assigned 
				if imager in current_app.config['IMAGING_ADMINS']: # one of the admins started the form
					logger.debug("Imager is an admin")
					if current_user in current_app.config['IMAGING_ADMINS']: # one of the admins is accessing the form
						if current_user != imager:
							logger.debug(f"""Current user: {current_user} accessed the form of which {imager} is the imager""")
							flash("While you have access to this page, "
								  "you are not the primary imager "
								  "so please proceed with caution.",'warning')
							return f(*args, **kwargs)
						else:
							logger.info(f"""Current user: {current_user} is the rightful imager and so is allowed access""")
							return f(*args, **kwargs)
					else:
						flash(("The imager has already been assigned for this entry "
							  "and you are not them. Please email us at lightservhelper@gmail.com "  
						      "if you think there has been a mistake."),'warning')
						return redirect(url_for("requests.request_overview",
							username=username,request_name=request_name))
				elif imager == current_user:
					logger.info(f"Current user: {current_user} is the rightful imager and so is allowed access")
					return f(*args, **kwargs)
				else:
					logger.info(f"""Current user: {current_user} is not the imager. Denying them access""")
					flash(("The imager has already been assigned for this entry "
							  "and you are not them. Please email us at lightservhelper@gmail.com "  
						      "if you think there has been a mistake."),'warning')
					return redirect(url_for('main.welcome'))
		else:
			next_url = request.url
			login_url = '%s?next=%s' % (url_for('main.login'), next_url)
			return redirect(login_url)
	return decorated_function

def image_manager(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'user' in session: # user is logged in 
			current_user = session['user']
			if current_user in current_app.config['IMAGING_ADMINS']: # admin rights
				logger.info(f"Current user: {current_user} is an imaging admin. Allowing them access")
				return f(*args, **kwargs)
			else:
				logger.info(f"Current user: {current_user} is not an imaging admin. Denying them access.")
				flash("You do not have access to this page. \
					Please email us at lightservhelper@gmail.com if you think there has been a mistake.")
				return redirect(url_for('main.welcome'))
		else:
			next_url = request.url
			login_url = '%s?next=%s' % (url_for('main.login'), next_url)
			return redirect(login_url)
	return decorated_function

def logged_in_as_processor(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'user' in session: # user is logged in 
			current_user = session['user']
			username = kwargs['username']
			request_name = kwargs['request_name']
			sample_name = kwargs['sample_name']
			imaging_request_number = kwargs['imaging_request_number']
			processing_request_number = kwargs['processing_request_number']
			processing_request_contents = db_lightsheet.Request.ProcessingRequest() & f'request_name="{request_name}"' & \
			 	f'username="{username}"' & f'sample_name="{sample_name}"' & \
			 	f'imaging_request_number="{imaging_request_number}"' & \
			 	f'processing_request_number="{processing_request_number}"'
			if len(processing_request_contents) == 0:
				flash("No processing request exists with those parameters. Please try again.","danger")
				logger.debug("No processing request exists with those parameters. Redirecting to all requests page")
				return redirect(url_for('requests.all_requests'))
			processor = processing_request_contents.fetch1('processor')
			''' check to see if user assigned themself as processor '''
			if processor == None: # not yet assigned
				logger.info("processing entry form accessed with processor not yet assigned. ")
				''' now check to see if user is a designated processor ''' 
				if current_user in  current_app.config['PROCESSING_ADMINS']: # 
					dj.Table._update(processing_request_contents,'processor',current_user)
					logger.info(f"{current_user} is a designated processor and is now assigned as the processor")
					return f(*args, **kwargs)
				elif current_user == username:
					logger.info(f"Current user: {current_user} = username for this request, so assigning them as the processor")
					return f(*args, **kwargs)
				else: # user is not a designated processor and did not self assign
					logger.info(f"""Current user: {current_user} is not a designated processor and did not specify themselves
					 as the processor when submitting request. Denying them access""")
					flash('''You do not have permission to access the processing form for this experiment. 
						Please email us at lightservhelper@gmail.com if you think there has been a mistake.''','warning')
					return redirect(url_for('main.welcome'))
			else: # processor is assigned 
				if processor in current_app.config['PROCESSING_ADMINS']: # one of the admins started the form
					if current_user in  current_app.config['PROCESSING_ADMINS']: # one of the admins is accessing the form
						if current_user != processor:
							logger.info(f"""Current user: {current_user} accessed the form of which {processor} is the processor""")
							flash("While you have access to this page, "
								  "you are not the primary processor "
								  "so please proceed with caution.",'warning')
							return f(*args, **kwargs)
						else:
							logger.info(f"""Current user: {current_user} is the rightful processor and so is allowed access""")
							return f(*args, **kwargs)
					else:
						flash(("The processor has already been assigned for this entry "
							  "and you are not them. Please email us at lightservhelper@gmail.com "  
						      "if you think there has been a mistake."),'warning')
				elif processor == current_user:
					logger.info(f"Current user: {current_user} is the rightful processor and so is allowed access")
					return f(*args, **kwargs)
				else:
					logger.info(f"""Current user: {current_user} is not the processor. Denying them access""")
					flash(("The processor has already been assigned for this entry "
							  "and you are not them. Please email us at lightservhelper@gmail.com "  
						      "if you think there has been a mistake."),'warning')
					return redirect(url_for('main.welcome'))
		else:
			next_url = request.url
			login_url = '%s?next=%s' % (url_for('main.login'), next_url)
			return redirect(login_url)
	return decorated_function

def check_clearing_completed(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		request_name = kwargs['request_name']
		sample_name = kwargs['sample_name']
		username = kwargs['username']
		sample_contents = db_lightsheet.Request.Sample() & f'request_name="{request_name}"' & \
			f'username="{username}"' & f'sample_name="{sample_name}"'
		# print(sample_contents)
		clearing_protocol, antibody1, antibody2 = sample_contents.fetch1(
			'clearing_protocol','antibody1','antibody2')
		clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & f'request_name="{request_name}"' & \
	 		f'username="{username}"' & f'clearing_protocol="{clearing_protocol}"' & \
	 		f'antibody1="{antibody1}"' & f'antibody2="{antibody2}"'
		clearing_progress = clearing_batch_contents.fetch1('clearing_progress')

		if clearing_progress != 'complete':
			flash(f"Clearing must be completed first for sample_name={sample_name}",'warning')
			return redirect(url_for('requests.request_overview',username=username,
				request_name=request_name,
				sample_name=sample_name))
		else:
			return f(*args, **kwargs)
	return decorated_function

def check_imaging_completed(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		request_name = kwargs['request_name']
		sample_name = kwargs['sample_name']
		username = kwargs['username']
		imaging_request_number = kwargs['imaging_request_number']
		imaging_request_contents = db_lightsheet.Request.ImagingRequest() & \
		 	f'request_name="{request_name}"' & \
		 	f'username="{username}"' & f'sample_name="{sample_name}"' & \
		 	f'imaging_request_number="{imaging_request_number}"'
		imaging_progress = imaging_request_contents.fetch1('imaging_progress')
		if imaging_progress != 'complete':
			flash(f"Imaging must be completed first for sample_name={sample_name}"
				  f", imaging_request_number={imaging_request_number}",'danger')
			return redirect(url_for('requests.request_overview',username=username,
				request_name=request_name,
				sample_name=sample_name))
		else:
			return f(*args, **kwargs)
	return decorated_function

def check_some_precomputed_pipelines_completed(f):
	""" Given a processing request check whether
	at least one of the precomputed pipelines 
	is complete """
	@wraps(f)
	def decorated_function(*args, **kwargs):
		request_name = kwargs['request_name']
		sample_name = kwargs['sample_name']
		username = kwargs['username']
		imaging_request_number = kwargs['imaging_request_number']
		processing_request_number = kwargs['processing_request_number']
		imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & \
		 	f'request_name="{request_name}"' & \
		 	f'username="{username}"' & f'sample_name="{sample_name}"' & \
		 	f'imaging_request_number="{imaging_request_number}"'
		processing_channel_contents = db_lightsheet.Request.ProcessingChannel() & \
		 	f'request_name="{request_name}"' & \
		 	f'username="{username}"' & f'sample_name="{sample_name}"' & \
		 	f'imaging_request_number="{imaging_request_number}"' & \
		 	f'processing_request_number="{processing_request_number}"' 
		""" check for any of the channels whether left or right light sheet 
		raw precomputed pipeline has been run """
		left_raw_precomputed_array = \
			imaging_channel_contents.fetch('left_lightsheet_precomputed_spock_job_progress')
		right_raw_precomputed_array = \
			imaging_channel_contents.fetch('right_lightsheet_precomputed_spock_job_progress')
		logger.debug(left_raw_precomputed_array)
		logger.debug(right_raw_precomputed_array)
		any_left_raw_precomputed_complete = any([x=='COMPLETED' for x in left_raw_precomputed_array])
		any_right_raw_precomputed_complete = any([x=='COMPLETED' for x in right_raw_precomputed_array])
		if any_left_raw_precomputed_complete or any_right_raw_precomputed_complete:
			return f(*args, **kwargs)
		
		""" check for any of the channels whether left or right light sheet
		stitched precomputed pipeline has been run """
		left_stitched_precomputed_array = \
			processing_channel_contents.fetch('left_lightsheet_stitched_precomputed_spock_job_progress')
		right_stitched_precomputed_array = \
			processing_channel_contents.fetch('right_lightsheet_stitched_precomputed_spock_job_progress')
		any_left_stitched_precomputed_complete = any([x=='COMPLETED' for x in left_stitched_precomputed_array])
		any_right_stitched_precomputed_complete = any([x=='COMPLETED' for x in right_stitched_precomputed_array])
		if any_left_stitched_precomputed_complete or any_right_stitched_precomputed_complete:
			return f(*args, **kwargs)

		""" check for any of the channels whether blended
		precomputed pipeline has been run """
		blended_precomputed_array,downsized_precomputed_array,registered_precomputed_array = \
			processing_channel_contents.fetch(
				'blended_precomputed_spock_job_progress',
				'downsized_precomputed_spock_job_progress',
				'registered_precomputed_spock_job_progress',
				)
		any_blended_precomputed_complete = any([x=='COMPLETED' for x in blended_precomputed_array])
		any_downsized_precomputed_complete = any([x=='COMPLETED' for x in downsized_precomputed_array])
		any_registered_precomputed_complete = any([x=='COMPLETED' for x in registered_precomputed_array])
		if (any_blended_precomputed_complete or 
			any_downsized_precomputed_complete or  
			any_registered_precomputed_complete):
			return f(*args, **kwargs)

		flash('No data ready to be visualized for this request at this time.','danger')
		return redirect(url_for('requests.request_overview',
			username=username,request_name=request_name))
		
	return decorated_function
def toabs(path):
	""" Convert relative path to absolute path. From Cloudvolume.lib """
	path = os.path.expanduser(path)
	return os.path.abspath(path)

def mymkdir(path,mode=0o777):
	""" Make directories recursively as needed up to path,
	checking to make sure directory does not already exist. Modified 
	from Cloudvolume.lib """
	path = toabs(path)

	try:
		if path != '' and not os.path.exists(path):
			os.makedirs(path)
			os.chmod(path=path,mode=mode)
	except OSError as e:
		if e.errno == 17: # File Exists
			time.sleep(0.1)
			return mymkdir(path)
		else:
			raise

	return path

def check_imaging_request_precomputed(f):
	""" Ensures that all of the
	raw data in an imaging request that 
	can be made into precomputed format 
	(i.e the non-tiled channels) is completed converted.
	"""
	@wraps(f)
	def decorated_function(*args, **kwargs):
		request_name = kwargs['request_name']
		sample_name = kwargs['sample_name']
		username = kwargs['username']
		imaging_request_number = kwargs['imaging_request_number']
		restrict_dict = dict(username=username,request_name=request_name,
				sample_name=sample_name,imaging_request_number=imaging_request_number)
		imaging_channel_contents = db_lightsheet.Request.ImagingChannel() & restrict_dict
		imaging_request_job_statuses = []
		for imaging_channel_dict in imaging_channel_contents:
			left_lightsheet_used = imaging_channel_dict['left_lightsheet_used']
			right_lightsheet_used = imaging_channel_dict['right_lightsheet_used']
			if left_lightsheet_used:
				job_status = imaging_channel_dict['left_lightsheet_precomputed_spock_job_progress']
				imaging_request_job_statuses.append(job_status)
			if right_lightsheet_used:
				job_status = imaging_channel_dict['right_lightsheet_precomputed_spock_job_progress']
				imaging_request_job_statuses.append(job_status)
		# logger.debug("job statuses for this imaging request:")
		# logger.debug(imaging_request_job_statuses)
		if len(imaging_request_job_statuses) == 0:
			flash(f"Raw images are not visualizable for this imaging request.",'danger')
			return redirect(url_for('requests.request_overview',username=username,
				request_name=request_name,
				sample_name=sample_name))
		if all(x=='COMPLETED' for x in imaging_request_job_statuses):
			return f(*args, **kwargs)
		else:
			flash(f"Images are not done being converted so that Neuroglancer can visualize them. "
				  f"Try again later.",'danger')
			return redirect(url_for('requests.request_overview',username=username,
				request_name=request_name,
				sample_name=sample_name))
			
	return decorated_function