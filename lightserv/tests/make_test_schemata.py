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
    if 'ahoag_lightsheet_test' in dj.list_schemas():
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
        princeton_email       : varchar(50)
        """
        
    @test_schema
    class Experiment(dj.Manual):
        definition = """ # Experiments performed using the light sheet microscope
        experiment_id                :   smallint auto_increment    # allowed here are sql datatypes.
        ----
        -> User 
        labname                      :   varchar(50)
        correspondence_email = ''    :   varchar(100)
        title                        :   varchar(100)
        description                  :   varchar(250)
        notes = ""                   :   varchar(1000)
        species                      :   varchar(50)
        clearing_protocol            :   enum("iDISCO+_immuno","iDISCO abbreviated clearing","iDISCO abbreviated clearing (rat)","uDISCO","iDISCO_EdU")
        clearing_progress            :   enum("incomplete","in progress","complete")
        antibody1                    :   varchar(100)
        antibody2                    :   varchar(100)
        image_resolution             :   enum("1.3x","4x")
        channel488                   :   enum("","registration","cell_detection","probe_detection","injection_detection")                    
        channel555                   :   enum("","registration","cell_detection","probe_detection","injection_detection")
        channel647                   :   enum("","registration","cell_detection","probe_detection","injection_detection")
        channel790                   :   enum("","registration","cell_detection","probe_detection","injection_detection")
        """  
        
    @test_schema #  
    class Microscope(dj.Manual): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
        definition = """ # Periodic calibration data of the light sheet microscope
        entrynum                :   smallint auto_increment    # allowed here are sql datatypes.
        ----
        -> User              
        date = NULL             :   date    
        old_objective           :   varchar(50)
        new_objective           :   varchar(50)
        swapper                 :   varchar(250)
        calibration =           :   varchar(1000) 
        notes =                 :   varchar(1000)
        """

    @test_schema
    class IdiscoPlusClearing(dj.Manual): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
        definition = """ # Periodic calibration data of the light sheet microscope
        -> Experiment              # experiment_id, the primary key from the Experiment() table
        ----
        -> User                    # username, the researcher's netid from the User() table
        clearer                                                  :   varchar(20)   # the netid of the person who did the clearing
        exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during experiment that could affect clearing
        perfusion_date = NULL                                    :   date 
        time_dehydr_pbs_wash1 = NULL                             :   datetime
        dehydr_pbs_wash1_notes = ""                              :   varchar(250)
        time_dehydr_pbs_wash2 = NULL                             :   datetime
        dehydr_pbs_wash2_notes = ""                              :   varchar(250)
        time_dehydr_pbs_wash3 = NULL                             :   datetime
        dehydr_pbs_wash3_notes = ""                              :   varchar(250)
        time_dehydr_methanol_20percent_wash1 = NULL                 :   datetime
        dehydr_methanol_20percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_40percent_wash1 = NULL                 :   datetime
        dehydr_methanol_40percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_60percent_wash1 = NULL                 :   datetime
        dehydr_methanol_60percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_80percent_wash1 = NULL                 :   datetime
        dehydr_methanol_80percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_100percent_wash1 = NULL                :   datetime
        dehydr_methanol_100percent_wash1_notes = ""                 :   varchar(250)
        time_dehydr_methanol_100percent_wash2 = NULL                :   datetime
        dehydr_methanol_100percent_wash2_notes = ""                 :   varchar(250)
        time_dehydr_h202_wash1 = NULL                            :   datetime
        dehydr_h202_wash1_notes = ""                             :   varchar(250)
        time_rehydr_methanol_100percent_wash1 = NULL                :   datetime
        rehydr_methanol_100percent_wash1_notes = ""                 :   varchar(250)
        time_rehydr_methanol_80percent_wash1 = NULL                 :   datetime
        rehydr_methanol_80percent_wash1_notes = ""                  :   varchar(250)
        time_rehydr_methanol_60percent_wash1 = NULL                 :   datetime
        rehydr_methanol_60percent_wash1_notes = ""                  :   varchar(250)
        time_rehydr_methanol_40percent_wash1 = NULL                 :   datetime
        rehydr_methanol_40percent_wash1_notes = ""                  :   varchar(250)
        time_rehydr_methanol_20percent_wash1 = NULL                 :   datetime
        rehydr_methanol_20percent_wash1_notes = ""                  :   varchar(250)
        time_rehydr_pbs_wash1 = NULL                             :   datetime
        rehydr_pbs_wash1_notes = ""                              :   varchar(250)
        time_rehydr_sodium_azide_wash1 = NULL                    :   datetime
        rehydr_sodium_azide_wash1_notes = ""                     :   varchar(250)
        time_rehydr_sodium_azide_wash2 = NULL                    :   datetime
        rehydr_sodium_azide_wash2_notes = ""                     :   varchar(250)
        time_rehydr_glycine_wash1 = NULL                         :   datetime
        rehydr_glycine_wash1_notes = ""                          :   varchar(250)
        time_blocking_start_roomtemp = NULL                      :   datetime
        blocking_start_roomtemp_notes = ""                       :   varchar(250)
        time_blocking_donkey_serum = NULL                        :   datetime
        blocking_donkey_serum_notes = ""                         :   varchar(250)
        time_antibody1_start_roomtemp = NULL                     :   datetime
        antibody1_start_roomtemp_notes = ""                      :   varchar(250)
        time_antibody1_ptwh_wash1 = NULL                         :   datetime
        antibody1_ptwh_wash1_notes = ""                          :   varchar(250)
        time_antibody1_ptwh_wash2 = NULL                         :   datetime
        antibody1_ptwh_wash2_notes = ""                          :   varchar(250)
        time_antibody1_added = NULL                              :   datetime
        antibody1_added_notes = ""                               :   varchar(250)
        time_wash1_start_roomtemp = NULL                         :   datetime
        wash1_start_roomtemp_notes = ""                          :   varchar(250)
        time_wash1_ptwh_wash1 = NULL                             :   datetime
        wash1_ptwh_wash1_notes = ""                              :   varchar(250)
        time_wash1_ptwh_wash2 = NULL                             :   datetime
        wash1_ptwh_wash2_notes = ""                              :   varchar(250)
        time_wash1_ptwh_wash3 = NULL                             :   datetime
        wash1_ptwh_wash3_notes = ""                              :   varchar(250)
        time_wash1_ptwh_wash4 = NULL                             :   datetime
        wash1_ptwh_wash4_notes = ""                              :   varchar(250)
        time_wash1_ptwh_wash5 = NULL                             :   datetime
        wash1_ptwh_wash5_notes = ""                              :   varchar(250)
        time_antibody2_added = NULL                              :   datetime
        antibody2_added_notes = ""                               :   varchar(250)
        time_wash2_start_roomtemp = NULL                         :   datetime
        wash2_start_roomtemp_notes = ""                          :   varchar(250)
        time_wash2_ptwh_wash1 = NULL                             :   datetime
        wash2_ptwh_wash1_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash2 = NULL                             :   datetime
        wash2_ptwh_wash2_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash3 = NULL                             :   datetime
        wash2_ptwh_wash3_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash4 = NULL                             :   datetime
        wash2_ptwh_wash3_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash5 = NULL                             :   datetime
        wash2_ptwh_wash5_notes = ""                              :   varchar(250)
        time_clearing_methanol_20percent_wash1 = NULL               :   datetime
        clearing_methanol_20percent_wash1_notes = ""                :   varchar(250)
        time_clearing_methanol_40percent_wash1 = NULL               :   datetime
        clearing_methanol_40percent_wash1_notes = ""                :   varchar(250)
        time_clearing_methanol_60percent_wash1 = NULL               :   datetime
        clearing_methanol_60percent_wash1_notes = ""                :   varchar(250)
        time_clearing_methanol_80percent_wash1 = NULL               :   datetime
        clearing_methanol_80percent_wash1_notes = ""                :   varchar(250)
        time_clearing_methanol_100percent_wash1 = NULL              :   datetime
        clearing_methanol_100percent_wash1_notes = ""               :   varchar(250)
        time_clearing_methanol_100percent_wash2 = NULL              :   datetime
        clearing_methanol_100percent_wash2_notes = ""               :   varchar(250)
        time_clearing_dcm_66percent_methanol_33percent = NULL       :   datetime
        clearing_dcm_66percent_methanol_33percent_notes = ""        :   varchar(250)
        time_clearing_dcm_wash1 = NULL                           :   datetime
        clearing_dcm_wash1_notes = ""                            :   varchar(250)
        time_clearing_dcm_wash2 = NULL                           :   datetime
        clearing_dcm_wash2_notes = ""                            :   varchar(250)
        time_clearing_dbe = NULL                                 :   datetime
        clearing_dbe_notes = ""                                  :   varchar(250)
        time_clearing_new_tubes = NULL                           :   datetime
        clearing_new_tubes_notes = ""                            :   varchar(250)
        clearing_notes = ""                                      :   varchar(500)
        """


    @test_schema
    class IdiscoAbbreviatedClearing(dj.Manual): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
        definition = """ # Periodic calibration data of the light sheet microscope
        -> Experiment              # experiment_id, the primary key from the Experiment() table
        ----
        -> User                    # username, the researcher's netid from the User() table
        clearer                                                  :   varchar(20)   # the netid of the person who did the clearing
        exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during experiment that could affect clearing
        perfusion_date = NULL                                    :   date 
        time_pbs_wash1 = NULL                                    :   datetime
        pbs_wash1_notes = ""                                     :   varchar(250)
        time_pbs_wash2 = NULL                                    :   datetime
        pbs_wash2_notes = ""                                     :   varchar(250)
        time_pbs_wash3 = NULL                                    :   datetime
        pbs_wash3_notes = ""                                     :   varchar(250)
        time_dehydr_methanol_20percent_wash1 = NULL                 :   datetime
        dehydr_methanol_20percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_40percent_wash1 = NULL                 :   datetime
        dehydr_methanol_40percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_60percent_wash1 = NULL                 :   datetime
        dehydr_methanol_60percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_80percent_wash1 = NULL                 :   datetime
        dehydr_methanol_80percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_100percent_wash1 = NULL                :   datetime
        dehydr_methanol_100percent_wash1_notes = ""                 :   varchar(250)
        time_dehydr_methanol_100percent_wash2 = NULL                :   datetime
        dehydr_methanol_100percent_wash2_notes = ""                 :   varchar(250)
        time_dehydr_dcm_66percent_methanol_33percent = NULL         :   datetime
        dehydr_dcm_66percent_methanol_33percent_notes = ""          :   varchar(250)
        time_dehydr_dcm_wash1 = NULL                             :   datetime
        dehydr_dcm_wash1_notes = ""                              :   varchar(250)
        time_dehydr_dcm_wash2 = NULL                             :   datetime
        dehydr_dcm_wash2_notes = ""                              :   varchar(250)
        time_dehydr_dbe_wash1 = NULL                             :   datetime
        dehydr_dbe_wash1_notes = ""                              :   varchar(250)
        time_dehydr_dbe_wash2 = NULL                             :   datetime
        dehydr_dbe_wash2_notes = ""                              :   varchar(250)
        clearing_notes = ""                                      :   varchar(500)
        """

    @test_schema
    class IdiscoAbbreviatedRatClearing(dj.Manual): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
        definition = """ # Abbreviated Rat clearing table
        -> Experiment              # experiment_id, the primary key from the Experiment() table
        ----
        -> User                    # username, the researcher's netid from the User() table
        clearer                                                  :   varchar(20)   # the netid of the person who did the clearing
        exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during experiment that could affect clearing
        perfusion_date = NULL                                    :   date 
        time_pbs_wash1 = NULL                                    :   datetime
        pbs_wash1_notes = ""                                     :   varchar(250)
        time_pbs_wash2 = NULL                                    :   datetime
        pbs_wash2_notes = ""                                     :   varchar(250)
        time_pbs_wash3 = NULL                                    :   datetime
        pbs_wash3_notes = ""                                     :   varchar(250)
        time_dehydr_methanol_20percent_wash1 = NULL                 :   datetime
        dehydr_methanol_20percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_20percent_wash2 = NULL                 :   datetime
        dehydr_methanol_20percent_wash2_notes = ""                  :   varchar(250)
        time_dehydr_methanol_40percent_wash1 = NULL                 :   datetime
        dehydr_methanol_40percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_40percent_wash2 = NULL                 :   datetime
        dehydr_methanol_40percent_wash2_notes = ""                  :   varchar(250)
        time_dehydr_methanol_60percent_wash1 = NULL                 :   datetime
        dehydr_methanol_60percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_80percent_wash1 = NULL                 :   datetime
        dehydr_methanol_80percent_wash1_notes = ""                  :   varchar(250)
        time_dehydr_methanol_80percent_wash2 = NULL                 :   datetime
        dehydr_methanol_80percent_wash2_notes = ""                  :   varchar(250)
        time_dehydr_methanol_100percent_wash1 = NULL                :   datetime
        dehydr_methanol_100percent_wash1_notes = ""                 :   varchar(250)
        time_dehydr_methanol_100percent_wash2 = NULL                :   datetime
        dehydr_methanol_100percent_wash2_notes = ""                 :   varchar(250)
        time_dehydr_h202_wash1 = NULL                            :   datetime
        dehydr_h202_wash1_notes = ""                             :   varchar(250)
        time_dehydr_methanol_100percent_wash3 = NULL                :   datetime
        dehydr_methanol_100percent_wash3_notes = ""                 :   varchar(250)
        time_dehydr_methanol_100percent_wash4 = NULL                :   datetime
        dehydr_methanol_100percent_wash4_notes = ""                 :   varchar(250)
        time_dehydr_methanol_100percent_wash5 = NULL                :   datetime
        dehydr_methanol_100percent_wash5_notes = ""                 :   varchar(250)
        time_dehydr_dcm_66percent_methanol_33percent = NULL         :   datetime
        dehydr_dcm_66percent_methanol_33percent_notes = ""          :   varchar(250)
        time_dehydr_dcm_wash1 = NULL                             :   datetime
        dehydr_dcm_wash1_notes = ""                              :   varchar(250)
        time_dehydr_dcm_wash2 = NULL                             :   datetime
        dehydr_dcm_wash2_notes = ""                              :   varchar(250)
        time_dehydr_dbe_wash1 = NULL                             :   datetime
        dehydr_dbe_wash1_notes = ""                              :   varchar(250)
        time_dehydr_dbe_wash2 = NULL                             :   datetime
        dehydr_dbe_wash2_notes = ""                              :   varchar(250)
        clearing_notes = ""                                      : varchar(500)
        """

    @test_schema
    class UdiscoClearing(dj.Manual): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
        definition = """ # uDISCO clearing table
        -> Experiment              # experiment_id, the primary key from the Experiment() table
        ----
        -> User                    # username, the researcher's netid from the User() table
        clearer                                                  :   varchar(20)   # the netid of the person who did the clearing
        exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during experiment that could affect clearing
        perfusion_date = NULL                                    :   date 
        time_dehydr_pbs_wash1 = NULL                             :   datetime
        dehydr_pbs_wash1_notes = ""                              :   varchar(250)
        time_dehydr_butanol_30percent = NULL                     :   datetime
        dehydr_butanol_30percent_notes = ""                      :   varchar(250)
        time_dehydr_butanol_50percent = NULL                     :   datetime
        dehydr_butanol_50percent_notes = ""                      :   varchar(250)
        time_dehydr_butanol_70percent = NULL                     :   datetime
        dehydr_butanol_70percent_notes = ""                      :   varchar(250)
        time_dehydr_butanol_80percent = NULL                     :   datetime
        dehydr_butanol_80percent_notes = ""                      :   varchar(250)
        time_dehydr_butanol_90percent = NULL                     :   datetime
        dehydr_butanol_90percent_notes = ""                      :   varchar(250)
        time_dehydr_butanol_96percent = NULL                     :   datetime
        dehydr_butanol_96percent_notes = ""                      :   varchar(250)
        time_dehydr_butanol_100percent = NULL                    :   datetime
        dehydr_butanol_100percent_notes = ""                     :   varchar(250)
        time_clearing_dcm_wash1 = NULL                           :   datetime
        clearing_dcm_wash1_notes = ""                            :   varchar(250)
        time_clearing_babb_wash1 = NULL                          :   datetime
        clearing_babb_wash1_notes = ""                           :   varchar(250)
        clearing_notes = ""                                      : varchar(500)
        """

    with open(experiment_test_data_file,'rb') as f:
        experiment_test_data = pickle.load(f)

    labname_dict = {'tomohito':'falkner','jverpeut':'wang',
    'soline':'falkner','marlies.oostland':'wang','zmd':'wang',
    'ejdennis':'brody','willmore':'witten','apv2':'witten',
    'mioffe':'tank','pbibawi':'brody','rmallarino':'mallarino',
    'zhihaoz':'tank'}    
    def fill_user_exp_tables():
        """ Fills the User() and Experiment() tables 
        using the form response data from the tab in the clearing google spreadsheet
        """
        exp_column_names = ['username','labname','species','clearing_protocol',
                            'clearing_progress','title','description',
                            'antibody1','antibody2','image_resolution',
                            'channel488','channel555','channel647',
                            'channel790','notes'] # order doesn't matter since we will be using these in a dictionary
        for form_response in experiment_test_data:
            # ignore blank lines
            if not form_response:
                continue
            assert len(form_response) == 15
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
            # fluorophores = form_response[4]
            antibody1 = form_response[6]
            antibody2 = form_response[7]
            imaging_str = form_response[8]
            image_resolution = "1.3x" if "1.3x" in imaging_str else "4x"
            processing_str = form_response[9]
            processing_list = [x.lower() for x in processing_str.split(',')]
           
            channel488 = ''
            channel555 = ''
            channel647 = ''
            channel790 = ''
            for item in processing_list:
                if 'cell detection' in item:
                    channel488 = 'cell_detection'
                if 'registration' in item:
                    channel647 = 'registration'
                if 'probe' in item and 'detection' in item:
                    channel555 = 'probe_detection'
                if 'injection' in item and 'detection' in item:
                    channel790 = 'injection_detection'
            notes = form_response[11]
            email = form_response[14]
            username = email.split('@')[0].lower() if 'princeton' in email else 'zmd' # zahra is the only one who used her gmail
            labname = labname_dict[username]
            user_insert_dict = {'username':username,'princeton_email':email}
            
            exp_insert_row = [username,labname,species,clearing_protocol,clearing_progress,
                              title,description,antibody1,antibody2,image_resolution,
                              channel488,channel555,channel647,channel790,notes]
            exp_insert_dict = {exp_column_names[ii]:exp_insert_row[ii] for ii in range(len(exp_column_names))}
            # print(exp_insert_dict)
            User().insert1(user_insert_dict,skip_duplicates=True)
            Experiment().insert1(exp_insert_dict)

    fill_user_exp_tables()
    return test_schema