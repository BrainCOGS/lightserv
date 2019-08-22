from flask import url_for,session

# def test_user_in_db(test_client,init_database):
# 	""" Test that the new user added in the fixture init_database
# 	actually appears in the database"""


def test_logged_in(test_client,test_schema,test_login): 
	""" Test whether a user is logged in. Requires test_client() 
	and init_database() fixtures because those are required to be logged in. 
	init_database() does not re-load because it has session scope 
	but it still needs to be an argument so that the login can proceed."""
	assert f'''Logged in as: {session['user']}'''.encode('utf-8') in test_login.data
	# print login_response.data

def test_logout(test_client,test_schema,test_login): 
	response = test_client.get(url_for('users.logout'),follow_redirects=True)
	assert b'Log In' in response.data 


def test_register_new_user(test_client,test_schema):
	response = test_client.post(url_for('users.register'),data=dict(
		username='new_user',email='new_user@princeton.edu',
		password='testpass',confirm_password='testpass'
		),
	follow_redirects=True
	)
	assert b'Log In' in response.data

def test_deny_register_existing_user(test_client,test_schema):
	response = test_client.post(url_for('users.register'),data=dict(
		username='testuser',email='new_user@princeton.edu',
		password='testpass',confirm_password='testpass'
		),
	follow_redirects=True
	)
	assert b'Create Your Account' in response.data

