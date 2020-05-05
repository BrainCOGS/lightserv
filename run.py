import os
hosturl = os.environ.get('HOSTURL')
from lightserv import create_app
from lightserv.config import DevConfig,ProdConfig
import socket

flask_mode = os.environ['FLASK_MODE']
if flask_mode == 'PROD':
	app = create_app(ProdConfig)
elif flask_mode == 'DEV':
	app = create_app(Config)

if __name__ == '__main__':
	import logging
	logger = logging.getLogger('werkzeug')

	formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

	''' Make the file handler to deal with logging to file '''
	file_handler = logging.FileHandler('logs/app_debug.log')
	file_handler.setFormatter(formatter)

	stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

	stream_handler.setFormatter(formatter)

	logger.addHandler(stream_handler)
	logger.addHandler(file_handler)
	if flask_mode == 'DEV':
		app.run(host='0.0.0.0',port='5000',debug=True) # 5000 inside the container
	elif flask_mode == 'PROD':
		app.run(host='0.0.0.0',port='5000') # 5000 inside the container


	