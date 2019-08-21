# lightserv_dj_demo

lightserv_dj_demo is a flask application to allow users to create light sheet microscopy data requests at the Princeton Neuroscience Institute U19 Core Facility. Users can view their current and past requests.

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
ssh {username}@pni-192QMG3Y2.princeton.edu -L 3306:127.0.0.1:3306 -N
```


## Run

```python
python run.py
```

This will run the application on http://127.0.0.1:5000/
