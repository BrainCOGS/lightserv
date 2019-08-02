from flask import url_for

# def test_user_in_db(test_client,init_database):
# 	""" Test that the new user added in the fixture init_database
# 	actually appears in the database"""


def test_logged_in(test_client,init_database,login_response): 
	""" Test whether a user is logged in. Requires test_client() 
	and init_database() fixtures because those are required to be logged in. 
	init_database() does not re-load because it has session scope 
	but it still needs to be an argument so that the login can proceed."""
	assert b'Logged in as:' in login_response.data
	# print login_response.data

def test_logout(test_client,init_database,login_response): 
	response = test_client.get(url_for('users.logout'),follow_redirects=True)
	assert b'Log In' in response.data 


