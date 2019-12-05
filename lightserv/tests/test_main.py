from flask import url_for

def test_home_redirects(test_client):
	""" Tests that the home page returns a 302 code (i.e. a redirect signal) for a not logged in user """
	response = test_client.get(url_for('main.home'),
		content_type='html/text')
	assert response.status_code == 302, \
			'Status code is {0}, but should be 302 (redirect)'.\
			 format(response.status_code)

def test_home_login_redirects(test_client):
	""" Tests that the home page redirects to the login route """
	response = test_client.get(url_for('main.home'),content_type='html/text',
		follow_redirects=True)

	assert response.status_code == 200, 'Status code is {0}, but should be 200'.format(response.status_code)
	assert b'Logged in as' in response.data

def test_welcome_login_redirects(test_client):
	""" Check that when someone lands on the welcome page they are logged in and then the 
	welcome page loads properly """
	response = test_client.get(url_for('main.welcome'),follow_redirects=True)

	assert b'Welcome to the' in response.data and b'How to contact us?' in response.data

def test_welcome_page(test_client,test_login):
	""" Check that the welcome page loads properly (once already logged in) """
	response = test_client.get(url_for('main.welcome'),follow_redirects=True)

	assert b'Welcome to the' in response.data and b'How to contact us?' in response.data


def test_home_page(test_client,test_login):
	""" Check that the home page loads properly """
	response = test_client.get(url_for('main.home'),follow_redirects=True)

	assert b'All core facility requests:' in response.data 
