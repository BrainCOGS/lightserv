from flask import url_for,session,current_app

def test_logged_in(test_client,test_schema,test_login): 
	""" Test whether a user is logged in. Requires test_client() 
	and init_database() fixtures because those are required to be logged in. 
	init_database() does not re-load because it has session scope 
	but it still needs to be an argument so that the login can proceed."""
	assert f'''Logged in as: {session['user']}'''.encode() in test_login.data
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

def test_reset_password_request(test_client):
	response = test_client.post(url_for('users.reset_request'),
		data=dict(email='testuser@demo.com'),
		follow_redirects=True)
	print(response.data)
	assert b'Log In' in response.data # a successful password request brings one to the login page

def test_reset_password_request_bademail(test_client):
	response = test_client.post(url_for('users.reset_request'),
		data=dict(email='baduser@demo.com'),
		follow_redirects=True)
	print(response.data)
	assert b'Log In' not in response.data # a successful password request brings one to the login page
	assert b'Reset Password' in response.data


def test_reset_password(test_client):
	""" First get a token """
	from lightserv.users.utils import get_reset_token
	from itsdangerous import TimedJSONWebSignatureSerializer as Serializer

	username = 'testuser'
	token = get_reset_token(username) 
	response = test_client.post(url_for('users.reset_token',token=token),data=dict(
		password='testing2',confirm_password='testing2'),
	follow_redirects=True
	)
	assert b'Log In' in response.data # a successful password reset brings one to the login page