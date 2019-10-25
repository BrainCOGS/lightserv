""" conftest.py 
pytest sees this file and loads all 
fixtures into memory so that they 
don't need to be imported for the 
tests in other test modules.
This file must have the name conftest.py
"""

import os, sys
if os.environ.get('FLASK_MODE') != 'TEST':
	raise KeyError("Must set environmental variable FLASK_MODE=TEST")

from flask_testing import TestCase
from lightserv import create_app, config
# from ..models import User, Experiment
import secrets
import pytest
from flask import url_for
import datajoint as dj


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
def test_schema():
	""" Create the database and the database tables """
	print('----------Setup test schema----------')
	# test_schema = dj.create_virtual_module('test_lightsheet','test_lightsheet')
	from lightserv import db_lightsheet
	yield db  # this is where the testing happens!
	print('----------Teardown test schema----------')
	db.schema.drop(force=True)

@pytest.fixture(scope='function')
def test_login(test_client):
	""" Log the user in. Requires a test_client fixture to do this. """
	print('----------Setup login response----------')
	with test_client.session_transaction() as sess:
		sess['user'] = 'ahoag'

	yield sess
	print('----------Teardown login response----------')
	pass
