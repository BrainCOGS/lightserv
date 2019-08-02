""" conftest.py 
pytest sees this file and loads all 
fixtures into memory so that they 
don't need to be imported for the 
tests in other test modules.
This file must have the name conftest.py
"""

from flask_testing import TestCase
from .. import create_app, db, bcrypt, config
from ..models import User, Experiment
import secrets
import pytest
from flask import url_for

@pytest.fixture(scope='session') 
def test_client():
	""" Create the application and the test client.

	The way a fixture works is whaterver is yielded
	by this function will be passed to the tests that 
	take the name of the fixture function as an argument.

	We use scope='module' because we only want the test_client
	to last for tests in a single module. If we use scope='session',
	then the state of the test client will be altered by one test module,
	and then that is the state of the client when the next test module
	is executed. This will mean the test order will matter which is a 
	terrible way to do things. It does mean we will have to reload the
	test client in each module in which we use it, so it is slightly slower this way."" 
	"""
	print('----------Setup test client----------')
	app = create_app(config_class=config.TestConfig)
	testing_client = app.test_client()

	ctx = app.test_request_context() # makes it so I can use the url_for() function in the tests

	ctx.push()
	yield testing_client # this is where the testing happens
	print('-------Teardown test client--------')
	ctx.pop()

@pytest.fixture(scope='session') 
def init_database():
	""" Create the database and the database tables """
	print('----------Setup init database----------')

	db.create_all()
	hashed_password = bcrypt.generate_password_hash('admin').decode('utf-8')
	db.session.add(User(username="admin",email="ad@min.com",password=hashed_password))
	db.session.add(Experiment(dataset_hex=secrets.token_hex(5),title="Test Experiment",
		description="This is a test experiment",clearing_protocol="A brand new protocol",
		species="mouse",image_resolution=1.3,cell_detection=False,registration=False,
		fluorophores="None",injection_detection=True,probe_detection=True,user_id=1))

	db.session.commit()

	yield db  # this is where the testing happens!
	print('----------Teardown init database----------')
	db.drop_all()

@pytest.fixture(scope='function')
def login_response(test_client):
	""" """
	print('----------Setup login response----------')
	response = test_client.post(
				'/login',
				data=dict(email="ad@min.com", password="admin"),
				follow_redirects=True
			)
	yield response
	print('----------Teardown login response----------')
	pass
