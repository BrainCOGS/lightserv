from flask import url_for

def test_index(test_client):
	response = test_client.get(url_for('users.login'),content_type='html/text')
	assert response.status_code == 200, 'Status code is {0}, but should be 200'.format(response.status_code)

def test_login_page_loads(test_client):
	response = test_client.get(url_for('users.login'))
	assert b'Log In' in response.data