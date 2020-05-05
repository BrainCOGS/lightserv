import os
from lightserv import cel, create_app
from lightserv.config import Config,ProdConfig

flask_mode = os.environ['FLASK_MODE']

if flask_mode == 'PROD':
	print("Using production config")
	app = create_app(ProdConfig)
elif flask_mode == 'DEV':
	app = create_app(Config)
app.app_context().push()