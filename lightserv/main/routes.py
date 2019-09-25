from flask import render_template, request, redirect, Blueprint, session, url_for, flash, Markup,Request
from lightserv import db
from lightserv.tables import ExpTable
import pandas as pd
from . import utils
from functools import partial

import socket
import numpy as np

# from lightserv.experiments.routes import experiments

main = Blueprint('main',__name__)
@main.route("/") # Where the app brings you when you pass CAS
@main.route("/home")
def home():
	# if 'user' not in session: # When the user has just logged into CAS 
	# username = session['user']
	print(session)
	hostname = socket.gethostname()
	if hostname == 'braincogs00.pni.princeton.edu':
		username = request.headers['X-Remote-User']
	else:
		username = 'ahoag'
	session['user'] = username

	if username in ['ahoag','zmd']:
		exp_contents = db.Experiment()
		legend = 'All light sheet experiments'
	else:
		exp_contents = db.Experiment() & f'username="{username}"'
		legend = 'Your light sheet experiments'
	sort = request.args.get('sort', 'experiment_id') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	sorted_results = sorted(exp_contents.fetch(as_dict=True),
		key=partial(utils.table_sorter,sort_key=sort),reverse=reverse) # partial allows you to pass in a parameter to the function

	table = ExpTable(sorted_results,sort_by=sort,
					  sort_reverse=reverse)
	return render_template('home.html',exp_table=table,legend=legend)

@main.route("/allenatlas",)
def allenatlas():
	""" Makes a neuroglancer viewer for the allen brain atlas and then generates a link for the user to click 
	to enter neuroglancer."""
	import neuroglancer
	import cloudvolume
	try: 
		vol = cloudvolume.CloudVolume('file:///jukebox/LightSheetData/atlas/neuroglancer/atlas/allenatlas_2017')
		# vol = cloudvolume.CloudVolume('file:///home/ahoag/ngdemo/demo_bucket/demo_dataset/demo_layer_singletif/')
		atlas_data = np.transpose(vol[:][...,0],(2,1,0)) # can take a few seconds
		viewer = neuroglancer.Viewer()
		# This volume handle can be used to notify the viewer that the data has changed.
		volume = neuroglancer.LocalVolume(
				 data=atlas_data, # need it in z,y,x order, strangely
				 voxel_size=[25000,25000,25000],
				 voxel_offset = [0, 0, 0], # x,y,z in nm not voxels
				 volume_type='segmentation'
				 )
		with viewer.txn() as s:
			s.layers['segmentation'] = neuroglancer.SegmentationLayer(source=volume
			)
	except:
		flash('Something went wrong starting Neuroglancer. Try again later.','danger')
		return redirect(url_for('main.home'))
	return render_template('datalink.html',viewer=viewer)