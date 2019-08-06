# lightserv_UI

lightserv_UI is a flask application to allow users to create light sheet microscopy data requests at the Princeton Neuroscience Institute U19 Core Facility. Users can view their current and past requests.

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
SECRET_KEY # a random string hex string, for example
SQLALCHEMY_DATABASE_URI # point to the database. For the demo, set this to "sqlite:///site.db"
MAIL_USERNAME # The email account from which password reset info will be delivered to user
MAIL_PASSWORD # The password to the above email account
```

## Run

```python
python run.py
```

This will run the application on http://127.0.0.1:5000/
