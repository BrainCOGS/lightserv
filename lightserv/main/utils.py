from flask import session,request,url_for,redirect, flash
from functools import wraps
from lightserv import db_lightsheet

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

		if 'user' in session:
			username = session['user']
			if username in ['ll3','zmd','jduva']:
				logger.info(f"{session['user']} is a designated clearer")
				return f(*args, **kwargs)
			else:
				experiment_id = kwargs['experiment_id']
				exp_contents = db_lightsheet.Experiment() & f'experiment_id={experiment_id}'
				clearer = exp_contents.fetch1('clearer')
				if username == clearer:
					logger.info(f"{username} is the clearer.")
					return f(*args, **kwargs)	
				else:
					logger.info(f"{username} is neither the clearer nor a designated clearer. Denying them access")
					flash('''You do not have permission to access this. 
						Ask a site or clearing admin to be granted access.''','warning')
					return redirect(url_for('main.home'))
		else:
			next_url = request.url
			login_url = '%s?next=%s' % (url_for('main.login'), next_url)
			return redirect(login_url)
	return decorated_function