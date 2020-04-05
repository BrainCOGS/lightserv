FROM python:3.7.6-slim-buster

RUN apt-get update && apt-get install -y openssh-server

# Copy requirements over first so that they can be cached if they are not changed
COPY requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip install -r requirements.txt

COPY lightserv/ /app
COPY logs /app/logs

COPY run.py /app

# Make lightservuser 
RUN useradd -r -u 153574 -d /home/lightservuser -m lightservuser
# Give read and write permissions to lightservuser /app
RUN chown -R lightservuser /app

RUN mkdir /home/lightservuser/.ssh
COPY sshconfig/id_rsa /home/lightservuser/.ssh/id_rsa
COPY sshconfig/id_rsa.pub /home/lightservuser/.ssh/id_rsa.pub
RUN chown -R lightservuser /home/lightservuser/.ssh/id_rsa
# Set active user lightservuser
USER lightservuser
RUN chmod 700 /home/lightservuser/.ssh/id_rsa 
