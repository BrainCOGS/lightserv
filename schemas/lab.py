"""This module defines tables in the schema U19_lab"""


import datajoint as dj
import os, sys

if os.environ.get('FLASK_MODE') == 'TEST':
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306

    dj.config['database.user'] = os.environ['DJ_DB_TEST_USER']
    dj.config['database.password'] = os.environ['DJ_DB_TEST_PASS']
    print("setting up test lab schema")
    schema = dj.schema('ahoag_lab_test')
    schema.drop()
    schema = dj.schema('ahoag_lab_test')
else:
    sys.exit()


@schema
class Location(dj.Lookup):
    definition = """
    # The physical location at which an session is performed or appliances
    # are located. This could be a room, a rig, or a bench
    location             : varchar(32)
    ---
    location_description="" : varchar(255)
    """
    contents = [
        ['Bezos2', ''],
        ['Bezos3',  ''],
        ['BezosMeso', ''],
        ['TrainVR1', ''],
        ['floater', ''],
        ['vivarium', ''],
        ['pni-171jppw32', ''],
        ['pni-174cr4jk2', ''],
        ['valhalla', '']
    ]


@schema
class Project(dj.Lookup):
    definition = """
    project              : varchar(64)
    ---
    project_description="" : varchar(255)
    """
    contents = [
        ['behavioral task', ''],
        ['accumulation of evidence', '']
    ]


@schema
class MobileCarrier(dj.Lookup):
    definition = """
    mobile_carrier       : varchar(16)                  # allowed mobile carries
    """
    contents = zip([
        'alltel',
        'att',
        'boost',
        'cingular',
        'cingular2',
        'cricket',
        'metropcs',
        'nextel',
        'sprint',
        'tmobile',
        'tracfone',
        'uscellular',
        'verizon',
        'virgin'
    ])


@schema
class User(dj.Manual):
    definition = """
    user_id              : varchar(32)                  # username
    ---
    user_nickname        : varchar(32)                  # same as netID for new users, for old users, this is used in the folder name etc.
    full_name=null       : varchar(32)                  # first name
    email=null           : varchar(64)                  # email address
    phone=null           : varchar(12)                  # phone number
    -> [nullable] MobileCarrier
    slack=null           : varchar(32)                  # slack username
    contact_via          : enum('Slack','text','Email')
    presence             : enum('Available','Away')
    primary_tech="N/A"   : enum('yes','no','N/A')
    tech_responsibility="N/A" : enum('yes','no','N/A')
    day_cutoff_time      : blob
    slack_webhook=null   : varchar(255)
    watering_logs=null   : varchar(255)
    """

@schema
class Protocol(dj.Lookup):
    definition = """
    protocol             : varchar(16)                  # protocol number
    ---
    reference_weight_pct=null : float                        # percentage of initial allowed
    protocol_description="" : varchar(255)                 # description
    """
    contents = [['1910', 0.8, 'Tank Lab protocol']]
