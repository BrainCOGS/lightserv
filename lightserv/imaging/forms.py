from flask import current_app
from flask_wtf import FlaskForm
from wtforms import (SubmitField, TextAreaField, SelectField, FieldList, FormField,
	StringField, DecimalField, IntegerField, HiddenField, BooleanField)
from wtforms.validators import (DataRequired, Length, InputRequired, ValidationError, 
	Optional)
from wtforms.widgets import html5
import os, glob

""" For the imaging entry form """

class ChannelForm(FlaskForm):
	""" A form that is used in ImagingForm() via a FormField Fieldlist
	so I dont have to write the imaging parameters out for each channel
	"""
	channel_name = HiddenField('Channel name')
	image_resolution = HiddenField('Image resolution')
	image_orientation = SelectField('Image orientation',choices=[('sagittal','sagittal'),('coronal','coronal'),
				 ('horizontal','horizontal')],default='sagittal',validators=[InputRequired()])
	left_lightsheet_used = BooleanField('Left',default=False)
	right_lightsheet_used = BooleanField('Right',default=False)
	tiling_scheme = StringField('Tiling scheme (e.g. 3x3) -- n_rows x n_columns --',default='1x1')
	tiling_overlap = DecimalField('Tiling overlap (number between 0.0 and 1.0; leave as default if unsure or not using tiling)',
		places=2,validators=[Optional()],default=0.1) 
	z_step = IntegerField('Z resolution (microns)',
		widget=html5.NumberInput(),validators=[InputRequired()],default=10)
	number_of_z_planes = IntegerField('Number of z planes',
		widget=html5.NumberInput(),validators=[InputRequired()],default=657)
	rawdata_subfolder = TextAreaField('channel subfolder',validators=[InputRequired()])

	def validate_tiling_overlap(self,tiling_overlap):
		try:
			fl_val = float(tiling_overlap.data)
		except:
			raise ValidationError("Tiling overlap must be a number between 0.0 and 1.0")
		if tiling_overlap.data < 0.0 or tiling_overlap.data >= 1.0:
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

	def validate_z_step(self,z_step):
		if z_step.data < 2:
			raise ValidationError("z_step must be a positive number larger than 2 microns")
		elif z_step.data > 1000:
			raise ValidationError("z_step greater than 1000 microns is not supported by the microscope.")

	def validate_number_of_z_planes(self,number_of_z_planes):
		if number_of_z_planes.data <= 0:
			raise ValidationError("The number of z planes must be a positive number")
		elif number_of_z_planes.data > 5500:
			raise ValidationError("More than 5500 z planes is not supported by the microscope.")

class ImageResolutionForm(FlaskForm):
	""" A form for each image resolution that a user picks """
	max_number_of_channels = 4
	image_resolution = HiddenField('image resolution')
	notes_for_imager = TextAreaField('Notes for imager:')
	channel_forms = FieldList(FormField(ChannelForm),min_entries=0,max_entries=max_number_of_channels)
	
class ImagingForm(FlaskForm):
	""" The form for entering imaging information """
	username = HiddenField('username')
	request_name = HiddenField('request_name')
	sample_name = HiddenField('sample_name')
	imaging_request_number = HiddenField('imaging_request_number')

	max_number_of_image_resolutions = 4 
	notes_from_imaging = TextAreaField("Note down anything additional about the imaging"
									   " that you would like recorded")
	image_resolution_forms = FieldList(FormField(ImageResolutionForm),min_entries=0,max_entries=max_number_of_image_resolutions)
	submit = SubmitField('Click when imaging is complete and data are on bucket')

	def validate_image_resolution_forms(self,image_resolution_forms):
		""" Make sure that for each channel within 
		an image resolution form, there is at least 
		one light sheet selected. 

		Also make sure that each rawdata folder has the correct number 
		of files that the imager reported there was.
		"""

		for image_resolution_dict in self.image_resolution_forms.data:
			subfolder_dict = {}
			this_image_resolution = image_resolution_dict['image_resolution']
			for channel_dict in image_resolution_dict['channel_forms']:
				channel_name = channel_dict['channel_name']
				left_lightsheet_used = channel_dict['left_lightsheet_used']
				right_lightsheet_used = channel_dict['right_lightsheet_used']
				number_of_z_planes = channel_dict['number_of_z_planes']
				rawdata_subfolder = channel_dict['rawdata_subfolder']
				""" First check that at least one of the 
				light sheets (left or right) was selected """
				if not (left_lightsheet_used or right_lightsheet_used):
					raise ValidationError(f"Image resolution: {this_image_resolution}, Channel: {channel_name}: "
										   "At least one light sheet needs to be selected")
				""" Now handle the number of raw data files for this channel """
				if rawdata_subfolder in subfolder_dict.keys():
					subfolder_dict[rawdata_subfolder].append(channel_name)
				else:
					subfolder_dict[rawdata_subfolder] = [channel_name]
				channel_index = subfolder_dict[rawdata_subfolder].index(channel_name)

				rawdata_fullpath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
						self.username.data,self.request_name.data,self.sample_name.data,
						f'imaging_request_{self.imaging_request_number.data}',
						'rawdata',rawdata_subfolder) 

				number_of_rawfiles_expected = number_of_z_planes*(left_lightsheet_used+right_lightsheet_used)
				number_of_rawfiles_found = len(glob.glob(rawdata_fullpath + f'/*RawDataStack*Filter000{channel_index}*'))				
				if number_of_rawfiles_found != number_of_rawfiles_expected:
					error_str = (f"You entered that for channel: {channel_name} there should be {number_of_rawfiles_expected} files, "
						  f"but found {number_of_rawfiles_found} in raw data folder: "
						  f"{rawdata_fullpath}","danger")
					raise ValidationError(error_str)

""" For new imaging requests """

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
	final_orientation = SelectField('Output orientation',
		choices=[('sagittal','sagittal'),('coronal','coronal'),
				 ('horizontal','horizontal')],default='sagittal',validators=[InputRequired()])
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
	species = HiddenField('species') 
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
			if 'registration' in selected_imaging_modes and resolution_form_dict['final_orientation'] != 'sagittal':
				raise ValidationError(f"Image resolution table: {image_resolution}:"
					  						f" Output orientation must be sagittal since registration was selected")
			elif self.species.data != 'mouse' and \
					  ('injection_detection' in selected_imaging_modes or \
					  'probe_detection' in selected_imaging_modes  or \
					  'cell_detection' in selected_imaging_modes or \
					  'registration' in selected_imaging_modes):
				raise ValidationError(f"Only generic imaging is currently available for species: {self.species.data}")
			elif ('injection_detection' in selected_imaging_modes or \
				  'probe_detection' in selected_imaging_modes  or \
				  'cell_detection' in selected_imaging_modes) and \
				  'registration' not in selected_imaging_modes:
				raise ValidationError(f"Image resolution table: {image_resolution}."
										f" You must select a registration channel"
										 " when requesting any of the detection channels")

		if self.new_image_resolution_form_submit.data == True:
			
			if self.image_resolution_forsetup.data in current_image_resolutions_rendered:
				raise ValidationError(f"You tried to make a table for image_resolution: {image_resolution}"
									  f", but that resolution has already been picked")