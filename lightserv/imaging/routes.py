from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup)
from lightserv import db_lightsheet, mail, cel

from lightserv.main.utils import (logged_in, logged_in_as_clearer,
								  logged_in_as_imager,check_clearing_completed,
								  image_manager)
from lightserv.tables import ImagingTable, dynamic_imaging_management_table
from .forms import ImagingForm
import numpy as np
import datajoint as dj
import re
import datetime
from flask_mail import Message
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/imaging_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

imaging = Blueprint('imaging',__name__)

@imaging.route("/imaging/imaging_manager",methods=['GET','POST'])
@image_manager
def imaging_manager(): 
	sort = request.args.get('sort', 'datetime_submitted') # first is the variable name, second is default value
	reverse = (request.args.get('direction', 'asc') == 'desc')
	samples_contents = db_lightsheet.Sample()
	exp_contents = db_lightsheet.Experiment()
	joined_contents = (exp_contents * samples_contents) 
	proj_contents = joined_contents.proj('species','imager','clearing_progress',
	'imaging_progress',
	datetime_submitted='TIMESTAMP(date_submitted,time_submitted)') # will pick up the primary keys by default
	''' First get all entities that are currently being imaged '''
	contents_being_imaged = proj_contents & 'imaging_progress="in progress"'
	being_imaged_table_id = 'horizontal_being_imaged_table'
	table_being_imaged = dynamic_imaging_management_table(contents_being_imaged,
		table_id=being_imaged_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Next get all entities that are ready to be imaged '''
	contents_ready_to_image = proj_contents & 'clearing_progress="complete"' & 'imaging_progress="incomplete"'
	ready_to_image_table_id = 'horizontal_ready_to_image_table'
	table_ready_to_image = dynamic_imaging_management_table(contents_ready_to_image,
		table_id=ready_to_image_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Now get all entities on deck (currently being cleared) '''
	contents_on_deck = proj_contents & 'clearing_progress!="complete"' & 'imaging_progress!="complete"'
	on_deck_table_id = 'horizontal_on_deck_table'
	table_on_deck = dynamic_imaging_management_table(contents_on_deck,table_id=on_deck_table_id,
		sort_by=sort,sort_reverse=reverse)
	''' Finally get all entities that have already been imaged '''
	contents_already_imaged = proj_contents & 'imaging_progress="complete"'
	already_imaged_table_id = 'horizontal_already_imaged_table'
	table_already_imaged = dynamic_imaging_management_table(contents_already_imaged,
		table_id=already_imaged_table_id,
		sort_by=sort,sort_reverse=reverse)
	
	return render_template('imaging/image_management.html',table_being_imaged=table_being_imaged,
		table_ready_to_image=table_ready_to_image,
		table_on_deck=table_on_deck,table_already_imaged=table_already_imaged)

@imaging.route("/imaging/imaging_entry/<username>/<experiment_name>/<sample_name>",methods=['GET','POST'])
@logged_in
@logged_in_as_imager
@check_clearing_completed
def imaging_entry(username,experiment_name,sample_name): 
	form = ImagingForm(request.form)

	sample_contents = db_lightsheet.Sample() & f'experiment_name="{experiment_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"'								
	if not sample_contents:
		flash(f"""Request must exist for experiment_name={experiment_name}, 
			sample_name={sample_name} before imaging can be done. 
			Please submit a new request for this experiment first. """,'danger')
		return redirect(url_for('experiments.new_exp'))
	''' If imaging is already complete (from before), then dont change imaging_progress '''
	imaging_progress = sample_contents.fetch1('imaging_progress')
	logger.info(imaging_progress)
	if imaging_progress == 'complete':
		logger.info("Imaging already complete but accessing the imaging entry page anyway")
		flash("Imaging is already complete for this sample. "
			"This page is read only and hitting submit will do nothing",'warning')
	else:
		dj.Table._update(sample_contents,'imaging_progress','in progress')

	channel_contents = (db_lightsheet.Sample.ImagingChannel() & f'experiment_name="{experiment_name}"' & \
	 		f'username="{username}"' & f'sample_name="{sample_name}"')
	channel_content_dict_list = channel_contents.fetch(as_dict=True)
	logger.info(channel_content_dict_list)
	if request.method == 'POST':
		logger.info("Post request")
		if form.validate_on_submit():
			logger.info("form validated")
			imaging_progress = sample_contents.fetch1('imaging_progress')
			if imaging_progress == 'complete':
				logger.info("Imaging is already complete so hitting the done button again did nothing")
				return redirect(url_for('experiments.exp',username=username,
				experiment_name=experiment_name,sample_name=sample_name))
			""" Loop through the channels in the form  
			and update the existing table entry """
			for form_channel_dict in form.channels.data:
				logger.info(form_channel_dict)
				channel_name = form_channel_dict['channel_name']
				channel_content = channel_contents & f'channel_name="{channel_name}"'
				dj.Table._update(channel_content,'image_resolution_used',form_channel_dict['image_resolution_used'])
			correspondence_email = (db_lightsheet.Experiment() &\
			 f'experiment_name="{experiment_name}"').fetch1('correspondence_email')
			path_to_data = f'/jukebox/LightSheetData/lightserv_testing/{username}/{experiment_name}/{sample_name}'
			msg = Message('Lightserv automated email',
			          sender='lightservhelper@gmail.com',
			          recipients=['ahoag@princeton.edu']) # keep it to me while in DEV phase
			msg.body = ('Hello!\n    This is an automated email sent from lightserv, the Light Sheet Microscopy portal. '
						'The raw data for your experiment:\n'
						f'experiment_name: "{experiment_name}"\n'
						f'sample_name: "{sample_name}"\n'
						f'are now available on bucket here: {path_to_data}')
			# mail.send(msg)
			flash(f"""Imaging is complete. An email has been sent to {correspondence_email} 
				informing them that their raw data is now available on bucket.
				The processing pipeline is now ready to run. ""","success")
			dj.Table._update(sample_contents,'imaging_progress','complete')
			return redirect(url_for('experiments.exp',username=username,
				experiment_name=experiment_name,sample_name=sample_name))
		else:
			logger.info("Not validated")
			logger.info(form.errors)
			for channel in form.channels:
				print(channel.tiling_scheme.errors)
	elif request.method == 'GET': # get request

		while len(form.channels) > 0:
			form.channels.pop_entry()
		for channel_content_dict in channel_content_dict_list:
			logger.info("In loop")
			form.channels.append_entry()
			channel_name = channel_content_dict['channel_name']
			logger.info(form.channels.data)
			form.channels[-1].channel_name.data = channel_name
			logger.info(form.channels.data)


	sample_dict = sample_contents.fetch1()
	imaging_table = ImagingTable(sample_contents)


	return render_template('imaging/imaging_entry.html',form=form,
		channel_content_dict_list=channel_content_dict_list,sample_dict=sample_dict,imaging_table=imaging_table)
