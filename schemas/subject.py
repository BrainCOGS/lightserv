"""This module defines tables in the schema U19_subject"""

import datajoint as dj
import os, sys

if os.environ.get('FLASK_MODE') == 'TEST':
    dj.config['database.host'] = '127.0.0.1'
    dj.config['database.port'] = 3306

    dj.config['database.user'] = os.environ['DJ_DB_TEST_USER']
    dj.config['database.password'] = os.environ['DJ_DB_TEST_PASS']
    print("setting up test subject schema")
    schema = dj.schema('ahoag_subject_test')
    schema.drop()
    schema = dj.schema('ahoag_subject_test')
else:
    sys.exit()

from . import lab


@schema
class Species(dj.Lookup):
    definition = """
    binomial             : varchar(32)                  # binomial
    ---
    species_nickname     : varchar(32)                  # nickname
    """
    contents = [
        ['Mus musculus', 'Laboratory mouse']
    ]


@schema
class Strain(dj.Lookup):
    definition = """
    strain_name          : varchar(32)                  # strain name
    ---
    strain_description="" : varchar(255)                 # description
    """
    contents = [
        ['C57BL6/J', '']
    ]

@schema
class Line(dj.Lookup):
    definition = """
    line                 : varchar(128)                 # name
    ---
    -> Species
    -> Strain
    line_description=""  : varchar(2048)                # description
    target_phenotype=""  : varchar(255)                 # target phenotype
    is_active=1          : tinyint                      # is active
    """
    contents = [
        ['Unknown', 'Mus musculus', 'C57BL6/J', '', '', 1],
        ['C57BL6/J', 'Mus musculus', 'C57BL6/J', 'wild-type mice', '', 1],
        ['VGAT-ChR2-EYFP', 'Mus musculus', 'C57BL6/J', '', '', 1],
        ['Ai93-Emx1', 'Mus musculus', 'C57BL6/J', '', '', 1],
        ['Thy1-GP5.3', 'Mus musculus', 'C57BL6/J', '', '', 1],
        ['Thy1-YFP', 'Mus musculus', 'C57BL6/J', '', '', 1],
        ['DAT-IRES-CRE', 'Mus musculus', 'C57BL6/J', '', '', 1],
        ['DAT-Ai148', 'Mus musculus', 'C57BL6/J', '', '', 1],
        ['Slc17a7-Ai148', 'Mus musculus', 'C57BL6/J', '', '', 1],
        ['D1-CRE', 'Mus musculus', 'C57BL6/J', '', '', 1],
        ['D2-CRE', 'Mus musculus', 'C57BL6/J', '', '', 1]
    ]


@schema
class Subject(dj.Manual):
    definition = """
    subject_fullname     : varchar(64)                  # username_mouse_nickname
    ---
    subject_nickname     : varchar(16)
    -> lab.User
    genomics_id=null     : int                          # number from the facility
    sex="Unknown"        : enum('Male','Female','Unknown') # sex
    dob=null             : date                         # birth date
    head_plate_mark=null : blob                         # little drawing on the head plate for mouse identification
    -> lab.Location
    -> [nullable] lab.Protocol
    -> [nullable] Line
    subject_description="" : varchar(255)               # description
    initial_weight=null  : float
    """
