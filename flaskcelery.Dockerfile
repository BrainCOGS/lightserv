FROM python:3.7.6-slim-buster

RUN apt-get update && apt-get install -y openssh-server

# Copy requirements over first so that they can be cached if they are not changed
COPY flask_requirements.txt /app/flask_requirements.txt

WORKDIR /app

RUN pip install -r flask_requirements.txt

COPY lightserv/ /app

COPY run.py /app

# CMD python run.py