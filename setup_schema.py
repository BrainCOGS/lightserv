# import datajoint as dj
import os 
import datajoint as dj

os.environ['FLASK_MODE'] = 'PROD'

dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
dj.config['database.port'] = 3306

dj.config['database.user'] = os.environ['DJ_DB_USER']
dj.config['database.password'] = os.environ['DJ_DB_PASS']

spockadmin_schema = dj.schema('u19lightserv_appcore')
lightsheet_schema = dj.schema('u19lightserv_lightsheet')
# admin_schema = dj.schema('u19lightserv_appcore')
# microscope_schema = dj.schema('ahoag_microscope_demo')

from schemas import spockadmin 
from schemas import lightsheet 
from schemas import admin	
