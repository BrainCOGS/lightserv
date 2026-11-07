"""Run only in the isolated Docker test network (writes disposable schemas)."""
import os
assert os.environ['DJ_DB_HOST'] == 'db'
assert os.environ['FLASK_MODE'] == 'TEST'
import datajoint as dj
from celery_worker import app, cel
from lightserv import db_admin, db_lightsheet
from lightserv.config import ProdConfig, DevConfig, TestConfig
from lightserv.user_agent import browser_details
from flask import url_for

assert dj.__version__ == '0.14.10'
assert len(ProdConfig.beat_schedule) == 12
assert len(DevConfig.beat_schedule) == 1
assert cel.conf.task_always_eager
assert cel.conf.timezone == 'America/New_York'
assert len([name for name in cel.tasks if name.startswith('lightserv.')]) >= 21
assert all(browser_details(''))
app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
with app.test_client() as client:
    response = client.get('/login?next=/', headers={'User-Agent': '', 'X-Remote-User': 'testuser'})
    assert response.status_code == 302, response.data
    row = db_admin.UserActionLog().fetch(as_dict=True)[-1]
    assert row['browser_name'] and row['browser_version'] and row['platform']
    assert len(db_lightsheet.User() & {'username': 'testuser'}) == 1
    for endpoint in ('main.welcome', 'main.gallery', 'main.FAQ', 'requests.all_requests'):
        with app.test_request_context():
            path = url_for(endpoint)
        response = client.get(path, follow_redirects=True)
        assert response.status_code == 200, (path, response.status_code, response.data[:500])
from lightserv.main.tasks import hello
assert hello.delay().get() == 'hello world'
print('PASS: exact DataJoint pin, schedules, task registration, login/audit writes, pages/tables, eager task')
