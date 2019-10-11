import os
os.environ['FLASK_MODE']='DEV'

from lightserv import cel, create_app
app = create_app()
app.app_context().push()