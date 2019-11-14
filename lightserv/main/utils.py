from flask import session,request,url_for,redirect, flash
from functools import wraps
from lightserv import db_lightsheet
import datajoint as dj

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/clearing_routes.log')
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
			username = session['user']
			# if username == 'ahoag': # admin rights
			# 	return f(*args, **kwargs)
			experiment_name = kwargs['experiment_name']
			sample_name = kwargs['sample_name']
			username = kwargs['username']
			sample_contents = db_lightsheet.Sample() & f'experiment_name="{experiment_name}"' & \
			 	f'username="{username}"' & f'sample_name="{sample_name}"'
			clearer = sample_contents.fetch1('clearer')
			''' check to see if user assigned themself as clearer '''
			if clearer == "not yet assigned":
				logger.info("Clearing entry form accessed with clearer not yet assigned. ")
				''' now check to see if user is a designated clearer ''' 
				if username in ['ll3','zmd','jduva','ahoag','kellyms']: # 
					dj.Table._update(sample_contents,'clearer',username)
					logger.info(f"{username} is a designated clearer and is now assigned as the clearer")
					return f(*args, **kwargs)
				else: # user is not a designated clearer and did not self assign
					logger.info(f"""{username} is not a designated clearer and did not specify themselves
					 as the clearer when submitting request. Denying them access""")
					flash('''You do not have permission to access the clearing form for this experiment. 
						Please email us at lightservhelper@gmail.com if you think there has been a mistake.''','warning')
					return redirect(url_for('main.home'))
			else: # clearer is assigned - only allow access to clearing entry to them
				if username == clearer:
					logger.info(f"{username} is the rightful clearer and accessed the clearing entry form")
					return f(*args, **kwargs)
				else:
					logger.info(f"""{username} is not the clearer. Denying them access""")
					flash('''The clearer has already been assigned for this entry and you are not them.  
						Please email us at lightservhelper@gmail.com if you think there has been a mistake.''','warning')
					return redirect(url_for('main.home'))
		else:
			next_url = request.url
			login_url = '%s?next=%s' % (url_for('main.login'), next_url)
			return redirect(login_url)
	return decorated_function

def logged_in_as_imager(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'user' in session: # user is logged in 
			username = session['user']
			# if username == 'ahoag': # admin rights
			# 	return f(*args, **kwargs)
			experiment_name = kwargs['experiment_name']
			sample_name = kwargs['sample_name']
			username = kwargs['username']
			sample_contents = db_lightsheet.Sample() & f'experiment_name="{experiment_name}"' & \
			 	f'username="{username}"' & f'sample_name="{sample_name}"'
			imager = sample_contents.fetch1('imager')
			''' check to see if user assigned themself as imager '''
			if imager == "not yet assigned":
				logger.info("Imaging entry form accessed with imager not yet assigned. ")
				''' now check to see if user is a designated imager ''' 
				if username in ['zmd','jduva','ahoag','kellyms']: # 
					dj.Table._update(sample_contents,'imager',username)
					logger.info(f"{username} is a designated imager and is now assigned as the imager")
					return f(*args, **kwargs)
				else: # user is not a designated imager and did not self assign
					logger.info(f"""{username} is not a designated imager and did not specify themselves
					 as the imager when submitting request. Denying them access""")
					flash('''You do not have permission to access the imaging form for this experiment. 
						Please email us at lightservhelper@gmail.com if you think there has been a mistake.''','warning')
					return redirect(url_for('main.home'))
			else: # imager is assigned - only allow access to imaging entry to them
				if imager == username:
					logger.info(f"{username} is the rightful imager and accessed the imaging entry form")
					return f(*args, **kwargs)
				else:
					logger.info(f"""{username} is not the imager. Denying them access""")
					flash('''The imager has already been assigned for this entry and you are not them.  
						Please email us at lightservhelper@gmail.com if you think there has been a mistake.''','warning')
					return redirect(url_for('main.home'))
		else:
			next_url = request.url
			login_url = '%s?next=%s' % (url_for('main.login'), next_url)
			return redirect(login_url)
	return decorated_function


def check_clearing_completed(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		experiment_name = kwargs['experiment_name']
		sample_name = kwargs['sample_name']
		username = kwargs['username']
		sample_contents = db_lightsheet.Sample() & f'experiment_name="{experiment_name}"' & \
		 	f'username="{username}"' & f'sample_name="{sample_name}"'
		clearing_progress = sample_contents.fetch1('clearing_progress')
		if clearing_progress != 'complete':
			flash(f"Clearing must be completed first for sample_name={sample_name}",'warning')
			return redirect(url_for('experiments.exp',username=username,
				experiment_name=experiment_name,
				sample_name=sample_name))
		else:
			return f(*args, **kwargs)
	return decorated_function


def check_imaging_completed(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		experiment_name = kwargs['experiment_name']
		sample_name = kwargs['sample_name']
		username = kwargs['username']
		sample_contents = db_lightsheet.Sample() & f'experiment_name="{experiment_name}"' & \
		 	f'username="{username}"' & f'sample_name="{sample_name}"'
		imaging_progress = sample_contents.fetch1('imaging_progress')
		if imaging_progress != 'complete':
			print("imaging not complete")
			flash(f"Imaging must be completed first for sample_name={sample_name}",'warning')
			return redirect(url_for('experiments.exp',username=username,
				experiment_name=experiment_name,
				sample_name=sample_name))
		else:
			return f(*args, **kwargs)
	return decorated_function