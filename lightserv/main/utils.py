from flask import session,request,url_for,redirect, flash
from functools import wraps

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
			if session['user'] in ['ahoag','ll3','zmd','jduva']:
				return f(*args, **kwargs)
			else:
				flash('''You do not have permission to access this. 
					Ask a site or clearing admin to be granted access.''','warning')
				return redirect(url_for('main.home'))
		else:
			next_url = request.url
			login_url = '%s?next=%s' % (url_for('main.login'), next_url)
			return redirect(login_url)
	return decorated_function