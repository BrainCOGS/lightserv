import os
os.environ['FLASK_MODE']='DEV'

from lightserv import create_app
import socket

app = create_app()


if __name__ == '__main__':
	if socket.gethostname() == 'braincogs00.pni.princeton.edu':
		app.run(host='0.0.0.0',port='8080',debug=True)
	else:
		app.run(debug=True)