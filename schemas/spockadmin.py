import datajoint as dj
import os

if os.environ.get('FLASK_MODE') == 'TEST':
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306
    dj.config['database.user'] = os.environ['DJ_DB_TEST_USER']
    dj.config['database.password'] = os.environ['DJ_DB_TEST_PASS']
    print("setting up test spockadmin schema")
    schema = dj.schema('ahoag_spockadmin_test')
elif os.environ.get('FLASK_MODE') == 'DEV':
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306
    dj.config['database.user'] = os.environ['DJ_DB_USER']
    dj.config['database.password'] = os.environ['DJ_DB_PASS']
    print("setting up DEV: ahoag_spockadmin_demo schema")
    schema = dj.schema('ahoag_spockadmin_demo')
elif os.environ.get('FLASK_MODE') == 'PROD':
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306
    dj.config['database.user'] = os.environ['DJ_DB_USER']
    dj.config['database.password'] = os.environ['DJ_DB_PASS']
    print("setting up PROD: u19lightserv_appcore schema")
    schema = dj.schema('u19lightserv_appcore')

@schema 
class ProcessingPipelineSpockJob(dj.Manual):
    definition = """    # Spock job management table for the entire light sheet pipeline
    jobid_step0                   : varchar(16) # the jobid on spock for the first step in the pipeline.
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---    
    username                      : varchar(32)
    stitching_method              : enum("terastitcher","blending") # to keep track of whether terastitcher was run on tiled data
    jobid_step1                   : varchar(16)
    jobid_step2                   : varchar(16)
    jobid_step3 = NULL            : varchar(16) # nullable because we dont always run step 3, e.g. if no registration is needed
    status_step0                  : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT") # 
    status_step1                  : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT") # 
    status_step2                  : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT") # 
    status_step3 = NULL           : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT") # nullable because we dont always run step 3, e.g. if no registration is needed
    """

@schema 
class SmartspimStitchingSpockJob(dj.Manual):
    definition = """    # Spock job management table for the entire light sheet pipeline
    jobid_step0                   : varchar(16) # the jobid on spock for the first step in the pipeline.
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---    
    username                      : varchar(32)
    jobid_step1                   : varchar(16)
    jobid_step2                   : varchar(16)
    jobid_step3 = NULL            : varchar(16) # nullable because we dont always run step 3, e.g. if no registration is needed
    status_step0                  : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT") # 
    status_step1                  : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT") # 
    status_step2                  : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT") # 
    status_step3 = NULL           : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT") # nullable because we dont always run step 3, e.g. if no registration is needed
    """

@schema 
class SmartspimPystripeSpockJob(dj.Manual):
    definition = """    # Spock job management table for the entire light sheet pipeline
    jobid_step0                   : varchar(16) # the jobid on spock for the first step in the pipeline.
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---    
    username                      : varchar(32)
    status_step0                  : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT") # 
    """

@schema 
class RawPrecomputedSpockJob(dj.Manual):
    definition = """    # Spock job management table for precomputed jobs
    jobid_step2  : varchar(16) # the jobid on spock of step2 (downsampling) in the precomputed pipeline. Used as primary key so that the progress of the precomputed pipeline can be probed.
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---
    lightsheet   : varchar(8) # left or right
    jobid_step0  : varchar(16)
    jobid_step1  : varchar(16)
    username     : varchar(32)
    status_step0 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    status_step1 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    status_step2 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    """

@schema 
class StitchedPrecomputedSpockJob(dj.Manual):
    definition = """    # Spock job management table for keeping track of spock jobs for making precomputed data from the stitched multi-tile data
    jobid_step2  : varchar(16) # the jobid on spock of step2 (downsampling) in the precomputed pipeline. Used as primary key so that the progress of the precomputed pipeline can be probed.
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---
    processing_pipeline_jobid_step0 : varchar(16) 
    lightsheet   : varchar(8) # left or right
    jobid_step0  : varchar(16)
    jobid_step1  : varchar(16)
    username     : varchar(32)
    status_step0 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    status_step1 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    status_step2 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    """

