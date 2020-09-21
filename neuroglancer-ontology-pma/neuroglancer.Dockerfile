FROM python:3.6.9-slim-buster

RUN mkdir -p /opt/repos && mkdir -p /mnt/exchange

##not actually in use anymore, removal of igneous outmodes the need.
WORKDIR /opt/repos

RUN apt-get update -y && apt-get upgrade -y && \
    apt-get install bash git gcc 'g++' musl-dev -y

RUN  pip install neuroglancer==2.10 redis graphviz

COPY neuroglancer_launcher.py /opt/neuroglancer_launcher.py

COPY PMA_ontology.json /opt/PMA_ontology.json

CMD ["python","/opt/neuroglancer_launcher.py"]
