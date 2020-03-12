FROM python:3.7.6-slim-buster

RUN apt-get update && apt-get install -y openssh-server

# Copy requirements over first so that they can be cached if they are not changed
COPY lightserv_requirements.txt /app/lightserv_requirements.txt

WORKDIR /app

RUN pip install -r lightserv_requirements.txt

COPY lightserv/ /app

COPY run.py /app

RUN mkdir /root/.ssh

COPY sshconfig/id_rsa /root/.ssh
COPY sshconfig/id_rsa.pub /root/.ssh

RUN chmod 700 /root/.ssh/id_rsa 