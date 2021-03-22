from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
					 SelectField, BooleanField, IntegerField,
					 DecimalField, FieldList,FormField,HiddenField)
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Email, Optional
from wtforms.widgets import html5, HiddenInput

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
	image_resolution = HiddenField('Image resolution')
	channel_name = HiddenField('Channel name')
	pystripe_started = HiddenField('Pipeline started',default=False)
	flat_name = StringField('Flat field filename',default='flat.tiff',validators=[Length(max=64)])
	start_pystripe = SubmitField('Start pystripe')	

	
class PystripeEntryForm(FlaskForm):
	""" The form for entering flat information and then starting Pystripe """
	max_number_of_channels = 4 # Only have 3.6x imaging so 4 possible channels
	channel_forms = FieldList(FormField(ChannelPystripeForm),min_entries=0,
		max_entries=max_number_of_channels)