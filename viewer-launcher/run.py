# app.py - a minimal flask application
# from flask import Flask
# from celery import Celery
# import redis
# from datetime import timedelta
from viewer_launcher import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0',port=5005)