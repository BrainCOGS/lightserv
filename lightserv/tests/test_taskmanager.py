from flask import url_for

def test_hello_task(celery_app,celery_worker,test_client):
	""" Check that I can execute a basic task 
	that does not depend on the state of the app """
	response = test_client.get(url_for('taskmanager.say_hello'),
		follow_redirects=True)
	""" check that the last entry in the test celery database is "hello world" """

	# print(celery_app.conf)
	assert 4==4

def test_goodbye_task(celery_app,celery_worker,test_client):
	""" Check that I can execute a basic task 
	that does not depend on the state of the app """
	response = test_client.get(url_for('taskmanager.say_goodbye'),
		follow_redirects=True)
	# print(celery_app.conf)
	assert 4==4

def test_check_all_statuses(celery_app,celery_worker,test_client):
	""" Check that I can execute a basic task 
	that does not depend on the state of the app """
	response = test_client.get(url_for('taskmanager.check_all_statuses'),
		follow_redirects=True)
	# print(celery_app.conf)
	assert 4==4

# @pytest.mark.usefixtures('celery_session_app')
# @pytest.mark.usefixtures('celery_session_worker')
# class MyTest():
#     def test(self):
#         assert mul.delay(4, 4).get(timeout=10) == 16

# def test_create_task(celery_app, celery_worker):
#     @celery_app.task
#     def mul(x, y):
#         return x * y

#     assert mul.delay(4, 4).get(timeout=10) == 16