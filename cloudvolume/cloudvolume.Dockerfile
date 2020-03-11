FROM python:3.6.9-slim-buster

RUN mkdir -p /opt/repos && mkdir -p /tmp/cloudvolume/test-skeletons

WORKDIR /opt/repos

RUN apt-get update && apt-get upgrade -y && \
    apt-get install bash git build-essential musl-dev curl htop psmisc net-tools -y

#RUN git clone https://github.com/seung-lab/cloud-volume.git && cd cloud-volume && \

RUN pip install redis cloud-volume && pip install cloud-volume[boss,test,all_viewers]

VOLUME ["/mnt/data"]

COPY cloudvolume_launcher.py /opt/cloudvolume_launcher.py

CMD ["python","/opt/cloudvolume_launcher.py"]
