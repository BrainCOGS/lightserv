import datajoint as dj
import socket
import os


if os.environ.get('FLASK_MODE') == 'TEST':
    dj.config['database.host'] = '127.0.0.1'
    dj.config['database.port'] = 3306
    dj.config['database.user'] = os.environ['DJ_DB_TEST_USER']
    dj.config['database.password'] = os.environ['DJ_DB_TEST_PASS']
    print("setting up test admin schema")

    schema = dj.schema('ahoag_admin_test')
    schema.drop()
    schema = dj.schema('ahoag_admin_test')
else:
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306
    dj.config['database.user'] = os.environ['DJ_DB_USER']
    dj.config['database.password'] = os.environ['DJ_DB_PASS']
    print("setting up real admin schema")

    # schema = dj.schema('u19lightserv_appcore')
    schema = dj.schema('ahoag_admin_demo')
    schema.drop()
    schema = dj.schema('ahoag_admin_demo')

@schema 
class UserActionLog(dj.Manual):
    definition = """    # event logging table 
    event_number  : int auto_increment
    ---
    timestamp = CURRENT_TIMESTAMP : timestamp 
    browser_name    : varchar(255)
    browser_version : varchar(255)
    platform        : varchar(255)
    event=""  : varchar(255)  # custom message
    """

@schema 
class SpockJobManager(dj.Manual):
    definition = """    # Spock job management table 
    jobid  : varchar(16) # the jobid on spock
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---
    username : varchar(32)
    status : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING")
    """

