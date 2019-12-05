from flask import current_app
from flask_wtf import FlaskForm
from wtforms import (SubmitField, TextAreaField, SelectField, FieldList, FormField,
	StringField, DecimalField, IntegerField, HiddenField, BooleanField)
from wtforms.fields.html5 import DateField, DateTimeLocalField
from wtforms.validators import (DataRequired, Length, InputRequired, ValidationError, 
	Optional)
from wtforms.widgets import html5


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

class ChannelForm(FlaskForm):
	""" A form that is used in ImagingForm() via a FormField Fieldlist
	so I dont have to write the imaging parameters out for each channel
	"""
	channel_name = HiddenField('Channel name')
	image_resolution = HiddenField('Image resolution')
	tiling_scheme = StringField('Tiling scheme (e.g. 3x3) -- n_rows x n_columns --',default='1x1')
	tiling_overlap = DecimalField('Tiling overlap (number between 0.0 and 1.0; leave as default if unsure or not using tiling)',
		places=2,validators=[Optional()],default=0.1) 
	z_resolution = IntegerField('Z resolution (microns)',
		widget=html5.NumberInput(),validators=[InputRequired()],default=10)
	number_of_z_planes = IntegerField('Number of z planes',
		widget=html5.NumberInput(),validators=[InputRequired()],default=1000)
	rawdata_subfolder = TextAreaField('channel subfolder',validators=[InputRequired()])

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
		if self.image_resolution.data in ['1.1x','1.3x']:
			if n_rows > 2 or n_columns > 2:
				raise ValidationError("Tiling scheme must not exceed 2x2 for this resolution")
		elif self.image_resolution.data in ['2x','4x']:
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

class ImageResolutionForm(FlaskForm):
	""" A form for each image resolution that a user picks """
	max_number_of_channels = 4
	image_resolution = HiddenField('image resolution')
	channel_forms = FieldList(FormField(ChannelForm),min_entries=0,max_entries=max_number_of_channels)
	
class ImagingForm(FlaskForm):
	""" The form for entering imaging information """
	max_number_of_image_resolutions = 4 
	notes_from_imaging = TextAreaField("Note down anything additional about the imaging"
									   " that you would like recorded")
	image_resolution_forms = FieldList(FormField(ImageResolutionForm),min_entries=0,max_entries=max_number_of_image_resolutions)
	submit = SubmitField('Click when imaging is complete and data are on bucket')

class ChannelRequestForm(FlaskForm):
	""" Used by other forms in a FieldList """
	channel_name = HiddenField('Channel Name')
	registration = BooleanField('Registration',default=False)
	injection_detection = BooleanField('Injection Detection',default=False)
	probe_detection = BooleanField('Probe Detection',default=False)
	cell_detection = BooleanField('Cell Detection',default=False)
	generic_imaging = BooleanField('Generic imaging',default=False)

class ImageResolutionRequestForm(FlaskForm):
	""" A form used in a FieldList for each image resolution that a user picks 
	in NewImagingRequestForm """
	image_resolution = HiddenField('image resolution')
	channels = FieldList(FormField(ChannelRequestForm),min_entries=4,max_entries=4)
	notes_for_imager = TextAreaField('''Note here why you are requesting additional imaging. Also include any special notes for imaging 
		(e.g. z step size, exposure time, suggested tiling scheme -- make sure to specify which channel) -- max 1024 characters --''',
		validators=[Length(max=1024)])

	notes_for_processor = TextAreaField('''Special notes for processing 
		 -- max 1024 characters --''',validators=[Length(max=1024)])

	atlas_name = SelectField('Atlas for registration',
		choices=[('allen_2017','Allen atlas (2017)'),('allen_2011','Allen atlas (pre-2017)'),
				 ('princeton_mouse_atlas','Princeton Mouse Atlas')],validators=[InputRequired()])


class NewImagingRequestForm(FlaskForm):
	""" The form for entering imaging information """
	max_number_of_image_resolutions = 4 
	self_imaging = BooleanField('Check if you plan to do the imaging yourself',default=False)
	image_resolution_forsetup = SelectField('Select an image resolution you want to use:', 
		choices=[('1.3x','1.3x'),
	('4x','4x'),('1.1x','1.1x'),('2x','2x')],default='')   

	image_resolution_forms = FieldList(FormField(ImageResolutionRequestForm),min_entries=0,max_entries=max_number_of_image_resolutions)

	new_image_resolution_form_submit = SubmitField('Set up imaging parameters') # renders a new resolution table
	submit = SubmitField("Submit request") # final submit button


	def validate_image_resolution_forms(self,image_resolution_forms):

		current_image_resolutions_rendered = []
		if image_resolution_forms.data == [] and self.submit.data == True:
			raise ValidationError("You must set up the imaging parameters for at least one image resolution")
		for resolution_form_dict in image_resolution_forms.data:
			image_resolution = resolution_form_dict['image_resolution']
			current_image_resolutions_rendered.append(image_resolution)
			channel_dict_list = resolution_form_dict['channels']
			selected_imaging_modes = [key for channel_dict in channel_dict_list \
				for key in channel_dict if key in current_app.config['IMAGING_MODES'] and channel_dict[key] == True]
			if selected_imaging_modes == []:
				raise ValidationError(f"The image resolution table: {image_resolution}"
									  f" is empty. Please select at least one option. ")
			elif ('injection_detection' in selected_imaging_modes or \
				  'probe_detection' in selected_imaging_modes  or \
				  'cell_detection' in selected_imaging_modes) and \
				  'registration' not in selected_imaging_modes:
				  raise ValidationError(f"Image resolution table: {image_resolution}."
				  						f" You must select a registration channel"
				  						 " when requesting any of the 'detection' channels")

		if self.new_image_resolution_form_submit.data == True:
			
			if self.image_resolution_forsetup.data in current_image_resolutions_rendered:
				raise ValidationError(f"You tried to make a table for image_resolution {image_resolution}"
									  f", but that resolution has already been picked")