import datajoint as dj
import os
import csv
from flask_bcrypt import Bcrypt
import pkg_resources

DATA_PATH = pkg_resources.resource_filename('lightserv', 'data') # package name first then subdirectory next
# home = os.environ['HOME']
csv_file = DATA_PATH + '/pni_core_facility_request_responses4testing.txt'

def create_test_schema():
    """ If test schema already exists (from e.g. a failed previous test), then drop it """
    if 'ahoag_lightsheet_test' in dj.get_schema_names():
        print("Removing existing test schema")
        test_schema = dj.schema('ahoag_lightsheet_test')
        test_schema.drop(force=True)
        # test_schema = dj.create_virtual_module('ahoag_lightsheet_test','ahoag_lightsheet_test',create_schema=True,create_tables=True)
    test_schema = dj.schema('ahoag_lightsheet_test')
    # test_schema = dj.
    bcrypt = Bcrypt()

    @test_schema
    class User(dj.Lookup):
        definition = """
        # Users of the light sheet microscope
        username : varchar(20)      # user in the lab
        ---
        email       : varchar(50)
        password    : varchar(100)
        """

    @test_schema
    class Experiment(dj.Manual):
        definition = """ # Experiments performed using the light sheet microscope
        experiment_id           :   smallint auto_increment    # allowed here are sql datatypes.
        ----
        username                :   varchar(20)
        title                   :   varchar(100)
        description             :   varchar(250)
        notes = ""              :   varchar(1000)
        species                 :   varchar(50)
        clearing_protocol       :   enum("iDISCO+_immuno","iDISCO abbreviated clearing","uDISCO","iDISCO+","iDISCO_EdU")
        fluorophores            :   varchar(100)
        primary_antibody        :   varchar(100)
        secondary_antibody      :   varchar(100)
        image_resolution        :   enum("1.3x","4x")
        cell_detection          :   tinyint
        registration            :   tinyint
        probe_detection         :   tinyint
        injection_detection     :   tinyint
        """
    
    def fill_user_table():
        with open(csv_file, mode='r') as infile:
            reader = csv.reader(infile)
            data_dict = {}
            next(reader) # skips the header
            index = 0
            for row in reader:
                email = row[0]
                username = email.split('@')[0].lower()
                password = row[1]
                hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
                insert_user_list = [username,email,hashed_password]
                User().insert((insert_user_list,),skip_duplicates = True)
                index+=1

    column_names = ['username','title','description','notes','species','clearing_protocol',
                    'fluorophores','primary_antibody','secondary_antibody',
                    'image_resolution','cell_detection','registration',
                    'probe_detection','injection_detection']

    def fill_exp_table():
        with open(csv_file, mode='r') as infile:
            reader = csv.reader(infile)
            data_dict = {}
            next(reader) # skips the header
            index = 0
            for row in reader:
                email = row[0]
                username = email.split('@')[0].lower()
                insert_exp_list = [username] + row[3:]
                insert_dict = {column_names[ii]:insert_exp_list[ii] for ii in range(len(column_names))}
                Experiment().insert1(insert_dict,skip_duplicates=True)
    
    fill_user_table()
    fill_exp_table()



    return test_schema

