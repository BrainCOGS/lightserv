FROM python:3.14-slim-trixie
WORKDIR /opt/repos
RUN mkdir -p /mnt/exchange
COPY requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt
COPY neuroglancer_launcher.py /opt/neuroglancer_launcher.py
COPY kimatlas_segments.npy kimatlas_segments.npy 
CMD ["python","/opt/neuroglancer_launcher.py"]
