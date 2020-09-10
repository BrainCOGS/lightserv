from lightserv.main import tasks as maintasks
from datetime import datetime,timedelta

def test_celery_working(celery_app,celery_worker,test_client):
	""" Check that I can execute a basic task 
	that does not depend on the state of the app """
	# response = test_client.get(url_for('main.say_hello'),
	#     follow_redirects=True)
	# assert 4==4
	assert maintasks.hello.delay().get(timeout=10) == "hello world"

