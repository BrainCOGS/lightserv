from flask import current_app
from flask_wtf import FlaskForm
from wtforms import (SubmitField, TextAreaField, SelectField, FieldList, FormField,
	StringField, DecimalField, IntegerField, HiddenField, BooleanField,
	FloatField)
from wtforms.validators import (DataRequired, Length, InputRequired, ValidationError, 
	Optional)
from wtforms.widgets import html5
import os, glob

""" For imaging setup """

class ImagingSetupForm(FlaskForm):
	""" The form for entering imaging information """
	image_together = BooleanField('Check if using same setup for all samples',default=True)
	sample_dropdown = SelectField('Select sample to image',choices=[],validators=[Optional()])
	submit = SubmitField('Submit')

""" For the imaging entry form """

class ChannelForm(FlaskForm):
	""" A form that is used in ImagingForm() via a FormField Fieldlist
	so I dont have to write the imaging parameters out for each channel
	"""
	channel_name = HiddenField('Channel name')
	image_resolution = HiddenField('Image resolution')
	zoom_body_magnification = DecimalField('Zoom body magnification',default=1.0,validators=[Optional()])
	image_orientation = SelectField('Image orientation',choices=[('sagittal','sagittal'),('coronal','coronal'),
				 ('horizontal','horizontal')],default='horizontal',validators=[InputRequired()])
	left_lightsheet_used = BooleanField('Left',default=False)
	right_lightsheet_used = BooleanField('Right',default=False)
	tiling_scheme = StringField('Tiling scheme (e.g. 3x3) -- n_rows x n_columns --',validators=[InputRequired()])
	tiling_overlap = StringField('Tiling overlap (number between 0.0 and 1.0; leave as default if unsure or not using tiling)',
		validators=[Optional()]) 
	z_step = StringField('Z resolution (microns)',validators=[InputRequired()])
	number_of_z_planes = IntegerField('Number of z planes',
		widget=html5.NumberInput(),validators=[InputRequired()])
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
	notes_for_clearer = TextAreaField('Notes left for clearer:')
	notes_for_imager = TextAreaField('Notes left for imager:')

	change_resolution = BooleanField("Change image resolution?",default=False)
	new_image_resolution = SelectField('Select the new image resolution you want to use:', 
		choices=[('1.3x','1.3x'),
	('4x','4x'),('1.1x','1.1x'),('2x','2x')],validators=[Optional()])
	update_resolution_button = SubmitField('Update')
	new_channel_dropdown = SelectField("Add additional channel?",choices=[('488','488'),
	('555','555'),('647','647'),('790','790')],validators=[Optional()])
	new_channel_purpose = SelectField("What type of imaging?",choices=[('registration','registration'),
	('injection_detection','injection_detection'),('probe_detection','probe_detection'),
	('cell_detection','cell_detection'),
	('generic_imaging','generic_imaging')],validators=[Optional()])
	new_channel_button = SubmitField("Add channel")
	channel_forms = FieldList(FormField(ChannelForm),min_entries=0,max_entries=max_number_of_channels)

