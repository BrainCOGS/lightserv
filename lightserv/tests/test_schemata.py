import datajoint as dj
import os
import csv
import pickle
import pkg_resources

DATA_PATH = pkg_resources.resource_filename('lightserv', 'data') # package name first then subdirectory next
# home = os.environ['HOME']
experiment_test_data_file = DATA_PATH + '/experiment_test_data.pkl'

def create_test_schema():
    """ If test schema already exists (from e.g. a failed previous test), then drop it """
    if 'ahoag_lightsheet_test' in dj.get_schema_names():
        print("Removing existing test schema")
        test_schema = dj.schema('ahoag_lightsheet_test')
        test_schema.drop(force=True)
        # test_schema = dj.create_virtual_module('ahoag_lightsheet_test','ahoag_lightsheet_test',create_schema=True,create_tables=True)
    test_schema = dj.schema('ahoag_lightsheet_test')
    # test_schema = dj.

    @test_schema
    class User(dj.Lookup):
        definition = """
        # Users of the light sheet microscope
        username : varchar(20)      # user in the lab
        ---
        email       : varchar(50)
        """

    @test_schema
    class Experiment(dj.Manual):
        definition = """ # Experiments performed using the light sheet microscope
        experiment_id           :   smallint auto_increment    # allowed here are sql datatypes.
        ----
        -> User 
        title                   :   varchar(100)
        description             :   varchar(250)
        notes = ""              :   varchar(1000)
        species                 :   varchar(50)
        clearing_protocol       :   enum("iDISCO+_immuno","iDISCO abbreviated clearing","iDISCO abbreviated clearing (rat)","uDISCO","iDISCO_EdU")
        clearing_progress       :   enum("incomplete","complete")
        fluorophores            :   varchar(100)
        antibody1               :   varchar(100)
        antibody2               :   varchar(100)
        image_resolution        :   enum("1.3x","4x")
        cell_detection          :   tinyint
        registration            :   tinyint
        probe_detection         :   tinyint
        injection_detection     :   tinyint
        """  
        
    @test_schema #  
    class Microscope(dj.Manual): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
        definition = """ # Periodic calibration data of the light sheet microscope
        entrynum                :   smallint auto_increment    # allowed here are sql datatypes.
        ----
        -> User              
        date                    :   varchar(10)    
        old_objective           :   varchar(50)
        new_objective           :   varchar(50)
        swapper                 :   varchar(250)
        calibration =           :   varchar(1000) 
        notes =                 :   varchar(1000)
        """

    with open(experiment_test_data_file,'rb') as f:
        experiment_test_data = pickle.load(f)

    


    return test_schema

    def fill_user_exp_tables():
        """ Fills the User() and Experiment() tables 
        using the form response data from the tab in the clearing google spreadsheet
        """
        exp_column_names = ['username','species','clearing_protocol','clearing_progress','title','description','fluorophores',\
                        'antibody1','antibody2','image_resolution',\
                        'cell_detection','registration','probe_detection','injection_detection','notes'] # order doesn't matter since we will be using these in a dictionary
        for form_response in experiment_test_data:
            # ignore blank lines
            if not form_response:
                continue
            assert len(form_response) == 14
            species = form_response[0].lower()
            clearing_protocol = form_response[1]
            if 'immunostaining' in clearing_protocol:
                clearing_protocol = 'iDISCO+_immuno'
            elif 'abbreviated' in clearing_protocol:
                if species == 'rat':
                    clearing_protocol = 'iDISCO abbreviated clearing (rat)'
                else:
                    clearing_protocol = 'iDISCO abbreviated clearing'
            elif 'EdU' in clearing_protocol:
                clearing_protocol = 'iDISCO_EdU'
            else: # don't change it
                pass
            clearing_progress = 'complete' # All of the ones in this sheet have already been completed
            title=form_response[2]
            description = form_response[3]
            fluorophores = form_response[4]
            primary_antibody = form_response[5]
            secondary_antibody = form_response[6]
            imaging_str = form_response[7]
            image_resolution = "1.3x" if "1.3x" in imaging_str else "4x"
            processing_str = form_response[8]
            processing_list = [x.lower() for x in processing_str.split(',')]

            cell_detection = 0
            registration = 0
            probe_detection = 0
            injection_detection = 0
            for item in processing_list:
                if 'cell detection' in item:
                    cell_detection = 1
                if 'registration' in item:
                    registration=1
                if 'probe' in item and 'detection' in item:
                    probe_detection = 1
                if 'injection' in item and 'detection' in item:
                    injection_detection =1
            notes = form_response[11]
            email = form_response[13]
            username = email.split('@')[0].lower() if 'princeton' in email else 'zmd' # zahra is the only one who used her gmail
            
            user_insert_dict = {'username':username,'email':email}
            
            exp_insert_row = [username,species,clearing_protocol,clearing_progress,title,description,fluorophores,\
                          primary_antibody,secondary_antibody,image_resolution,cell_detection,registration,\
                          probe_detection,injection_detection,notes]
            exp_insert_dict = {exp_column_names[ii]:exp_insert_row[ii] for ii in range(len(exp_column_names))}
            
            User().insert1(user_insert_dict,skip_duplicates=True)
            Experiment().insert1(exp_insert_dict)

    fill_user_exp_tables()