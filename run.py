import os
os.environ['FLASK_MODE']='DEV'

from lightserv import create_app


app = create_app()

if __name__ == '__main__':
	app.run(debug=True)