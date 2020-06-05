FROM python:3.7.6-slim-buster

RUN apt-get update && apt-get install -y openssh-server graphviz

# Copy requirements over first so that they can be cached if they are not changed
COPY requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip install --upgrade pip

RUN pip install -r requirements.txt

COPY lightserv/ /app
COPY logs /app/logs

COPY run.py /app

# Make lightservuser, with same UID as lightservuser
RUN useradd -r -u 2354 -d /home/lightservuser -m lightservuser
# Make lightservuser owner of /app
RUN chown -R lightservuser /app
# Make the group with the same groupid as g_lightsheet_data on spock
RUN groupadd -g 9038 g_lightsheet_data
# Add lightservuser to that group
RUN usermod -aG g_lightsheet_data lightservuser

# Copy ssh key into container so user can ssh into spock without a password
RUN mkdir /home/lightservuser/.ssh
COPY sshconfig/id_rsa /home/lightservuser/.ssh/id_rsa
COPY sshconfig/id_rsa.pub /home/lightservuser/.ssh/id_rsa.pub
RUN chown -R lightservuser /home/lightservuser/.ssh/id_rsa
# Set active user lightservuser
USER lightservuser
RUN chmod 700 /home/lightservuser/.ssh/id_rsa 
