import os
os.environ['FLASK_MODE']='DEV'
hosturl = os.environ['HOSTURL']
from lightserv import create_app
import socket

app = create_app()

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

	if hosturl == 'braincogs00.pni.princeton.edu':
		app.run(host='0.0.0.0',port='8080',debug=True)
	else:
		app.run(port='5001',debug=True)

	