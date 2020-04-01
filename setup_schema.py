# import datajoint as dj
import os 
import datajoint as dj
dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
dj.config['database.port'] = 3306

dj.config['database.user'] = os.environ['DJ_DB_USER']
dj.config['database.password'] = os.environ['DJ_DB_PASS']
# dj.config['database.host'] = '127.0.0.1'
# dj.config['database.port'] = 3306

# dj.config['database.user'] = 'ahoag'
# dj.config['database.password'] = 'p@sswd'
os.environ['FLASK_MODE'] = 'DEV'

spockadmin_schema = dj.schema('ahoag_spockadmin_demo')
lightsheet_schema = dj.schema('ahoag_lightsheet_demo')
admin_schema = dj.schema('ahoag_admin_demo')
# microscope_schema = dj.schema('ahoag_microscope_demo')

drop_lightsheet_admin = input("Drop light sheet, admin and spockadmin schemas? (yes or No): ")
if drop_lightsheet_admin == 'yes':
	admin_schema.drop(force=True)
	lightsheet_schema.drop(force=True)
	spockadmin_schema.drop(force=True)
# # from schemas import admin # admin imports lightsheet so no need to reimport here
from schemas import spockadmin 
from schemas import lightsheet 
from schemas import admin
# drop_microscope = input("Drop microscope database? (yes or No): ")
# if drop_microscope == 'yes':
# 	microscope_schema.drop(force=True)
	
# from schemas import microscope

