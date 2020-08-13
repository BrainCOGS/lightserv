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
layer_name = 'allenatlas_2017_16bit_hierarch_labels'

with viewer.txn() as s:
	s.layers[layer_name] = neuroglancer.SegmentationLayer(
		source=f"precomputed://gs://wanglab-pma-test/{layer_name}" # this needs to be visible outside of the container in the browser
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

def init_tool(s):
	logging.debug("in init_tool()")
	with viewer.config_state.txn() as st:
		try:
			del st.status_messages['hello']
		except KeyError:
			pass
	logging.debug("made it here")
	""" first figure out the selected layer """
	with viewer.txn() as txn:
		if len(txn.layers) > 1:
			selected_layer_name = txn.selectedLayer.layer
			if not selected_layer_name:
				with viewer.config_state.txn() as st:
					st.status_messages['hello'] = 'No layer selected. Select a layer (right click or ctrl+click the layer panel)'        
					return None, None
		elif len(txn.layers) == 1:
			logging.debug("should be here")
			selected_layer_name = txn.layers[0].name
		else:
			with viewer.config_state.txn() as st:
				st.status_messages['hello'] = 'No layers loaded. First load a layer to use this tool'        
				return None, None
	logging.debug("selecting region_map")
	logging.debug("layer name:")
	logging.debug(selected_layer_name)
	logging.debug("selected values:")
	logging.debug(s.selected_values)
	try:
		region_map = s.selected_values[selected_layer_name]
	except KeyError:
		# you need to move your cursor to get the layer to be selectable again
		return None, None
	named_tuple = region_map.value
	logging.debug("end of init_tool()")
	logging.debug("named tuple:")
	logging.debug(named_tuple)
	return named_tuple, selected_layer_name

def contract_atlas(s):
	named_tuple, selected_layer_name = init_tool(s)

	if named_tuple:
		with viewer.config_state.txn() as st:
			st.status_messages['hello'] = 'key p pressed: contracting atlas' 
		if named_tuple.value:
			region_id = named_tuple.value
		else:
			region_id = named_tuple.key
		region_name = ontology_id_dict[region_id]
		# Look up parent name and then get corresponding ID
		parent_name = get_parent(Gnew,region_name)
		if not parent_name:
			with viewer.config_state.txn() as st:
				st.status_messages['hello'] = 'No parent found.'
			return
		parent_id = ontology_name_dict.get(parent_name)
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
			existing_equivalences = list(txn.layers[selected_layer_name].layer.equivalences.items())
			final_equivalence_list = existing_equivalences + equivalence_list
			txn.layers[selected_layer_name].layer.equivalences = final_equivalence_list
		return
	else:
		with viewer.config_state.txn() as st:
			st.status_messages['hello'] = 'No segment under cursor. Hover over segment to enable hierarchy tools' 
		return
	
def expand_atlas(s):
	named_tuple, selected_layer_name = init_tool(s)

	if named_tuple:
		with viewer.config_state.txn() as st:
			st.status_messages['hello'] = 'key c pressed: expanding atlas' 
		""" if the hovered segment is mapped to a parent, then start at the parent level"""
		if named_tuple.value:
			region_id = named_tuple.value
		else:
			region_id = named_tuple.key
		""" Find and remove any existing equivalences that involve this region_id"""
		with viewer.txn() as txn:
			equiv_map = txn.layers[selected_layer_name].layer.equivalences
			if region_id not in equiv_map.keys():
				with viewer.config_state.txn() as st:
					st.status_messages['hello'] = 'This segment is already at the lowest level in the hierarchy'
			else:
				equiv_map.delete_set(region_id)
		return
	else:
		with viewer.config_state.txn() as st:
			st.status_messages['hello'] = 'No segment under cursor. Hover over segment to enable hierarchy tools' 
		return


viewer.actions.add(f'go up a level in the atlas hierarchy', contract_atlas)
viewer.actions.add(f'got to bottom of this branch of the atlas hierarchy', expand_atlas)
with viewer.config_state.txn() as s:
	s.input_event_bindings.viewer['keyp'] = f'go up a level in the atlas hierarchy'
	s.input_event_bindings.viewer['keyc'] = f'got to bottom of this branch of the atlas hierarchy'
	s.status_messages['hello'] = ('Merge ontology tool activated. '
			'When hovered over a region: press p to go up, c to go down in hierarchy.')

# def my_action(s):
#     logging.debug('Got my-action')
#     logging.debug('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
#     logging.debug('  Layer selected values: %s' % (s.selected_values,))
#     with viewer.config_state.txn() as s:
#         s.status_messages['hello'] = 'We heard you.'
#     with viewer.txn() as s:
#         s.cross_section_scale = 8
# viewer.actions.add('my-action', my_action)
# with viewer.config_state.txn() as s:
#     s.input_event_bindings.viewer['keyt'] = 'my-action'
#     s.status_messages['hello'] = 'Welcome to this example'

while True:
	sleep(1)
