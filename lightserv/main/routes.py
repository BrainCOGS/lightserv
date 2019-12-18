from flask import (render_template, request, redirect,
				   Blueprint, session, url_for, flash,
				   Markup, Request, Response)
from lightserv import db_lightsheet
from lightserv.requests.tables import ExpTable
import pandas as pd
from lightserv.main.utils import logged_in, table_sorter, log_http_requests
from functools import partial, wraps
from lightserv.tasks import reverse

import datajoint as dj
import socket
import requests
import numpy as np

import logging
from time import sleep

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
@main.route("/welcome")
@logged_in
@log_http_requests
def welcome(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed welcome page")
	return render_template('main/welcome.html',)

@main.route("/home")
@log_http_requests
@logged_in
def home(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed home page")
	request_contents = db_lightsheet.Request()
	sample_contents = db_lightsheet.Sample()
	imaging_request_contents = db_lightsheet.Sample.ImagingRequest()
	processing_request_contents = db_lightsheet.Sample.ProcessingRequest()
	if current_user in ['ahoag','zmd','ll3','kellyms','jduva']:
		legend = 'All core facility requests'
	else:
		legend = 'Your core facility requests'
		request_contents = request_contents & f'username="{current_user}"'
		sample_contents = sample_contents & f'username="{current_user}"'
		imaging_request_contents = imaging_request_contents & f'username="{current_user}"'
		processing_request_contents = processing_request_contents & f'username="{current_user}"'
	''' Now figure out what fraction of the samples in each request are cleared/imaged/processed '''	
	sample_joined_contents = dj.U('username','request_name').aggr(
		request_contents * sample_contents,description='description',
		number_of_samples='number_of_samples',species='species',
		datetime_submitted='TIMESTAMP(date_submitted,time_submitted)',
		n_cleared='CONVERT(SUM(clearing_progress="complete"),char)').proj(
			number_of_samples='number_of_samples',
			fraction_cleared='CONCAT(n_cleared,"/",CONVERT(number_of_samples,char))',
			description='description',species='species',datetime_submitted='datetime_submitted')
	imaging_joined_contents = dj.U('username','request_name').aggr(
	sample_joined_contents * imaging_request_contents,
	number_of_samples='number_of_samples',
	species='species',description='description',
	datetime_submitted='datetime_submitted',
	fraction_cleared='fraction_cleared',
	n_imaged='CONVERT(SUM(imaging_progress="complete"),char)',
	total_imaging_requests='CONVERT(COUNT(*),char)'
	).proj(
		number_of_samples='number_of_samples',
		species='species',description='description',
		datetime_submitted='datetime_submitted',
		fraction_cleared='fraction_cleared',
		fraction_imaged='CONCAT(n_imaged,"/",total_imaging_requests)'
		)

	processing_joined_contents = dj.U('username','request_name').aggr(
	imaging_joined_contents * processing_request_contents,
	number_of_samples='number_of_samples',
	species='species',description='description',
	datetime_submitted='datetime_submitted',
	fraction_cleared='fraction_cleared',
	fraction_imaged='fraction_imaged',
	n_processed='CONVERT(SUM(processing_progress="complete"),char)',
	total_processing_requests='CONVERT(COUNT(*),char)'
	).proj(
		number_of_samples='number_of_samples',
		species='species',description='description',
		datetime_submitted='datetime_submitted',
		fraction_cleared='fraction_cleared',
		fraction_imaged='fraction_imaged',
		fraction_processed='CONCAT(n_processed,"/",total_processing_requests)'
		)

	sort = request.args.get('sort', 'request_name') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	sorted_results = sorted(processing_joined_contents.fetch(as_dict=True),
		key=partial(table_sorter,sort_key=sort),reverse=reverse) # partial allows you to pass in a parameter to the function

	table = ExpTable(sorted_results,sort_by=sort,
					  sort_reverse=reverse)
	table.table_id = 'horizontal'
	return render_template('main/home.html',request_contents=processing_joined_contents,request_table=table,legend=legend)

@main.route('/login', methods=['GET', 'POST'])
def login():
	next_url = request.args.get("next")
	logger.info("Logging you in first!")
	user_agent = request.user_agent
	browser_name = user_agent.browser # e.g. chrome
	browser_version = user_agent.version # e.g. '78.0.3904.108'
	platform = user_agent.platform # e.g. linux
	
	if browser_name.lower() != 'chrome':
		logger.info(f"User is using browser {browser_name}")
		flash(f"Warning: parts of this web portal were not completely tested on your browser: {browser_name}. "
		 "Firefox users will experience some known issues. We recommend switching to Google Chrome for a better experience.",'danger')
	hostname = socket.gethostname()
	if hostname == 'braincogs00.pni.princeton.edu':
		username = request.headers['X-Remote-User']
	else:
		username = 'ahoag'

	session['user'] = username
	''' If user not already in User() table, then add them '''
	all_usernames = db_lightsheet.User().fetch('username') 
	if username not in all_usernames:
		email = username + '@princeton.edu'
		user_dict = {'username':username,'princeton_email':email}
		db_lightsheet.User().insert1(user_dict)
		logger.info(f"Added {username} to User table in database")
	# logger.info(session)
	logstr = f'{username} logged in via "login()" route in lightserv.main.routes'
	insert_dict = {'browser_name':browser_name,'browser_version':browser_version,
				   'event':logstr,'platform':platform}
	db_lightsheet.UserActionLog().insert1(insert_dict)
	return redirect(next_url)

@main.route("/allenatlas")
@log_http_requests
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

@main.route("/npp_table",methods=['GET'])
@logged_in
@log_http_requests
def npp_table(): 
	r = requests.get('http://localhost:8001/api/routes')
	return Response(
		r.text,
		status=r.status_code
	)
	# return render_template('main/home.html',request_contents=request_contents,request_table=table,legend=legend)

@main.route("/post_to_table/",methods=['POST','GET'])
@logged_in
@log_http_requests
def post_npp_table(): 
	""" Send a post request to the npp table, opening a port """
	data = {
	'target':"http://localhost:1337"
	}
	headers={'Authorization': 'token 31507a9ddf3e41cf86b58ffede2db68326657437704461ae2c1a4018d55e18f0'}
	response = requests.post('http://localhost:8001/api/routes/test',json=data,headers=headers)
	print(response)
	flash(f'Entered port 1337 into routing table','success')
	return redirect(url_for('main.home'))