class ImagingForm(FlaskForm):
	""" The form for entering imaging information """
	username = HiddenField('username')
	request_name = HiddenField('request_name')
	sample_name = HiddenField('sample_name')
	imaging_request_number = HiddenField('imaging_request_number')

	max_number_of_image_resolutions = 4 
	notes_from_imaging = TextAreaField("Note down anything additional about the imaging"
									   " of this sample that you would like recorded:")
	image_resolution_forms = FieldList(FormField(ImageResolutionForm),min_entries=0,max_entries=max_number_of_image_resolutions)
	submit = SubmitField('Click when imaging is complete and data are on bucket')

	def validate_image_resolution_forms(self,image_resolution_forms):
		""" Make sure that for each channel within 
		an image resolution form, there is at least 
		one light sheet selected. 

		Also make sure that each rawdata folder has the correct number 
		of files given the number of z planes, tiling scheme and number of 
		lightsheets reported by the user.

		Also make sure that every channel at the same resolution
		has the same tiling parameters, i.e. tiling scheme, tiling overlap
		Number of z planes can differ because the code does not actually
		use this information and we store it correctly in the db.
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
				tiling_scheme = channel_dict['tiling_scheme']
				n_rows = int(tiling_scheme.lower().split('x')[0])
				n_columns = int(tiling_scheme.lower().split('x')[1])
				""" First check that at least one of the 
				light sheets (left or right) was selected """
				if not (left_lightsheet_used or right_lightsheet_used):
					raise ValidationError(f"Image resolution: {this_image_resolution}, Channel: {channel_name}: "
										   "At least one light sheet needs to be selected")
				""" Now handle the number of raw data files for this channel """

				if rawdata_subfolder in subfolder_dict.keys():
					subfolder_dict[rawdata_subfolder].append(channel_dict)
				else:
					subfolder_dict[rawdata_subfolder] = [channel_dict]
				
				channel_index = len(subfolder_dict[rawdata_subfolder]) - 1

				rawdata_fullpath = os.path.join(current_app.config['DATA_BUCKET_ROOTPATH'],
						self.username.data,self.request_name.data,self.sample_name.data,
						f'imaging_request_{self.imaging_request_number.data}',
						'rawdata',f'resolution_{this_image_resolution}',rawdata_subfolder) 
				number_of_rawfiles_expected = number_of_z_planes*(left_lightsheet_used+right_lightsheet_used)*n_rows*n_columns
				""" calculate the number we find. We have to be careful here
				because the raw data filenames will include C00 if there
				is only one light sheet used, regardless of whether it is
				left or right. If both are used,
				then the left lightsheet files always have C00 in filenames
				and right lightsheet files always have C01 in filenames. """
				number_of_rawfiles_found = 0
				if left_lightsheet_used and right_lightsheet_used:
					number_of_rawfiles_found_left_lightsheet = \
						len(glob.glob(rawdata_fullpath + f'/*RawDataStack*_C00_*Filter000{channel_index}*'))	
					number_of_rawfiles_found += number_of_rawfiles_found_left_lightsheet
					number_of_rawfiles_found_right_lightsheet = \
						len(glob.glob(rawdata_fullpath + f'/*RawDataStack*_C01_*Filter000{channel_index}*'))	
					number_of_rawfiles_found += number_of_rawfiles_found_right_lightsheet
				else:
					# doesn't matter if its left or right lightsheet. Since there is only one, their glob patterns will be identical
					number_of_rawfiles_found = \
						len(glob.glob(rawdata_fullpath + f'/*RawDataStack*_C00_*Filter000{channel_index}*'))	

				if number_of_rawfiles_found != number_of_rawfiles_expected:
					error_str = (f"You entered that for channel: {channel_name} there should be {number_of_rawfiles_expected} files, "
						  f"but found {number_of_rawfiles_found} in raw data folder: "
						  f"{rawdata_fullpath}")
					raise ValidationError(error_str)
			
			""" Now make sure imaging parameters are the same for all channels within the same subfolder """
			common_key_list = ['image_orientation','left_lightsheet_used',
				'right_lightsheet_used','tiling_scheme','tiling_overlap',
				'z_step','number_of_z_planes']
			all_tiling_schemes = [] # also keep track of tiling parameters for all subfolders at this resolution
			all_tiling_overlaps = [] # also keep track of tiling parameters for all subfolders at this resolution
			for subfolder in subfolder_dict.keys():
				channel_dict_list = subfolder_dict[subfolder]
				for d in channel_dict_list:
					all_tiling_schemes.append(d['tiling_scheme'])
					all_tiling_overlaps.append(d['tiling_overlap'])
				if not all([list(map(d.get,common_key_list)) == \
					list(map(channel_dict_list[0].get,common_key_list)) \
						for d in channel_dict_list]):
					
					raise ValidationError(f"Subfolder: {subfolder}. "
										  "Tiling and imaging parameters must be identical"
										  " for all channels in the same subfolder. Check your entries.")

			""" Now make sure tiling parameters are same for all channels at each resolution """
			if (not all([x==all_tiling_overlaps[0] for x in all_tiling_overlaps]) 
			or (not all([x==all_tiling_schemes[0] for x in all_tiling_schemes]))):
				raise ValidationError("All tiling parameters must be the same for each channel of a given resolution")

""" For the imaging BATCH entry form """

class ChannelBatchForm(FlaskForm):
	""" A form that is used in ImagingForm() via a FormField Fieldlist
	so I dont have to write the imaging parameters out for each channel
	"""
	channel_name = HiddenField('Channel name')
	image_resolution = HiddenField('Image resolution')
	zoom_body_magnification = DecimalField('Zoom body magnification',default=1.0,validators=[Optional()])
	image_orientation = SelectField('Image orientation',choices=[('sagittal','sagittal'),('coronal','coronal'),
				 ('horizontal','horizontal')],default='horizontal',validators=[InputRequired()])
	left_lightsheet_used = BooleanField('Left',default=False)
	right_lightsheet_used = BooleanField('Right',default=False)
	tiling_scheme = StringField('Tiling scheme (e.g. 3x3) -- n_rows x n_columns --',validators=[InputRequired()])
	tiling_overlap = StringField('Tiling overlap (number between 0.0 and 1.0; leave as default if unsure or not using tiling)',
		validators=[Optional()]) 
	z_step = StringField('Z resolution (microns)',validators=[InputRequired()])
	# number_of_z_planes = IntegerField('Number of z planes',
	# 	widget=html5.NumberInput(),validators=[InputRequired()])
	# rawdata_subfolder = TextAreaField('channel subfolder',validators=[InputRequired()])

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

class ImageBatchResolutionForm(FlaskForm):
	""" A form for each image resolution that a user picks """
	max_number_of_channels = 4
	image_resolution = HiddenField('image resolution')
	notes_for_clearer = TextAreaField('Notes left for clearer:')
	notes_for_imager = TextAreaField('Notes left for imager:')

	change_resolution = BooleanField("Change image resolution?",default=False)
	new_image_resolution = SelectField('Select the new image resolution you want to use:', 
		choices=[('1.3x','1.3x'),
	('4x','4x'),('1.1x','1.1x'),('2x','2x')],validators=[Optional()])
	update_resolution_button = SubmitField('Update')
	new_channel_dropdown = SelectField("Add additional channel?",choices=[('488','488'),
	('555','555'),('647','647'),('790','790')],validators=[Optional()])
	new_channel_purpose = SelectField("What type of imaging?",choices=[('registration','registration'),
	('injection_detection','injection_detection'),('probe_detection','probe_detection'),
	('cell_detection','cell_detection'),
	('generic_imaging','generic_imaging')],validators=[Optional()])
	new_channel_button = SubmitField("Add channel")
	channel_forms = FieldList(FormField(ChannelBatchForm),min_entries=0,max_entries=max_number_of_channels)

class ImagingBatchForm(FlaskForm):
	""" The form for entering imaging information """
	username = HiddenField('username')
	request_name = HiddenField('request_name')
	sample_name = HiddenField('sample_name')
	imaging_request_number = HiddenField('imaging_request_number')

	max_number_of_image_resolutions = 4 
	max_number_of_samples = 50 # per request and therefore per imaging batch
	notes_from_imaging = TextAreaField("Note down anything additional about the imaging"
									   " that you would like recorded:")
	image_resolution_batch_forms = FieldList(FormField(ImageBatchResolutionForm),min_entries=0,max_entries=max_number_of_image_resolutions)
	apply_batch_parameters_button = SubmitField('Apply these parameters to all samples') # setting default=True does not do anything, so I have to do it in the view function:  https://github.com/lepture/flask-wtf/issues/362
	sample_forms = FieldList(FormField(ImagingForm),min_entries=0,max_entries=max_number_of_samples)

	submit = SubmitField('Click when imaging is complete and data are on bucket')

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
				 ('horizontal','horizontal')],default='sagittal',validators=[Optional()])
	channels = FieldList(FormField(ChannelRequestForm),min_entries=4,max_entries=4)
	notes_for_imager = TextAreaField('''Note here why you are requesting additional imaging. Also include any special notes for imaging 
		(e.g. z step size, exposure time, suggested tiling scheme -- make sure to specify which channel) -- max 1024 characters --''',
		validators=[Length(max=1024)])

	notes_for_processor = TextAreaField('''Special notes for processing 
		 -- max 1024 characters --''',validators=[Length(max=1024)])

	atlas_name = SelectField('Atlas for registration',
		choices=[('allen_2017','Allen atlas (2017)'),('allen_2011','Allen atlas (pre-2017)'),
				 ('princeton_mouse_atlas','Princeton Mouse Atlas')],validators=[Optional()])

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