@schema 
class BlendedPrecomputedSpockJob(dj.Manual):
    definition = """    # Spock job management table for keeping track of spock jobs for making precomputed data from the blended data products 
    jobid_step2  : varchar(16) # the jobid on spock of step2 (downsampling) in the precomputed pipeline. Used as primary key so that the progress of the precomputed pipeline can be probed.
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---
    processing_pipeline_jobid_step0 : varchar(16) 
    jobid_step0  : varchar(16)
    jobid_step1  : varchar(16)
    username     : varchar(32)
    status_step0 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    status_step1 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    status_step2 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    """
@schema 
class DownsizedPrecomputedSpockJob(dj.Manual):
    definition = """    # Spock job management table for keeping track of spock jobs for making precomputed data from the blended data products 
    jobid_step1  : varchar(16) # the jobid on spock of step1 (volume uploading) in the precomputed pipeline. Used as primary key so that the progress of the precomputed pipeline can be probed.
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---
    processing_pipeline_jobid_step0 : varchar(16) 
    jobid_step0  : varchar(16)
    username     : varchar(32)
    status_step0 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    status_step1 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    """

@schema 
class RegisteredPrecomputedSpockJob(dj.Manual):
    definition = """    # Spock job management table for keeping track of spock jobs for making precomputed data from the blended data products 
    jobid_step1  : varchar(16) # the jobid on spock of step1 (volume uploading) in the precomputed pipeline. Used as primary key so that the progress of the precomputed pipeline can be probed.
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---
    processing_pipeline_jobid_step0 : varchar(16) 
    jobid_step0  : varchar(16)
    username     : varchar(32)
    status_step0 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    status_step1 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    """

@schema 
class SmartspimCorrectedPrecomputedSpockJob(dj.Manual):
    definition = """    # Spock job management table for keeping track of spock jobs for making precomputed data from the stitched multi-tile data
    jobid_step3  : varchar(16) # the jobid on spock of step3 (downsampling) in the precomputed pipeline. Used as primary key so that the progress of the precomputed pipeline can be probed.
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---
    username     : varchar(32)
    jobid_step0  : varchar(16)
    jobid_step1  : varchar(16)
    jobid_step2  : varchar(16) # the jobid on spock of step2 (downsampling) in the precomputed pipeline. Used as primary key so that the progress of the precomputed pipeline can be probed.
    status_step0 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    status_step1 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    status_step2 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    status_step3 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED","TIMEOUT")
    """

@schema 
class BucketStorage(dj.Lookup):
    definition = """    # Keep track of storage space on LightSheetData bucket
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---    
    size_tb                       : float
    avail_tb                      : float
    """
    contents = [
        ['2021-05-03 08:30:00',150,5.783],
        ['2021-05-02 08:30:00',150,6.666],
        ['2021-05-01 08:30:00',150,8.056],
        ['2021-04-30 08:30:00',150,10.650],
        ['2021-04-29 08:30:00',150,11.767],
        ['2021-04-28 08:30:00',150,12.914],
        ['2021-04-27 08:30:00',150,14.961],
        ['2021-04-26 08:30:00',150,15.187],
        ['2021-04-25 08:30:00',150,18.544],
        ['2021-04-24 08:30:00',150,20.842],
        ['2021-04-23 08:30:00',150,22.806],
        ['2021-04-22 08:30:00',150,26.779],
        ['2021-04-21 08:30:00',150,26.771],
        ['2021-04-20 08:30:00',150,24.807],
        ['2021-04-19 08:30:00',125,0.012],
        ['2021-04-18 08:30:00',125,1.147],
        ['2021-04-17 08:30:00',125,2.360],
        ['2021-04-16 08:30:00',125,1.001],
        ['2021-04-15 08:30:00',125,3.049],
        ['2021-04-14 08:30:00',125,3.367],
        ['2021-04-13 08:30:00',125,4.983],

    ]