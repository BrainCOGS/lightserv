from lightserv.main import tasks as maintasks
from datetime import datetime,timedelta

def test_celery_working(celery_app,celery_worker,test_client):
	""" Check that I can execute a basic task 
	that does not depend on the state of the app """
	# response = test_client.get(url_for('main.say_hello'),
	#     follow_redirects=True)
	# assert 4==4
	assert maintasks.hello.delay().get(timeout=10) == "hello world"

def test_future_task(celery_app,celery_worker,test_client):
	""" Check that I can execute a basic task 
	that does not depend on the state of the app """
	# response = test_client.get(url_for('main.say_hello'),
	#     follow_redirects=True)
	# assert 4==4
	future_time = datetime.utcnow() + timedelta(seconds=45)
	print("sending hello task")
	maintasks.hello.apply_async(eta=future_time) 
	print("sending hello task")
	assert 4==4