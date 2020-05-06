import os 
import datajoint as dj
dj.config['database.host'] = 'datajoint00.pni.princeton.edu'
dj.config['database.port'] = 3306

dj.config['database.user'] = os.environ['DJ_DB_USER']
dj.config['database.password'] = os.environ['DJ_DB_PASS']

os.environ['FLASK_MODE'] = 'DEV'

spockadmin_schema = dj.schema('ahoag_spockadmin_demo')
lightsheet_schema = dj.schema('ahoag_lightsheet_demo')
admin_schema = dj.schema('ahoag_admin_demo')

drop_lightsheet_admin = input("Drop light sheet, admin and spockadmin schemas? (yes or No): ")
if drop_lightsheet_admin == 'yes':
	# You have to drop the schemas that use the other schemas first
	# because if you try to drop a parent schema but a dependent schema
	# still exists then you will get a foreign key error
	admin_schema.drop(force=True)
	lightsheet_schema.drop(force=True)
	spockadmin_schema.drop(force=True)

from schemas import spockadmin 
from schemas import lightsheet 
from schemas import admin
