from flask import url_for

def test_welcome_login_redirects(test_client):
	""" Check that when someone lands on the welcome page they are logged in and then the 
	welcome page loads properly """
	response = test_client.get(url_for('main.welcome'),
		follow_redirects=True)

	assert b'Welcome to the' in response.data and b'How to contact us?' in response.data

def test_welcome_page(test_client,test_login):
	""" Check that the welcome page loads properly (once already logged in) """
	response = test_client.get(url_for('main.welcome'),
		follow_redirects=True)

	assert b'Welcome to the' in response.data and b'How to contact us?' in response.data


def test_login_inserts_user(test_client,test_login):
	from lightserv import db_lightsheet
	user_contents = db_lightsheet.User()
	print(user_contents)
	assert len(user_contents) > 0 

def test_welcome_page_firefox_warning(test_client_firefox):
	""" Check that the when user logs in and accesses welcome page
	for the first time they get a flash message warning them to not 
	firefox"""
	response = test_client_firefox.get(url_for('main.welcome'),
		follow_redirects=True)

	assert b'Welcome to the' in response.data and b'How to contact us?' in response.data
	assert b'Warning: parts of this web portal were not completely tested on your browser: firefox' in response.data