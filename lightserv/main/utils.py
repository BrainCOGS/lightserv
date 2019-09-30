from flask import session,request,url_for,redirect
from functools import wraps

def table_sorter(dic,sort_key):
    if type(dic[sort_key]) == str:
        return dic[sort_key].lower()
    
    return dic[sort_key]

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