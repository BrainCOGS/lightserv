FROM cloudv:latest

RUN pip install Pillow tifffile

VOLUME ["/mnt/viz"]

COPY make_precomputed_rawdata.py /opt/make_precomputed_rawdata.py

RUN useradd -r -u 153574 -d /home/lightservuser -m lightservuser
USER lightservuser

