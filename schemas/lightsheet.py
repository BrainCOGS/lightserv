import datajoint as dj
import os

if os.environ.get('FLASK_MODE') == 'TEST':
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306

    dj.config['database.user'] = os.environ['DJ_DB_TEST_USER']
    dj.config['database.password'] = os.environ['DJ_DB_TEST_PASS']
    print("setting up test light sheet schema")
    schema = dj.schema('ahoag_lightsheet_test')
    
elif os.environ.get('FLASK_MODE') == 'DEV':
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306

    dj.config['database.user'] = os.environ['DJ_DB_USER']
    dj.config['database.password'] = os.environ['DJ_DB_PASS']
    print("setting up DEV: ahoag_lightsheet_demo schema")

    schema = dj.schema('ahoag_lightsheet_demo')
elif os.environ.get('FLASK_MODE') == 'PROD':
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306
    dj.config['database.user'] = os.environ['DJ_DB_USER']
    dj.config['database.password'] = os.environ['DJ_DB_PASS']
    print("setting up PROD: u19lightserv_lightsheet schema")
    schema = dj.schema('u19lightserv_lightsheet')

# from . import spockadmin

@schema
class User(dj.Lookup):
    definition = """
    # Users of the light sheet microscope
    username : varchar(20)      # user in the lab
    ---
    princeton_email       : varchar(50)
    """
    
