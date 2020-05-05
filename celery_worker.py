import os
from lightserv import cel, create_app
from lightserv.config import DevConfig,ProdConfig

flask_mode = os.environ['FLASK_MODE']

if flask_mode == 'PROD':
	app = create_app(ProdConfig)
elif flask_mode == 'DEV':
	app = create_app(DevConfig)
app.app_context().push()