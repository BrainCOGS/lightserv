from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup)
from lightserv import db_lightsheet

from lightserv.main.utils import (logged_in, logged_in_as_clearer,
								  logged_in_as_imager,check_clearing_completed)
from lightserv.tables import ImagingTable
from .forms import ImagingForm
import numpy as np
import datajoint as dj
import re
import datetime

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

	if form.validate_on_submit():
		logger.info("form validated")
		dj.Table._update(sample_contents,'imaging_progress','complete')
		correspondence_email = (db_lightsheet.Experiment() &\
		 f'experiment_name="{experiment_name}"').fetch1('correspondence_email')
		path_to_data = f'/jukebox/LightSheetData/lightserv_testing/{username}/{experiment_name}/{sample_name}'
		msg = Message('Lightserv automated email',
                  sender='lightservhelper@gmail.com',
                  recipients=['ahoag@princeton.edu']) # keep it to me while in DEV phase
	    msg.body = f"""The raw data for your experiment named "{experiment_name}", sample named 
	    "{sample_name}" are now available on bucket here: {path_to_data}
	    """
	    mail.send(msg)
		flash(f"""Imaging is complete. An email has been sent to {correspondence_email} 
			saying their raw data is now available.
			The processing pipeline is now ready to run. ""","success")
		return redirect(url_for('experiments.exp',username=username,
			experiment_name=experiment_name,sample_name=sample_name))

	dj.Table._update(sample_contents,'imaging_progress','in progress')

	sample_dict = sample_contents.fetch1()
	imaging_table = ImagingTable(sample_contents)
	''' Now figure out which channels need to be imaged '''
	used_channels = []
	for channel in ['488','555','647','790']:
		imaging_modes = [key for key in sample_dict.keys() if key[0:10] == 'channel%s' % channel]
		for mode in imaging_modes:
			val = sample_dict[mode]
			if val == 1:
				used_channels.append(channel)
				continue

	return render_template('imaging/imaging_entry.html',form=form,
		used_channels=used_channels,sample_dict=sample_dict,imaging_table=imaging_table)