@schema
class Request(dj.Manual):
    definition = """ # The highest level table for handling user requests to the Core Facility 
    -> User  
    request_name                    :   varchar(64)
    ----
    -> User.proj(requested_by='username') # defines a new column here called "requested_by" whose value must be one of the "username" entries in the User() table    
    date_submitted                  :   date     # The date it was submitted as a request
    time_submitted                  :   time     # The time it was submitted as a request
    labname                         :   varchar(50)
    correspondence_email = ''       :   varchar(100)
    description                     :   varchar(250)
    species                         :   varchar(50)
    number_of_samples               :   tinyint
    testing = 0                     :   boolean
    is_archival = 0                 :   boolean
    raw_data_retention_preference = NULL  :   enum("important","kind of important","not important","not sure")
    """  

    class ClearingBatch(dj.Part):
        definition = """ # Samples from a particular request
        -> Request
        clearing_protocol            :   enum("iDISCO+_immuno","iDISCO abbreviated clearing","iDISCO abbreviated clearing (rat)","uDISCO","uDISCO (rat)","iDISCO_EdU","experimental")
        antibody1 = ''               :   varchar(100)
        antibody2 = ''               :   varchar(100)
        clearing_batch_number        :   tinyint
        ----
        antibody1_lot = NULL         :   varchar(64)
        antibody2_lot = NULL         :   varchar(64)
        clearing_progress            :   enum("incomplete","in progress","complete")
        number_in_batch              :   tinyint
        perfusion_date = NULL        :   date
        expected_handoff_date = NULL :   date
        -> [nullable] User.proj(clearer='username') # defines a new column here called "clearer" whose value must be either None or one of the "username" entries in the User() table
        notes_for_clearer = ""       :   varchar(8192)                
        link_to_clearing_spreadsheet = NULL : varchar(256)
        """  

    class ImagingBatch(dj.Part):
        definition = """ # Batch of Samples to image the same way
        -> Request
        imaging_batch_number                      :   tinyint
        imaging_request_number                    :   tinyint
        ----
        -> [nullable] User.proj(imager='username') # defines a new column here called "imager" whose value must be one of the "username" entries in the User() table
        number_in_imaging_batch                   :   tinyint # date that the imaging form was submitted by the imager
        imaging_request_date_submitted            :   date # date that the user submitted the request for imaging
        imaging_request_time_submitted            :   time # time that the user submitted the request for imaging
        imaging_performed_date = NULL             :   date # date that the imaging form was submitted by the imager
        imaging_progress                          :   enum("incomplete","in progress","complete")
        imaging_dict                              :   blob
        """

    class Sample(dj.Part):
        definition = """ # Samples from a request, belonging to a clearing batch or imaging batch
        -> Request
        sample_name                  :   varchar(64)                
        ----
        -> master.ClearingBatch
        -> master.ImagingBatch
        subject_fullname = NULL      :   varchar(64)
        """ 

    class ImagingRequest(dj.Part):
        definition = """ # Imaging request
        -> master.Sample
        imaging_request_number                    :   tinyint
        ----
        -> [nullable] User.proj(imager='username') # defines a new column here called "imager" whose value must be one of the "username" entries in the User() table
        imaging_request_date_submitted            :   date # date that the user submitted the request for imaging
        imaging_request_time_submitted            :   time # time that the user submitted the request for imaging
        imaging_performed_date = NULL             :   date # date that the imaging form was submitted by the imager
        imaging_progress                          :   enum("incomplete","in progress","complete")
        """

    class ImagingResolutionRequest(dj.Part):
        definition = """ # Imaging parameters for a channel, belonging to a sample
        -> master.ImagingRequest
        image_resolution                          :   enum("1.3x","4x","1.1x","2x","3.6x")
        ----        
        microscope = NULL                         :   enum("LaVision","SmartSPIM")
        notes_for_imager = ""                     :   varchar(1024)
        notes_from_imaging = ""                   :   varchar(1024)
        """
    class ImagingChannel(dj.Part):
        definition = """ # Imaging parameters for a channel, belonging to a sample
        -> master.ImagingResolutionRequest
        channel_name                                            :   varchar(64)                
        ventral_up = 0                                          :   boolean # whether brain was flipped upside down to be imaged
        ----
        imaging_date = NULL                                     :   date 
        zoom_body_magnification = NULL                          :   float # only applicable for 2x
        left_lightsheet_used = 1                                :   boolean
        right_lightsheet_used = 1                               :   boolean
        registration = 0                                        :   boolean
        injection_detection = 0                                 :   boolean
        probe_detection = 0                                     :   boolean
        cell_detection = 0                                      :   boolean
        generic_imaging = 0                                     :   boolean
        pixel_type = NULL                                       :   varchar(32)
        image_orientation                                       :   enum("sagittal","coronal","horizontal") # how the imager imaged the sample. Most of the time will be horizontal
        numerical_aperture = NULL                               :   float # it is not always recorded in metadata so those times it will be NULL
        tiling_scheme = '1x1'                                   :   char(3)
        tiling_overlap = 0.0                                    :   float
        z_step = 10                                             :   float # distance between z planes in microns
        number_of_z_planes = NULL                               :   smallint unsigned
        rawdata_subfolder = NULL                                :   varchar(512)
        imspector_channel_index = NULL                          :   tinyint    # refers to multi-channel imaging - 0 if first (or only) channel in rawdata_subfolder, 1 if second, 2 if third, ...
        left_lightsheet_precomputed_spock_jobid = NULL          :   varchar(32)
        left_lightsheet_precomputed_spock_job_progress = NULL   :   enum("NOT_SUBMITTED","SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
        right_lightsheet_precomputed_spock_jobid = NULL         :   varchar(32)
        right_lightsheet_precomputed_spock_job_progress = NULL  :   enum("NOT_SUBMITTED","SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
        """

   
    class ProcessingRequest(dj.Part):
        definition = """ # Processing request - this needs to exist because for each imaging request there can be multiple processing requests 
        -> master.ImagingRequest
        processing_request_number                    :   tinyint
        ----
        -> [nullable] User.proj(processor='username') # defines column "processor" whose value must be one of the "username" entries in the User() table
        processing_request_date_submitted            :   date # date that the user submitted the request for processing
        processing_request_time_submitted            :   time # time that the user submitted the request for processing
        processing_performed_date = NULL             :   date # date that the processing form was submitted by the processor
        processing_progress                          :   enum("incomplete","running","failed", "complete")
        """

    class ProcessingResolutionRequest(dj.Part):
        definition = """ # Processing parameters at the image resolution level for a given ProcessingRequest(). These represent spock jobs
        -> master.ProcessingRequest
        image_resolution                          :   enum("1.3x","4x","1.1x","2x","3.6x")
        ventral_up = 0                            :   boolean # whether brain was flipped upside down to be imaged
        ----        
        atlas_name                                :   enum("allen_2017","allen_2011","princeton_mouse_atlas","paxinos")
        final_orientation                         :   enum("sagittal","coronal","horizontal")
        notes_for_processor = ""                  :   varchar(1024)
        notes_from_processing = ""                :   varchar(1024) 
        lightsheet_pipeline_spock_jobid = NULL            :   varchar(16)  # the jobid from the final step in the light sheet processing pipeline for LaVision
        lightsheet_pipeline_spock_job_progress = NULL     :   enum("NOT_SUBMITTED","SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT") # the spock job status code for the final step in the light sheet processing pipeline
        brainpipe_commit = NULL                   : char(7) # the commit that is checked out on the machine at the time the job was submitted 
        """

    class ProcessingChannel(dj.Part):
        definition = """ # Processing parameters for a channel. There can be more than one purpose for a single channel, hence why lightsheet_channel_str is a primary key
        -> master.ImagingChannel
        -> master.ProcessingResolutionRequest
        lightsheet_channel_str                                        :   enum("regch","injch","cellch","gench")
        ----
        imspector_version = ''                                        :   varchar(128)
        datetime_processing_started                                   :   datetime
        datetime_processing_completed = NULL                          :   datetime
        intensity_correction = 1                                      :   boolean
        metadata_xml_string = NULL                                    :   mediumblob # The entire metadata xml string. Sometimes it is not available so those times it will be NULL
        left_lightsheet_stitched_precomputed_spock_jobid = NULL          :   varchar(32)
        left_lightsheet_stitched_precomputed_spock_job_progress = NULL   :   enum("NOT_SUBMITTED","SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
        right_lightsheet_stitched_precomputed_spock_jobid = NULL         :   varchar(32)
        right_lightsheet_stitched_precomputed_spock_job_progress = NULL  :   enum("NOT_SUBMITTED","SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
        blended_precomputed_spock_jobid = NULL                        : varchar(32)
        blended_precomputed_spock_job_progress = NULL                 : enum("NOT_SUBMITTED","SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
        downsized_precomputed_spock_jobid = NULL                      : varchar(32)
        downsized_precomputed_spock_job_progress = NULL               : enum("NOT_SUBMITTED","SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
        registered_precomputed_spock_jobid = NULL                     : varchar(32)
        registered_precomputed_spock_job_progress = NULL              : enum("NOT_SUBMITTED","SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
        """
    
    class SmartspimStitchedChannel(dj.Part):
        definition = """ # Processing parameters for a channel. There can be more than one purpose for a single channel, hence why lightsheet_channel_str is a primary key
        -> master.ImagingChannel
        -> master.ProcessingResolutionRequest
        ----
        datetime_stitching_started                                    :   datetime
        datetime_stitching_completed = NULL                           :   datetime
        smartspim_stitching_spock_jobid = NULL                        :   varchar(16)  # the jobid from the final stitching step for SmartSPIM
        smartspim_stitching_spock_job_progress = NULL                 :   enum("NOT_SUBMITTED","SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT") # the spock job status code for the final step in the light sheet processing pipeline
        brainpipe_commit = NULL                                       :   char(7) # the commit that is checked out on the machine at the time the job was submitted 
        """  
                
    class IdiscoPlusClearing(dj.Part): # 
        definition = """ # iDISCO+ clearing table
        -> master.ClearingBatch           
        ----
        exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during request handling that could affect clearing
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
        time_dehydr_peroxide_wash1 = NULL                            :   datetime
        dehydr_peroxide_wash1_notes = ""                             :   varchar(250)
        
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
        antibody1_lot = ""                                       :   varchar(64)
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
        time_wash1_ptwh_wash6 = NULL                             :   datetime
        wash1_ptwh_wash6_notes = ""                              :   varchar(250)
        time_antibody2_added = NULL                              :   datetime
        antibody2_added_notes = ""                               :   varchar(250)
        antibody2_lot = ""                                       :   varchar(64)
        time_wash2_start_roomtemp = NULL                         :   datetime
        wash2_start_roomtemp_notes = ""                          :   varchar(250)
        time_wash2_ptwh_wash1 = NULL                             :   datetime
        wash2_ptwh_wash1_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash2 = NULL                             :   datetime
        wash2_ptwh_wash2_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash3 = NULL                             :   datetime
        wash2_ptwh_wash3_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash4 = NULL                             :   datetime
        wash2_ptwh_wash4_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash5 = NULL                             :   datetime
        wash2_ptwh_wash5_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash6 = NULL                             :   datetime
        wash2_ptwh_wash6_notes = ""                              :   varchar(250)
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

    class IdiscoAbbreviatedClearing(dj.Part): 
        definition = """ # iDISCO abbreviated clearing table
        -> master.ClearingBatch           
        ----
        exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during request handling that could affect clearing
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

    class IdiscoAbbreviatedRatClearing(dj.Part): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
        definition = """ # iDISCO Abbreviated Rat clearing table
        -> master.ClearingBatch              
        ----
        exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during request that could affect clearing
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
        time_dehydr_peroxide_wash1 = NULL                            :   datetime
        dehydr_peroxide_wash1_notes = ""                             :   varchar(250)
        time_dehydr_methanol_100percent_wash2 = NULL                :   datetime
        dehydr_methanol_100percent_wash2_notes = ""                 :   varchar(250)
        time_dehydr_dcm_66percent_methanol_33percent = NULL         :   datetime
        dehydr_dcm_66percent_methanol_33percent_notes = ""          :   varchar(250)
        time_dehydr_dcm_wash1 = NULL                             :   datetime
        dehydr_dcm_wash1_notes = ""                              :   varchar(250)
        time_dehydr_dbe_wash1 = NULL                             :   datetime
        dehydr_dbe_wash1_notes = ""                              :   varchar(250)
        time_dehydr_dbe_wash2 = NULL                             :   datetime
        dehydr_dbe_wash2_notes = ""                              :   varchar(250)
        clearing_notes = ""                                      : varchar(500)
        """

    class UdiscoClearing(dj.Part): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
        definition = """ # uDISCO clearing table
        -> master.ClearingBatch              
        ----
        exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during request that could affect clearing
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
        clearing_notes = ""                                      :   varchar(500)
        """

    class UdiscoRatClearing(dj.Part): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
        definition = """ # uDISCO clearing table
        -> master.ClearingBatch              
        ----
        exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during request that could affect clearing
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
        clearing_notes = ""                                      :   varchar(500)
        """

    class IdiscoEdUClearing(dj.Part): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
        definition = """ # uDISCO clearing table
        -> master.ClearingBatch              
        ----
        exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during request that could affect clearing
        time_dehydr_pbs_wash1 = NULL                             :   datetime
        dehydr_pbs_wash1_notes = ""                              :   varchar(250)
        time_dehydr_pbs_wash2 = NULL                             :   datetime
        dehydr_pbs_wash2_notes = ""                              :   varchar(250)
        time_dehydr_pbs_wash3 = NULL                             :   datetime
        dehydr_pbs_wash3_notes = ""                              :   varchar(250)

        time_dehydr_methanol_20percent_wash1 = NULL              :   datetime
        dehydr_methanol_20percent_wash1_notes = ""               :   varchar(250)
        time_dehydr_methanol_40percent_wash1 = NULL              :   datetime
        dehydr_methanol_40percent_wash1_notes = ""               :   varchar(250)
        time_dehydr_methanol_60percent_wash1 = NULL              :   datetime
        dehydr_methanol_60percent_wash1_notes = ""               :   varchar(250)
        time_dehydr_methanol_80percent_wash1 = NULL              :   datetime
        dehydr_methanol_80percent_wash1_notes = ""               :   varchar(250)
        time_dehydr_methanol_100percent_wash1 = NULL             :   datetime
        dehydr_methanol_100percent_wash1_notes = ""              :   varchar(250)
        time_dehydr_methanol_100percent_wash2 = NULL             :   datetime
        dehydr_methanol_100percent_wash2_notes = ""              :   varchar(250)
        
        time_dehydr_peroxide_wash1 = NULL                            :   datetime
        dehydr_peroxide_wash1_notes = ""                             :   varchar(250)
        time_rehydr_methanol_100percent_wash1 = NULL             :   datetime
        rehydr_methanol_100percent_wash1_notes = ""              :   varchar(250)
        time_rehydr_methanol_80percent_wash1 = NULL              :   datetime
        rehydr_methanol_80percent_wash1_notes = ""               :   varchar(250)
        time_rehydr_methanol_60percent_wash1 = NULL              :   datetime
        rehydr_methanol_60percent_wash1_notes = ""               :   varchar(250)
        time_rehydr_methanol_40percent_wash1 = NULL              :   datetime
        rehydr_methanol_40percent_wash1_notes = ""               :   varchar(250)
        time_rehydr_methanol_20percent_wash1 = NULL              :   datetime
        rehydr_methanol_20percent_wash1_notes = ""               :   varchar(250)
        
        time_rehydr_pbs_wash1 = NULL                             :   datetime
        rehydr_pbs_wash1_notes = ""                              :   varchar(250)
        time_rehydr_sodium_azide_wash1 = NULL                    :   datetime
        rehydr_sodium_azide_wash1_notes = ""                     :   varchar(250)
        time_rehydr_sodium_azide_wash2 = NULL                    :   datetime
        rehydr_sodium_azide_wash2_notes = ""                     :   varchar(250)
        time_rehydr_glycine_wash1 = NULL                         :   datetime
        rehydr_glycine_wash1_notes = ""                          :   varchar(250)
        
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

        time_edu_click_chemistry = NULL                          :   datetime
        edu_click_chemistry_notes = ""                           :   varchar(250)

        time_wash2_ptwh_wash1 = NULL                             :   datetime
        wash2_ptwh_wash1_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash2 = NULL                             :   datetime
        wash2_ptwh_wash2_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash3 = NULL                             :   datetime
        wash2_ptwh_wash3_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash4 = NULL                             :   datetime
        wash2_ptwh_wash4_notes = ""                              :   varchar(250)
        time_wash2_ptwh_wash5 = NULL                             :   datetime
        wash2_ptwh_wash5_notes = ""                              :   varchar(250)
        
        time_clearing_methanol_20percent_wash1 = NULL            :   datetime
        clearing_methanol_20percent_wash1_notes = ""             :   varchar(250)
        time_clearing_methanol_40percent_wash1 = NULL            :   datetime
        clearing_methanol_40percent_wash1_notes = ""             :   varchar(250)
        time_clearing_methanol_60percent_wash1 = NULL            :   datetime
        clearing_methanol_60percent_wash1_notes = ""             :   varchar(250)
        time_clearing_methanol_80percent_wash1 = NULL            :   datetime
        clearing_methanol_80percent_wash1_notes = ""             :   varchar(250)
        time_clearing_methanol_100percent_wash1 = NULL           :   datetime
        clearing_methanol_100percent_wash1_notes = ""            :   varchar(250)
        time_clearing_methanol_100percent_wash2 = NULL           :   datetime
        clearing_methanol_100percent_wash2_notes = ""            :   varchar(250)
        time_clearing_dcm_66percent_methanol_33percent = NULL    :   datetime
        clearing_dcm_66percent_methanol_33percent_notes = ""     :   varchar(250)
        time_clearing_dcm_wash1 = NULL                           :   datetime
        clearing_dcm_wash1_notes = ""                            :   varchar(250)
        time_clearing_dcm_wash2 = NULL                           :   datetime
        clearing_dcm_wash2_notes = ""                            :   varchar(250)
        time_clearing_dbe = NULL                                 :   datetime
        clearing_dbe_notes = ""                                  :   varchar(250)
        time_clearing_new_tubes = NULL                           :   datetime
        clearing_new_tubes_notes = ""                            :   varchar(250)
        clearing_notes = ""                                      : varchar(500)
        """

    class ExperimentalClearing(dj.Part): 
        definition = """ # Experimental clearing table
        -> master.ClearingBatch              
        ----
        link_to_clearing_spreadsheet = NULL : varchar(256)
        """
