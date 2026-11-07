FROM python:3.14-slim-trixie
WORKDIR /opt/repos
RUN mkdir -p /mnt/exchange
COPY requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt
COPY neuroglancer_launcher.py /opt/neuroglancer_launcher.py
COPY allen_hierarch_labels_fillmissing.json /opt/allen.json
COPY allen_id_table_w_voxel_counts_hierarch_labels.csv /opt/allen_id_table_w_voxel_counts_hierarch_labels.csv
CMD ["python","/opt/neuroglancer_launcher.py"]
