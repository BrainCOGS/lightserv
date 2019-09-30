from flask import url_for

def test_home_redirects(test_client):
	""" Tests that the home page returns a 302 code (i.e. a redirect signal) for a not logged in user """
	response = test_client.get(url_for('main.home'),content_type='html/text')
	assert response.status_code == 302, 'Status code is {0}, but should be 302 (redirect)'.format(response.status_code)

def test_home_login_redirect(test_client):
	""" Tests that the home page redirects to the login route """
	response = test_client.get(url_for('main.home'),content_type='html/text',follow_redirects=True)

	assert response.status_code == 200, 'Status code is {0}, but should be 200'.format(response.status_code)
	assert b'Logged in as' in response.data