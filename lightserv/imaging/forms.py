from flask_wtf import FlaskForm
from wtforms import (SubmitField, TextAreaField, SelectField, FieldList, FormField)
from wtforms.fields.html5 import DateField, DateTimeLocalField
from wtforms.validators import (DataRequired, Length, InputRequired, ValidationError, 
	Optional)

datetimeformat='%Y-%m-%dT%H:%M' # To get form.field.data to work. Does not work with the default (bug)

def OptionalDateField(description='',validators=[]):
	""" A custom field that makes the DateField optional """
	validators.append(Optional())
	field = DateField(description,validators)
	return field

def OptionalDateTimeLocalField(description='',validators=[],format=datetimeformat):
	""" A custom field that makes the DateTimeLocalField optional
	and applies a specific formatting to fix a bug in the default formatting """
	validators.append(Optional())
	field = DateTimeLocalField(description,validators,format=format)
	return field

def ChannelForm(FlaskForm):
	""" A form that is used in ImagingForm() via a FormField Fieldlist
	so I dont have to write the imaging parameters out for each channel
	"""
	image_resolution_used = SelectField('Select image resolution used:', 
		choices=[('1.3x','1.3x'),
	('4x','4x'),('1.1x','1.1x'),('2x','2x')],validators=[InputRequired()]) 
	tiling_scheme = StringField('Tiling scheme (e.g. 3x3) -- n_rows x n_columns --',default='1x1')
	tiling_overlap = DecimalField('Tiling overlap (number between 0.0 and 1.0; leave as default if unsure or not using tiling)',
		places=2,validators=[Optional()],default=0.1) 

	def validate_tiling_overlap(self,tiling_overlap):
		try:
			if tiling_overlap.data < 0 or tiling_overlap.data >= 1:
				raise ValidationError("Tiling overlap must be between 0.0 and 1.0")
		except:
			raise ValidationError("Tiling overlap must be a number between 0.0 and 1.0")

	def validate_tiling_scheme(self,tiling_scheme):
		if len(tiling_scheme) != 3:
			raise ValidationError("Tiling scheme is not in correct format."
								  " Make sure it is like: 1x1 with no spaces.")
		try:
			n_rows = int(tiling_scheme.lower().split('x')[0])
			n_columns = int(tiling_scheme.lower().split('x')[0])
		except:
			raise ValidationError("Tiling scheme is not in correct format."
								  " Make sure it is like: 2x3 with no spaces.")	
		if self.image_resolution_used in ['1.1x','1.3x']:
			if n_rows > 2 or n_columns > 2:
				raise ValidationError("Tiling scheme must not exceed 2x2 for this resolution")
		elif self.image_resolution_used in ['2x','4x']:
			if n_rows > 4 or n_columns > 4:
				raise ValidationError("Tiling scheme must not exceed 4x4 for this resolution")

		
		

class ImagingForm(FlaskForm):
	""" The form for entering imaging information """
	max_number_of_channels = 4 

	imaging_notes = TextAreaField('Note down anything additional about the imaging that you would recorded')
	channels = FieldList(FormField(ChannelForm),min_entries=0,max_entries=max_number_of_channels)
	submit = SubmitField('Click when imaging is complete and all files are on bucket in the folder above')
