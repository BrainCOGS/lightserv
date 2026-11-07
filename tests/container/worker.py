"""Exercise a real worker/beat and SQLAlchemy result storage, on disposable DB only."""
import os
import subprocess
import time
assert os.environ['DJ_DB_HOST'] == 'db'
assert os.environ['FLASK_MODE'] == 'TEST'
assert os.environ['CELERY_RESULT_BACKEND'] == 'db+mysql+pymysql://root:isolated-only@db/port_celery'
import datajoint as dj
from celery_worker import cel
dj.conn().query('CREATE DATABASE IF NOT EXISTS port_celery')
from celery.beat import PersistentScheduler
from lightserv.config import ProdConfig
from lightserv.main.tasks import hello

cel.conf.task_always_eager = False
worker = subprocess.Popen(['celery', '-A', 'celery_worker.cel', 'worker', '--pool=solo', '--concurrency=1', '--loglevel=INFO'])
try:
    for _ in range(30):
        if cel.control.ping(timeout=1):
            break
        time.sleep(1)
    else:
        raise AssertionError('worker did not respond')
    result = cel.send_task(hello.name)
    assert result.get(timeout=30) == 'hello world'
    # Construct the real production schedule without dispatching its tasks.
    cel.conf.beat_schedule = ProdConfig.beat_schedule
    scheduler = PersistentScheduler(app=cel, schedule_filename='/tmp/port-beat')
    assert set(ProdConfig.beat_schedule) <= set(scheduler.schedule)
    assert cel.conf.timezone == 'America/New_York'
    scheduler.close()
    # A separate scheduler exercises publication using only the harmless hello task.
    cel.conf.beat_schedule = {'smoke-hello': {'task': hello.name, 'schedule': 1}}
    scheduler = PersistentScheduler(app=cel, schedule_filename='/tmp/port-smoke-beat')
    entry = scheduler.schedule['smoke-hello']
    scheduled = scheduler.apply_async(entry)
    assert scheduled.get(timeout=30) == 'hello world'
    scheduler.close()
    print('PASS: worker delivery, SQL result backend, production schedule loading, beat publication')
finally:
    worker.terminate()
    worker.wait(timeout=20)
