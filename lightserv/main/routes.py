from flask import render_template, request, redirect, Blueprint, session, url_for, flash, Markup,Request
from lightserv import db
from lightserv.tables import ExpTable
import pandas as pd
from .utils import logged_in, table_sorter
from functools import partial, wraps
from lightserv.tasks import reverse


import socket
import numpy as np

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/main_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)


main = Blueprint('main',__name__)

@main.route("/") 
@main.route("/home")
@logged_in
def home(): 
	username = session['user']
	logger.info(f"{username} accessed home page")
	if username in ['ahoag','zmd','ll3']:
		exp_contents = db.Experiment()
		legend = 'All light sheet experiments'
	else:
		exp_contents = db.Experiment() & f'username="{username}"'
		legend = 'Your light sheet experiments'
	sort = request.args.get('sort', 'experiment_id') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	sorted_results = sorted(exp_contents.fetch(as_dict=True),
		key=partial(table_sorter,sort_key=sort),reverse=reverse) # partial allows you to pass in a parameter to the function

	table = ExpTable(sorted_results,sort_by=sort,
					  sort_reverse=reverse)
	return render_template('main/home.html',exp_contents=exp_contents,exp_table=table,legend=legend)

@main.route('/login', methods=['GET', 'POST'])
def login():
	next_url = request.args.get("next")
	logger.info("Logging you in first!")
	hostname = socket.gethostname()
	if hostname == 'braincogs00.pni.princeton.edu':
		username = request.headers['X-Remote-User']
	else:
		username = 'ahoag'

	session['user'] = username
	''' If user not already in User() table, then add them '''
	all_usernames = db.User().fetch('username') 
	if username not in all_usernames:
		email = username + '@princeton.edu'
		user_dict = {'username':username,'princeton_email':email}
		db.User().insert1(user_dict)
		logger.info(f"Added {username} to User table in database")
	logger.info(session)
	return redirect(next_url)

@main.route("/allenatlas")
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
	return render_template('experiments/datalink.html',viewer=viewer)


@main.route("/test_celery")
def test_celery():
	reverse.delay('youknowwho')
	return "Started an async task with celery!"