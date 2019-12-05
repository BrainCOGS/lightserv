from flask import session,request,url_for,redirect, flash, current_app
from functools import wraps
from lightserv import db_lightsheet
import datajoint as dj

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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

def logged_in_as_clearer(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'user' in session: # user is logged in 
			current_user = session['user']

			request_name = kwargs['request_name']
			sample_name = kwargs['sample_name']
			username = kwargs['username']
			sample_contents = db_lightsheet.Sample() & f'request_name="{request_name}"' & \
			 	f'username="{username}"' & f'sample_name="{sample_name}"'
			clearer = sample_contents.fetch1('clearer')
			''' check to see if user assigned themself as clearer '''
			if clearer == None:
				logger.info("Clearing entry form accessed with clearer not yet assigned. ")
				''' now check to see if user is a designated clearer ''' 
				if current_user in current_app.config['CLEARING_ADMINS']: # 
					dj.Table._update(sample_contents,'clearer',current_user)
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
					logger.info(f"""Current user: {current_user} is not the clearer and not a clearing manager. Denying them access""")
					flash('''The clearer has already been assigned for this entry and you are not them.  
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
			
			imaging_request_contents = db_lightsheet.Sample.ImagingRequest() & f'request_name="{request_name}"' & \
			 	f'username="{username}"' & f'sample_name="{sample_name}"' & \
			 	f'imaging_request_number="{imaging_request_number}"'
			processor = imaging_request_contents.fetch1('processor')
			''' check to see if user assigned themself as processor '''
			if processor == None:
				logger.info("processing entry form accessed with processor not yet assigned. ")
				''' now check to see if user is a designated processor ''' 
				if current_user in current_app.config['PROCESSING_ADMINS']: # 
					dj.Table._update(imaging_request_contents,'processor',current_user)
					logger.info(f"{current_user} is a designated processor and is now assigned as the processor")
					return f(*args, **kwargs)
				else: # user is not a designated processor and did not self assign
					logger.info(f"""Current user: {current_user} is not a designated processor and did not specify themselves
					 as the processor when submitting request. Denying them access""")
					flash('''You do not have permission to access the processing form for this experiment. 
						Please email us at lightservhelper@gmail.com if you think there has been a mistake.''','warning')
					return redirect(url_for('main.welcome'))
			else: # processor is assigned 
				if processor in current_app.config['PROCESSING_ADMINS']: # one of the admins started the form
					if current_user in current_app.config['PROCESSING_ADMINS']: # one of the admins is accessing the form
						
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
					logger.info(f"""{current_user} is not the processor. Denying them access""")
					flash(("The processor has already been assigned for this entry "
							  "and you are not them. Please email us at lightservhelper@gmail.com "  
						      "if you think there has been a mistake."),'warning')
					return redirect(url_for('main.welcome'))
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

			username = kwargs['username']
			request_name = kwargs['request_name']
			sample_name = kwargs['sample_name']
			imaging_request_number = kwargs['imaging_request_number']
			
			imaging_request_contents = db_lightsheet.Sample.ImagingRequest() & f'request_name="{request_name}"' & \
			 	f'username="{username}"' & f'sample_name="{sample_name}"' & \
			 	f'imaging_request_number="{imaging_request_number}"'
			imager = imaging_request_contents.fetch1('imager')
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
					if current_user in  current_app.config['IMAGING_ADMINS']: # one of the admins is accessing the form
						
						if current_user != imager:
							logger.info(f"""Current user: {current_user} accessed the form of which {imager} is the imager""")
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



def check_clearing_completed(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		request_name = kwargs['request_name']
		sample_name = kwargs['sample_name']
		username = kwargs['username']
		sample_contents = db_lightsheet.Sample() & f'request_name="{request_name}"' & \
		 	f'username="{username}"' & f'sample_name="{sample_name}"'
		clearing_progress = sample_contents.fetch1('clearing_progress')
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
		imaging_request_contents = db_lightsheet.Sample.ImagingRequest() & \
		 	f'request_name="{request_name}"' & \
		 	f'username="{username}"' & f'sample_name="{sample_name}"' & \
		 	f'imaging_request_number="{imaging_request_number}"'
		imaging_progress = imaging_request_contents.fetch1('imaging_progress')
		if imaging_progress != 'complete':
			flash(f"Imaging must be completed first for sample_name={sample_name}"
				  f", imaging_request_number={imaging_request_number}",'warning')
			return redirect(url_for('requests.request_overview',username=username,
				request_name=request_name,
				sample_name=sample_name))
		else:
			return f(*args, **kwargs)
	return decorated_function