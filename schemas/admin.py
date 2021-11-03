import datajoint as dj
import socket
import os

if os.environ.get('FLASK_MODE') == 'TEST':
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306
    dj.config['database.user'] = os.environ['DJ_DB_TEST_USER']
    dj.config['database.password'] = os.environ['DJ_DB_TEST_PASS']
    print("setting up test admin schema")
    schema = dj.schema('ahoag_admin_test')

elif os.environ.get('FLASK_MODE') == 'DEV':
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306
    dj.config['database.user'] = os.environ['DJ_DB_USER']
    dj.config['database.password'] = os.environ['DJ_DB_PASS']
    print("setting up DEV: ahoag_appcore_copy schema")
    schema = dj.schema('ahoag_appcore_copy')
elif os.environ.get('FLASK_MODE') == 'PROD':
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306
    dj.config['database.user'] = os.environ['DJ_DB_USER']
    dj.config['database.password'] = os.environ['DJ_DB_PASS']
    print("setting up PROD: u19lightserv_appcore schema")
    schema = dj.schema('u19lightserv_appcore')
from . import lightsheet

@schema 
class UserActionLog(dj.Manual):
    definition = """    # event logging table 
    event_number  : int auto_increment
    ---
    timestamp = CURRENT_TIMESTAMP : timestamp 
    browser_name    : varchar(255)
    browser_version : varchar(255)
    platform        : varchar(255)
    event=""        : varchar(255)  # custom message
    """
  

@schema
class RequestFeedback(dj.Lookup):
    definition = """    # Table to keep track of users' feedback from the forms they submitted. 
    # Feedback is gathered after a delay from submitting a request so it may not be present in this table if the request was recent 
    -> lightsheet.Request
    ---
    clearing_rating : tinyint
    clearing_notes : varchar(512)
    imaging_rating : tinyint
    imaging_notes : varchar(512)
    processing_rating : tinyint
    processing_notes : varchar(512)
    other_notes : varchar(512)
    """