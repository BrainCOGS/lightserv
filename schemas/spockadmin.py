import datajoint as dj
import os

if os.environ.get('FLASK_MODE') == 'TEST':
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306
    dj.config['database.user'] = os.environ['DJ_DB_TEST_USER']
    dj.config['database.password'] = os.environ['DJ_DB_TEST_PASS']
    print("setting up test spockadmin schema")
    schema = dj.schema('ahoag_spockadmin_test')
    # is_worker = os.environ.get('IS_WORKER')
    # if is_worker is not None:
    #     print("Worker; not dropping db")
    # else:    
    #     schema.drop(force=True)
    #     schema = dj.schema('ahoag_admin_test')
else:
    dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
    dj.config['database.port'] = 3306
    dj.config['database.user'] = os.environ['DJ_DB_USER']
    dj.config['database.password'] = os.environ['DJ_DB_PASS']
    print("setting up real spockadmin schema")
    schema = dj.schema('ahoag_spockadmin_demo')

@schema 
class ProcessingPipelineSpockJob(dj.Manual):
    definition = """    # Spock job management table for the entire light sheet pipeline
    jobid_step3                   : varchar(16) # the jobid on spock for the final step in the pipeline. Status column refers to this jobid
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---    
    username                      : varchar(32)
    stitching_method              : enum("terastitcher","blending") # to keep track of whether terastitcher was run on tiled data
    jobid_step0                   : varchar(16)
    jobid_step1                   : varchar(16)
    jobid_step2                   : varchar(16)
    status_step0                  : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED") # of jobid_step3
    status_step1                  : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED") # of jobid_step3
    status_step2                  : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED") # of jobid_step3
    status_step3                  : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED") # of jobid_step3
    """

@schema 
class RawPrecomputedSpockJob(dj.Manual):
    definition = """    # Spock job management table for precomputed jobs
    jobid_step2  : varchar(16) # the jobid on spock of step2 (downsampling) in the precomputed pipeline. Used as primary key so that the progress of the precomputed pipeline can be probed.
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---
    lightsheet   : varchar(8) 
    jobid_step0  : varchar(16)
    jobid_step1  : varchar(16)
    username     : varchar(32)
    status_step0 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED")
    status_step1 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED")
    status_step2 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED")
    """

@schema 
class TiledPrecomputedSpockJob(dj.Manual):
    definition = """    # Spock job management table for keeping track of spock jobs for making precomputed data from the stitched multi-tile data
    jobid_step2  : varchar(16) # the jobid on spock of step2 (downsampling) in the precomputed pipeline. Used as primary key so that the progress of the precomputed pipeline can be probed.
    timestamp = CURRENT_TIMESTAMP : timestamp
    ---
    -> ProcessingPipelineSpockJob.proj(processing_pipeline_jobid_step3='jobid_step3')
    lightsheet   : varchar(8) 
    jobid_step0  : varchar(16)
    jobid_step1  : varchar(16)
    username     : varchar(32)
    status_step0 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED")
    status_step1 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED")
    status_step2 : enum("SUBMITTED","COMPLETED","FAILED","RUNNING","PENDING","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REQUEUED"," RESIZING","REVOKED","SUSPENDED")
    """
