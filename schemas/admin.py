import datajoint as dj
import socket
import os

dj.config['database.host'] = '127.0.0.1'
dj.config['database.port'] = 3306

dj.config['database.user'] = 'ahoag'
dj.config['database.password'] = 'gaoha'

if os.environ.get('FLASK_MODE') == 'TEST':
    print("setting up test admin schema")
    schema = dj.schema('ahoag_admin_test')
    schema.drop()
    schema = dj.schema('ahoag_admin_test')
else:
    print("setting up real admin schema")
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
