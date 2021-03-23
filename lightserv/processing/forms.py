from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
					 SelectField, BooleanField, IntegerField,
					 DecimalField, FieldList,FormField,HiddenField)
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Email, Optional
from wtforms.widgets import html5, HiddenInput

from flask import current_app
import os

class ChannelProcessingForm(FlaskForm):
	channel_name = HiddenField('Channel name')
	ventral_up = HiddenField('Dorsal up or ventral up?')
	channel_purposes_str = HiddenField('Channel purposes')
	registration = BooleanField('Registration',default=False)
	injection_detection = BooleanField('Injection Detection',default=False)
	probe_detection = BooleanField('Probe Detection',default=False)
	cell_detection = BooleanField('Cell Detection',default=False)
	generic_imaging = BooleanField('Generic imaging',default=False)
	
class SubProcessingForm(FlaskForm):
	""" A form that contains channels of the same resolution
	and same orientation. For example there could be four total channels
	in a processing request but two are 1.3x 488, 555 dorsal up and the 
	other two are 1.3x 488, 555 ventral up """
	max_number_of_channels = 4
	atlas_name = SelectField('Choose atlas for registration:',
		choices=[('allen_2017','Allen atlas (2017)'),('allen_2011','Allen atlas (pre-2017)'),
				 ('princeton_mouse_atlas','Princeton Mouse Atlas'),
				 ('paxinos','Franklin-Paxinos Mouse Brain Atlas')],validators=[Optional()],default='allen_2017')
	image_resolution = HiddenField('Image resolution')
	ventral_up = HiddenField('Dorsal up or ventral up?')
	notes_for_processor = TextAreaField('''Special notes for processing 
		 -- max 1024 characters --''',validators=[Length(max=1024)])
	channel_forms = FieldList(FormField(ChannelProcessingForm),min_entries=0,
		max_entries=max_number_of_channels)
	
class StartProcessingForm(FlaskForm):
	""" The form for requesting to start the data processing """
	max_number_of_resolutions=4
	image_resolution_forms = FieldList(FormField(SubProcessingForm),min_entries=0,
		max_entries=max_number_of_resolutions)
	notes_from_processing = TextAreaField("Note down anything additional about the processing"
									   " that you would like recorded. -- max 1024 characters --",
									   validators=[Length(max=1024)])
	
	submit = SubmitField('Start the processing pipeline for this sample')	

class ChannelPystripeForm(FlaskForm):
	""" A form that contains channels of the same resolution
	and same orientation. For example there could be four total channels
	in a processing request but two are 1.3x 488, 555 dorsal up and the 
	other two are 1.3x 488, 555 ventral up """

	username = HiddenField('username')
	request_name = HiddenField('request name')
	sample_name = HiddenField('sample name')
	imaging_request_number = HiddenField('imaging request number')
	image_resolution = HiddenField('Image resolution')
	channel_name = HiddenField('Channel name')
	pystripe_started = HiddenField('Pipeline started',default=False)
	flat_name = StringField('Flat field filename',default='flat.tiff',validators=[Length(max=64)])
	start_pystripe = SubmitField('Start pystripe')	

	def validate_flat_name(self,flat_name):
		data_bucket_rootpath = current_app.config['DATA_BUCKET_ROOTPATH']
		channel_names = current_app.config['SMARTSPIM_IMAGING_CHANNELS']
		channel_index = channel_names.index(self.channel_name.data)
		flat_name_fullpath = os.path.join(data_bucket_rootpath,self.username.data,
			self.request_name.data,self.sample_name.data,
			f'imaging_request_{self.imaging_request_number.data}',
			'rawdata',f'resolution_{self.image_resolution.data}',
			f'Ex_{self.channel_name.data}_Em_{channel_index}_stitched',flat_name.data)
		print(flat_name_fullpath)
		if not os.path.exists(flat_name_fullpath):
			raise ValidationError(f"No file found named: {flat_name_fullpath}")

class PystripeEntryForm(FlaskForm):
	""" The form for entering flat information and then starting Pystripe """
	max_number_of_channels = 4 # Only have 3.6x imaging so 4 possible channels
	channel_forms = FieldList(FormField(ChannelPystripeForm),min_entries=0,
		max_entries=max_number_of_channels)