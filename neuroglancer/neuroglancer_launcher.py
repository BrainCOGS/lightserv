#! /bin/env python

## basic shim to load up neuroglancer in a browser:
import neuroglancer
import logging
from time import sleep
import redis
import os
import json

hosturl = os.environ['HOSTURL']

kv = redis.Redis(host="redis", decode_responses=True)  # container simply named redis

logging.basicConfig(level=logging.DEBUG)
# we are currently using the seunglab hosted neuroglancer static resources
# ideally this would be self hosted for local development against nglancer
logging.info("configuring neuroglancer defaults")
neuroglancer.set_static_content_source(
    url="https://neuromancer-seung-import.appspot.com"
)
## neuroglancer setup segment:	
## set the tornado server that is launched to talk on all ips and at port 8080
neuroglancer.set_server_bind_address("0.0.0.0", "8080")

neuroglancer.debug = True
neuroglancer.server.debug = True

logging.info("starting viewer subprocess")
# setup a viewer with pre-configured defaults and launch.
viewer = neuroglancer.Viewer()

logging.info("viewer token: {}".format(viewer.token))

logging.info("setting viewers default volume")
# load data from cloudvolume container:
session_name = os.environ['SESSION_NAME'] # from the environment passed to this container when it is run
session_dict = kv.hgetall(session_name) # gets a dict of all key,val pairs in the session
cv_count = int(session_dict['cv_count']) # number of cloudvolumes
cv_names = []
for ii in range(cv_count):
	cv_number = ii+1
	cv_name = session_dict[f'cv{cv_number}_name']
	cv_names.append(cv_name)
	layer_type = session_dict[f'layer{cv_number}_type']
	with viewer.txn() as s:
		if layer_type == 'image':
		    s.layers[cv_name] = neuroglancer.ImageLayer(
		        source=f"precomputed://https://{hosturl}/cv/{session_name}/{cv_name}" # this needs to be visible outside of the container in the browser
		    )
		elif layer_type == 'segmentation':
			s.layers[cv_name] = neuroglancer.SegmentationLayer(
		        source=f"precomputed://https://{hosturl}/cv/{session_name}/{cv_name}" # this needs to be visible outside of the container in the browser
		    )

row_layout_list = [neuroglancer.LayerGroupViewer(layers=[x]) for x in cv_names]
with viewer.txn() as s:	
    s.layout = neuroglancer.row_layout(
        row_layout_list
    )
## need to retool this so it shows the correct link, the container's internal FQDN is not useful
logging.info("viewer at: {}".format(viewer))

logging.debug("neuroglancer viewer is now available")

## redis shared state segment
viewer_dict = {"host": "nglancer", "port": "8080", "token": viewer.token}
viewer_json_str = json.dumps(viewer_dict)
kv.hmset(session_name,{'viewer': viewer_json_str})

# Keep the viewer running
while 1:
    sleep(0.1)
