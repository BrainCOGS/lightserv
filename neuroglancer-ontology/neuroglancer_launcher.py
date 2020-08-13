#! /bin/env python

## basic shim to load up neuroglancer in a browser:
import neuroglancer
import logging
from time import sleep
import redis
import os
import json
# from utils import *
import pandas as pd
import graphviz
import numpy as np

hosturl = os.environ['HOSTURL']

kv = redis.Redis(host="redis", decode_responses=True)  # container simply named redis

logging.basicConfig(level=logging.DEBUG)
# we are currently using the seunglab hosted neuroglancer static resources
# ideally this would be self hosted for local development against nglancer
logging.info("configuring neuroglancer defaults")
# neuroglancer.set_static_content_source(
#     url="https://neuromancer-seung-import.appspot.com"
# )
flask_mode = os.environ['FLASK_MODE']
if flask_mode == 'DEV':
	neuroglancer.set_static_content_source(
		url="http://nglancerstatic-dev:8080"
	)
elif flask_mode == 'PROD':
	neuroglancer.set_static_content_source(
		url="http://nglancerstatic-prod:8080"
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
logging.debug("session dict:")
logging.debug(session_dict)

try:
	cv_count = int(session_dict['cv_count']) # number of cloudvolumes
except:
	logging.debug("No cloudvolumes to view")
	cv_count = 0
layer_list = []
for ii in range(cv_count):
	cv_number = ii+1
	cv_name = session_dict[f'cv{cv_number}_name']

	layer_list.append(cv_name)
	layer_type = session_dict[f'layer{cv_number}_type']
	with viewer.txn() as s:
		logging.debug("Loading in source: ")
		logging.debug(f"precomputed://https://{hosturl}/cv/{session_name}/{cv_name}")
		if layer_type == 'image':
			s.layers[cv_name] = neuroglancer.ImageLayer(
				source=f"precomputed://https://{hosturl}/cv/{session_name}/{cv_name}") # this needs to be visible outside of the container in the browser
		elif layer_type == 'segmentation':
			
			s.layers[cv_name] = neuroglancer.SegmentationLayer(
				source=f"precomputed://https://{hosturl}/cv/{session_name}/{cv_name}" # this needs to be visible outside of the container in the browser
			)
		elif layer_type == 'annotation':
			s.layers[cv_name] = neuroglancer.AnnotationLayer(
				source=f"precomputed://https://{hosturl}/cv/{session_name}/{cv_name}" # this needs to be visible outside of the container in the browser
			)
			

logging.debug("Not changing the layout")
logging.debug("neuroglancer viewer is now available")

## redis shared state segment
viewer_dict = {"host": "nglancer", "port": "8080", "token": viewer.token}
viewer_json_str = json.dumps(viewer_dict)
kv.hmset(session_name,{'viewer': viewer_json_str})

# Add the key bindings
logging.debug('adding key bindings')
df_allen = pd.read_csv('/opt/allen_id_table_w_voxel_counts_hierarch_labels.csv')
logging.debug("read in dataframe")
logging.debug(df_allen)
ids = df_allen['reassigned_id']
names = df_allen['name']
ontology_id_dict = {ids[ii]:names[ii] for ii in range(len(df_allen))}
ontology_name_dict = {names[ii]:ids[ii] for ii in range(len(df_allen))}

ontology_file = '/opt/allen.json'
logging.debug("loading in JSON ontology file")

with open(ontology_file) as json_file:
	data = json.load(json_file)
logging.debug("read in JSON file")

""" Make the graph that will be used
in the get_parent() function below """

def make_id_graph(dic,graph):
	""" Make a edge-unweighted directed graph from a dictionary
	Representing a brain ontology
	"""
	name = dic.get('name')
	acronym = dic.get('acronym')
	children = dic.get('children')
	orig_id = dic.get('id')
	new_id = dic.get('graph_order') + 1
	graph.node(name,f'{acronym}: {new_id}')
	for child in children:
		child_name = child.get('name')
		graph.edge(name,child_name)
		make_id_graph(child,graph)
	return 

Gnew = graphviz.Digraph()
make_id_graph(data,Gnew)

def get_progeny(dic,input_nodename,progeny_list=None):
	"""
	Gets all of the descendents of a given input nodename.
	--- INPUT ---
	dic             The dictionary representing the JSON ontology graph
	input_nodename   The name of the region whose progeny you want to know
	"""
	if progeny_list == None:
		progeny_list = []
	if input_nodename == 'root':
		return list(ontology_name_dict.keys()) 
		
	name = dic.get('name')

	children = dic.get('children')
	if name == input_nodename:
		for child in children: # child is a dict
			child_name = child.get('name')
			progeny_list.append(child_name)
			get_progeny(child,input_nodename=child_name,progeny_list=progeny_list)
		return
	
	for child in children:
		child_name = child.get('name')
		get_progeny(child,input_nodename=input_nodename,progeny_list=progeny_list)
	return progeny_list

def get_parent(graph,input_nodename):
	if len(input_nodename.split(' ')) > 1:
		nodename_to_search = f'"{input_nodename}"'
	else:
		nodename_to_search = input_nodename
	edges_pointing_to_node=[x for x in graph.body if f'-> {nodename_to_search}' in x]
	if len(edges_pointing_to_node) == 0:
		return None
	elif len(edges_pointing_to_node) > 1:
		print("Error. There should not be more than one edge pointing to this node")
	else:
		parent_nodename = edges_pointing_to_node[0].split('->')[0].strip()
		# remove the extra quotes surrounding the nodename if there is more than one word
		if len(parent_nodename.split(' ')) > 1:
			return parent_nodename[1:-1]
		else:
			return parent_nodename
	return

def contract_atlas(s):
	# with viewer.config_state.txn() as st:
	# 	st.status_messages['hello'] = 'Message received'
	if cv_count != 1:
		with viewer.config_state.txn() as st:
			st.status_messages['hello'] = 'There was an issue with the ontology merge tool. Please report this.'
		return

	layer_name = session_dict['cv1_name']
	region_map = s.selected_values[layer_name]
	named_tuple = region_map.value
	if named_tuple:
		if named_tuple.value:
			region_id = named_tuple.value
		else:
			region_id = named_tuple.key
		region_name = ontology_id_dict[region_id]
		logging.debug(region_name)
		# Look up parent name and then get corresponding ID
		parent_name = get_parent(Gnew,region_name)
		if not parent_name:
			with viewer.config_state.txn() as st:
				st.status_messages['hello'] = 'No parent found.'
			return
		parent_id = ontology_name_dict.get(parent_name)
		logging.debug("parent found")
		logging.debug(parent_id)
		# find all progeny of this parent
		progeny_list = get_progeny(data,input_nodename=parent_name) # progeny names
		# initialize our equivalence list using the id-parent relationship we just found
		equivalence_list = [] 
		# Get the progeny ids and include them in the equivalence list
		for progeny_name in progeny_list:
			progeny_id = ontology_name_dict.get(progeny_name)
			if progeny_id:
				equivalence_list.append((progeny_id,parent_id)) 
		with viewer.txn() as txn:
			existing_equivalences = list(txn.layers[layer_name].layer.equivalences.items())
			final_equivalence_list = existing_equivalences + equivalence_list
			txn.layers['Allen hierarch labels'].layer.equivalences = final_equivalence_list
			logging.debug(txn.layers['Allen hierarch labels'].layer.equivalences.items())
		return
	else:
		with viewer.config_state.txn() as st:
			st.status_messages['hello'] = 'No segment under cursor. Hover over segment to enable hierarchy tools' 
		return
	
def expand_atlas(s):
	with viewer.config_state.txn() as st:
		logging.debug(st.status_messages)
		st.status_messages['hello'] = 'Message received'
	if cv_count != 1:
		with viewer.config_state.txn() as st:
			st.status_messages['hello'] = 'There was an issue with the ontology merge tool. Please report this.'
		return
	layer_name = session_dict['cv1_name']
	region_map = s.selected_values[layer_name]
	named_tuple = region_map.value
	if named_tuple:
		""" if the hovered segment is mapped to a parent, then start at the parent level"""
		if named_tuple.value:
			region_id = named_tuple.value
		else:
			region_id = named_tuple.key
		""" Find and remove any existing equivalences that involve this region_id"""
		with viewer.txn() as txn:
			equiv_map = txn.layers[layer_name].layer.equivalences
			if region_id not in equiv_map.keys():
				with viewer.config_state.txn() as st:
					st.status_messages['hello'] = 'This segment is already at the lowest level in the hierarchy'
			else:
				equiv_map.delete_set(region_id)
		return
	else:
		st.status_messages['hello'] = 'No segment under cursor. Hover over segment to enable hierarchy tools' 
		return


viewer.actions.add(f'go up a level in the atlas hierarchy', contract_atlas)
viewer.actions.add(f'got to bottom of this branch of the atlas hierarchy', expand_atlas)
with viewer.config_state.txn() as s:
	s.input_event_bindings.viewer['keyp'] = f'go up a level in the atlas hierarchy'
	s.input_event_bindings.viewer['keyc'] = f'got to bottom of this branch of the atlas hierarchy'
	s.status_messages['hello'] = 'Welcome to the merge ontology example. Press p to go up a level, c to go down to bottom of selected branch.'

# def my_action(s):
# 	logging.debug('Got my-action')
# 	logging.debug('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
# 	logging.debug('  Layer selected values: %s' % (s.selected_values,))
# 	randn = np.random.randint(5,10)
# 	with viewer.config_state.txn() as s:
# 		s.status_messages['hello'] = f'We heard you. Zooming to {randn}'
# 	with viewer.txn() as s:
# 		s.cross_section_scale = randn
# viewer.actions.add('my-action', my_action)
# with viewer.config_state.txn() as s:
# 	s.input_event_bindings.viewer['keyt'] = 'my-action'
# 	s.status_messages['hello'] = 'Welcome to this example'


while True:
	sleep(1)
# from flask import Flask

# app = Flask(__name__)

# @app.route("/") 
# def base():
#     return "home of my viewer"

# @app.route("/test") 
# def test():
#     print(viewer.state) 
#     return "test complete!"

# app.run(debug=True, host='0.0.0.0',port=5000)