# lightserv_dj_demo

lightserv_dj_demo is a flask application to allow users to create light sheet microscopy data requests at the Princeton Neuroscience Institute U19 Core Facility. Users can view their current and past requests. The application uses [datajoint](https://github.com/datajoint/datajoint-python) to connect to a MariaDB or MySQL database hosted on localhost:3306. One can forward a port (see [Database Setup](#database-setup) below) to 3306 as a way to connect to an external database server.

This is currently a demo, so submitting a new request only updates a database table but does not start an actual experiment.


## Setup

Create a new virtual environmet, e.g.:

```
conda create -n lightserv python=3.7
```
Activate virtual environment:
```
conda activate lightserv
```

Install packages into virtual environment:
```
pip install -r requirements.txt
```

Set environment variables:
```

SECRET_KEY # a random hex string, for example
MAIL_USERNAME # The email account from which password reset info will be delivered to user
MAIL_PASSWORD # The password to the above email account
```

In order to connect to the MariaDB database, forward port 3306 from jtb3-dev.princeton.edu to localhost:3306:
```
ssh {username}@jtb3-dev.princeton.edu -L 3306:127.0.0.1:3306 -N
```

## Celery config
Celery is a asynchronous job manager, allowing you to submit jobs from a flask route without having to wait for the job to complete. I have celery set up with a mysql database at jtb3-dev (same database server as where the main database lives) using rabbitmq as a message queue. The celery server needs to be started before the flask app is run in order for flask to be able to perform asynchronous tasks. It is started via:

```
bash
celery -A celery_worker.cel worker --loglevel=info
```
where `celery_worker` references the file: `celery_worker.py`. The above line starts a dummy version of this application, giving celery the flask application context it needs to run its tasks. 


## Run
=======

```python
python run.py
```

This will run the application on http://127.0.0.1:5000/


## Testing

In order to use pytest to test the application using the same database server but with a different schema, the environment variable 'FLASK_MODE' needs to be set. I created an alias to set this variable and to run pytest in a single command:
```bash
alias pytestflask="export FLASK_MODE='TEST';pytest"
```
To test, simply run:
```bash
pytestflask --your_options_here
```
