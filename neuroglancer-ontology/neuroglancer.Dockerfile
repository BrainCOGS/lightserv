FROM python:3.6.9-slim-buster

RUN mkdir -p /opt/repos && mkdir -p /mnt/exchange

##not actually in use anymore, removal of igneous outmodes the need.
WORKDIR /opt/repos

RUN apt-get update -y && apt-get upgrade -y && \
    apt-get install bash git gcc 'g++' musl-dev -y

RUN  pip install neuroglancer==2.8 redis pandas graphviz Flask==1.1.1

COPY neuroglancer_launcher.py /opt/neuroglancer_launcher.py

COPY allen.json /opt/allen.json

COPY allen_id_table_w_voxel_counts_hierarch_labels.csv /opt/allen_id_table_w_voxel_counts_hierarch_labels.csv

CMD ["python","/opt/neuroglancer_launcher.py"]
