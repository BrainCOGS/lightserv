from flask import url_for


def test_login_redirects(test_client):
	""" Check that when someone lands on the welcome page they are logged in and then the 
	welcome page loads properly """
	response = test_client.get(url_for('main.welcome'),follow_redirects=True)

	assert b'Welcome to the' in response.data and b'How to contact us?' in response.data

def test_welcome_page(test_client,test_login):
	""" Check that the welcome page loads properly (once already logged in) """
	response = test_client.get(url_for('main.welcome'),follow_redirects=True)

	assert b'Welcome to the' in response.data and b'How to contact us?' in response.data


def test_home_page(test_client,test_login):
	""" Check that the welcome page loads properly """
	response = test_client.get(url_for('main.home'),follow_redirects=True)

	assert b'All core facility requests:' in response.data 
