FROM python:3.7.6-slim-buster

RUN apt-get update && apt-get install -y openssh-server graphviz

# Copy requirements over first so that they can be cached if they are not changed
COPY requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip install --upgrade pip

RUN pip install -r requirements.txt

COPY lightserv/ /app
COPY logs /app/logs