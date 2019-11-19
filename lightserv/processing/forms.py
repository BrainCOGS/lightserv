from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
					 SelectField, BooleanField, IntegerField,
					 DecimalField, FieldList,FormField,HiddenField)
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Email, Optional
from wtforms.widgets import html5, HiddenInput


class ChannelForm(FlaskForm):
	""" A form that is used in ImagingForm() via a FormField Fieldlist
	so I dont have to write the imaging parameters out for each channel
	"""
	channel_name = HiddenField('Channel name')
	image_resolution_used = SelectField('Select image resolution used:', choices=[('1.3x','1.3x'),
	('4x','4x'),('1.1x','1.1x'),('2x','2x')],validators=[InputRequired()]) 
	tiling_scheme = StringField('Tiling scheme (e.g. 3x3) -- n_rows x n_columns --',default='1x1')
	tiling_overlap = DecimalField('Tiling overlap (number between 0.0 and 1.0; leave as default if unsure or not using tiling)',
		places=2,validators=[Optional()],default=0.1) 
	z_resolution = IntegerField('Z resolution (microns)',
		widget=html5.NumberInput(),validators=[InputRequired()],default=10)
	number_of_z_planes = IntegerField('Number of z planes',
		widget=html5.NumberInput(),validators=[InputRequired()],default=1000)

	def validate_tiling_overlap(self,tiling_overlap):
		try:
			if tiling_overlap.data < 0 or tiling_overlap.data >= 1:
				raise ValidationError("Tiling overlap must be between 0.0 and 1.0")
		except:
			raise ValidationError("Tiling overlap must be a number between 0.0 and 1.0")

	def validate_tiling_scheme(self,tiling_scheme):
		if len(tiling_scheme.data) != 3:
			raise ValidationError("Tiling scheme is not in correct format."
								  " Make sure it is like: 1x1 with no spaces.")
		try:
			n_rows = int(tiling_scheme.data.lower().split('x')[0])
			n_columns = int(tiling_scheme.data.lower().split('x')[1])
		except:
			raise ValidationError("Tiling scheme is not in correct format."
								  " Make sure it is like: 1x1 with no spaces.")	
		if self.image_resolution_used.data in ['1.1x','1.3x']:
			if n_rows > 2 or n_columns > 2:
				raise ValidationError("Tiling scheme must not exceed 2x2 for this resolution")
		elif self.image_resolution_used.data in ['2x','4x']:
			if n_rows > 4 or n_columns > 4:
				raise ValidationError("Tiling scheme must not exceed 4x4 for this resolution")

	def validate_z_resolution(self,z_resolution):
		if z_resolution.data < 2:
			raise ValidationError("z_resolution must be a positive number larger than 2 microns")
		elif z_resolution.data > 1000:
			raise ValidationError("Are you sure your z_resolution is >1000 microns?")

	def validate_number_of_z_planes(self,number_of_z_planes):
		if number_of_z_planes.data < 0:
			raise ValidationError("The number of z planes must be a positive number")
		elif number_of_z_planes.data > 5500:
			raise ValidationError("Are you sure you have >5500 z planes?")
	

class StartProcessingForm(FlaskForm):
	""" The form for requesting to start the data processing """
	max_number_of_channels=4
	notes_from_processing = TextAreaField("Note down anything additional about the processing"
									   " that you would like recorded.")

	channels = FieldList(FormField(ChannelForm),min_entries=0,max_entries=max_number_of_channels)
	submit = SubmitField('Start the processing pipeline for this sample')	