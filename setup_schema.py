# import datajoint as dj
import os
# dj.config['database.host'] = '127.0.0.1'
# dj.config['database.port'] = 3306

# dj.config['database.user'] = 'ahoag'
# dj.config['database.password'] = 'p@sswd'
os.environ['FLASK_MODE'] = 'DEV'
from schemas import lightsheet
from schemas import admin
from schemas import microscope

