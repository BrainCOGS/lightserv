from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup, current_app)
from lightserv import db_lightsheet, cel, smtp_server
from .utils import make_info_file
from lightserv.imaging.tables import (ImagingTable, dynamic_imaging_management_table,
	SampleTable, ExistingImagingTable, ImagingChannelTable)
from .forms import ImagingForm, NewImagingRequestForm
import numpy as np
import datajoint as dj
import re
from datetime import datetime
import logging
import glob
import os
from email.message import EmailMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/imaging_utils.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

def make_info_file(volume_size,layer_name,commit=True):
	""" 
	---PURPOSE---
	Make the cloudvolume info file.
	---INPUT---
	volume_size     [Nx,Ny,Nz] in voxels, e.g. [2160,2560,1271]
	layer_name      The name of the layer you want to create
	commit          if True, will write the info/provenance file to disk. 
					if False, just creates it in memory
	"""
	info = CloudVolume.create_new_info(
		num_channels = 1,
		layer_type = 'segmentation', # 'image' or 'segmentation'
		data_type = 'uint16', # 32 bit not necessary for Princeton atlas, but was for Allen atlas 
		encoding = 'raw', # other options: 'jpeg', 'compressed_segmentation' (req. uint32 or uint64)
		resolution = [ 20000, 20000, 20000 ], # X,Y,Z values in nanometers, 20 microns in each dim. 
		voxel_offset = [ 0, 0, 0 ], # values X,Y,Z values in voxels
		chunk_size = [ 1024,1024,1 ], # rechunk of image X,Y,Z in voxels -- only used for downsampling task I think
		volume_size = volume_size, # X,Y,Z size in voxels
	)

	vol = CloudVolume(f'file:///mnt/data/{layer_name}', info=info)
	vol.provenance.description = "Princeton mouse atlas, created in a docker container"
	vol.provenance.owners = ['ahoag@princeton.edu'] # list of contact email addresses
	if commit:
		vol.commit_info() # generates info json file
		vol.commit_provenance() # generates provenance json file
		print("Created CloudVolume info file: ",vol.info_cloudpath)
	return vol