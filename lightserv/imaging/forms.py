from flask import current_app
from flask_wtf import FlaskForm
from wtforms import (SubmitField, TextAreaField, SelectField, FieldList, FormField,
	StringField, DecimalField, IntegerField, HiddenField, BooleanField,
	FloatField)
from wtforms.validators import (DataRequired, Length, InputRequired, ValidationError, 
	Optional)
from wtforms.widgets import html5
import os, glob

""" For the imaging batch entry form """
class ChannelForm(FlaskForm):
	""" A form that is used in ImagingForm() via a FormField Fieldlist
	so I dont have to write the imaging parameters out for each channel
	"""
	channel_name = HiddenField('Channel name')
	image_resolution = HiddenField('Image resolution')
	zoom_body_magnification = DecimalField('Zoom body magnification',default=1.0,validators=[Optional()])
	image_orientation = SelectField('Image orientation',choices=[('sagittal','sagittal'),('coronal','coronal'),
				 ('horizontal','horizontal')],default='horizontal',
				 validators=[Optional()])
	ventral_up = BooleanField('Imaged ventral side up?',validators=[Optional()],
		default=False)
	left_lightsheet_used = BooleanField('Left',default=False)
	right_lightsheet_used = BooleanField('Right',default=False)
	tiling_scheme = StringField('Tiling scheme (e.g. 3x3) -- n_rows x n_columns --')
	tiling_overlap = StringField('Tiling overlap (number between 0.0 and 1.0; leave as default if unsure or not using tiling)',
		validators=[Optional()]) 
	z_step = StringField('Z resolution (microns)',validators=[Optional()])
	number_of_z_planes = IntegerField('Number of z planes',
		widget=html5.NumberInput(),validators=[Optional()])
	rawdata_subfolder = TextAreaField('channel subfolder',validators=[Optional()])
	delete_channel_button = SubmitField("Delete channel")
	add_flipped_channel_button = SubmitField("Add ventral up channel")

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
	max_number_of_channels = 8 # 4 channels and each of them can have a "flipped" copy
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

class ImagingSampleForm(FlaskForm):
	""" The form for entering imaging information """
	username = HiddenField('username')
	request_name = HiddenField('request_name')
	sample_name = HiddenField('sample_name')
	imaging_request_number = HiddenField('imaging_request_number')

	max_number_of_image_resolutions = 4 
	notes_from_imaging = TextAreaField("Note down anything additional about the imaging"
									   " of this sample that you would like recorded:")
	image_resolution_forms = FieldList(FormField(ImageResolutionForm),min_entries=0,max_entries=max_number_of_image_resolutions)
	submit = SubmitField('Click when imaging for this sample is complete and data are on bucket')

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

class ChannelBatchForm(FlaskForm):
	""" A form that is used via a FormField Fieldlist
	so I dont have to write the imaging parameters out for each channel
	"""
	channel_name = HiddenField('Channel name')
	image_resolution = HiddenField('Image resolution')
	zoom_body_magnification = DecimalField('Zoom body magnification',
		default=1.0,validators=[Optional()])
	image_orientation = SelectField('Image orientation',
		choices=[('sagittal','sagittal'),('coronal','coronal'),
				 ('horizontal','horizontal')],default='horizontal',
				 validators=[Optional()])
	ventral_up = BooleanField('Imaged ventral side up?',validators=[Optional()],
		default=False)
	left_lightsheet_used = BooleanField('Left',default=False)
	right_lightsheet_used = BooleanField('Right',default=False)
	tiling_scheme = StringField('Tiling scheme (e.g. 3x3) -- n_rows x n_columns --',
		validators=[Optional()])
	tiling_overlap = StringField('Tiling overlap (number between 0.0 and 1.0; leave as default if unsure or not using tiling)',
		validators=[Optional()]) 
	z_step = StringField('Z resolution (microns)',validators=[Optional()])
	delete_channel_button = SubmitField("Delete channel")
	add_flipped_channel_button = SubmitField("Add ventral up channel")

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
	new_channel_dropdown = SelectField("Add additional channel?",
		choices=[('488','488'),
	('555','555'),('647','647'),('790','790')],validators=[Optional()])
	new_channel_purpose = SelectField("What type of imaging?",choices=[('registration','registration'),
	('injection_detection','injection_detection'),('probe_detection','probe_detection'),
	('cell_detection','cell_detection'),
	('generic_imaging','generic_imaging')],validators=[Optional()])
	new_channel_button = SubmitField("Add channel")
	channel_forms = FieldList(FormField(ChannelBatchForm),min_entries=0,max_entries=max_number_of_channels)

class ImagingBatchForm(FlaskForm):
	""" The form for entering batch imaging information """
	username = HiddenField('username')
	request_name = HiddenField('request_name')
	sample_name = HiddenField('sample_name')
	imaging_request_number = HiddenField('imaging_request_number')

	max_number_of_image_resolutions = 4 
	max_number_of_samples = 50 # per request and therefore per imaging batch
	notes_from_imaging = TextAreaField("Note down anything additional about the imaging"
									   " that you would like recorded:")
	image_resolution_batch_forms = FieldList(
		FormField(ImageBatchResolutionForm),
		min_entries=0,max_entries=max_number_of_image_resolutions)
	apply_batch_parameters_button = SubmitField('Apply these parameters to all samples') 
	sample_forms = FieldList(FormField(ImagingSampleForm),min_entries=0,max_entries=max_number_of_samples)

	submit = SubmitField('Click when done imaging all samples')

""" For follow up imaging requests """

class NewImagingChannelForm(FlaskForm):
	""" Used by other forms in a FieldList """
	channel_name = HiddenField('Channel Name')
	registration = BooleanField('Registration',default=False)
	injection_detection = BooleanField('Injection Detection',default=False)
	probe_detection = BooleanField('Probe Detection',default=False)
	cell_detection = BooleanField('Cell Detection',default=False)
	generic_imaging = BooleanField('Generic imaging',default=False)

class NewImagingImageResolutionForm(FlaskForm):
	""" A form for each image resolution that a user picks """
	image_resolution = HiddenField('image resolution')
	channel_forms = FieldList(FormField(NewImagingChannelForm),min_entries=4,max_entries=4)
	notes_for_imager = TextAreaField('''Special notes for imaging 
		(e.g. z step size, whether to image ventral-side up, region of brain to image, exposure time, \
			suggested tiling scheme) -- max 1024 characters --''',
		validators=[Length(max=1024)])

	notes_for_processor = TextAreaField('''Special notes for processing 
		 -- max 1024 characters --''',validators=[Length(max=1024)])
	
	atlas_name = SelectField('Atlas for registration',
		choices=[('allen_2017','Allen atlas (2017)'),('allen_2011','Allen atlas (pre-2017)'),
				 ('princeton_mouse_atlas','Princeton Mouse Atlas'),
				 ('paxinos','Franklin-Paxinos Mouse Brain Atlas')],validators=[Optional()])
	final_orientation = SelectField('Output orientation',
		choices=[('sagittal','sagittal'),('coronal','coronal'),
				 ('horizontal','horizontal')],default='sagittal',validators=[Optional()])

class NewImagingForm(FlaskForm):
	""" A form that is used in ExpForm() via a FormField FieldList
	so I dont have to write the imaging parameters out for each sample
	"""
	sample_name = HiddenField('sample name')
	reimaging_this_sample = BooleanField('I need to reimage this sample')
	image_resolution_forsetup = SelectField('Select an image resolution you want to use:', 
		choices=[('1.1x','1.1x (LaVision)'),('1.3x','1.3x (LaVision, for continuity with older experiments)'),
	('2x','2x (LaVision)'),('3.6x','3.6x (SmartSPIM)'),
	('4x','4x (LaVision, for continuity with older experiments)')],validators=[Optional()],default='')   

	image_resolution_forms = FieldList(FormField(NewImagingImageResolutionForm),min_entries=0,max_entries=5)

	new_image_resolution_form_submit = SubmitField('Set up imaging parameters') # renders a new resolution table

class NewImagingRequestForm(FlaskForm):
	""" The form for a new imaging request """
	max_number_of_samples = 50
	number_of_samples = HiddenField('number of samples')
	species = HiddenField('species')
	""" Imaging """
	self_imaging = BooleanField('Check if you plan to do the imaging yourself',default=False)
	imaging_samples = FieldList(FormField(NewImagingForm),min_entries=0,max_entries=max_number_of_samples)
	uniform_imaging_submit_button = SubmitField('Apply these imaging/processing parameters to all samples') # setting default=True does not do anything, so I have to do it in the view function:  https://github.com/lepture/flask-wtf/issues/362

	""" Submission """

	submit = SubmitField('Submit request')	

	""" Custom validators """


	def validate_imaging_samples(self,imaging_samples):
		""" 
		Make sure that each resolution sub-form has at least
		one option selected, and if that option is one of the 
		detection algorithms, then registration 
		registration selected. 

		Also make sure that user cannot create multiple 
		image resolution sub-forms for the same image resolution. 

		Also make sure that if registration is used 
		in a given image resolution table, the output_orientation
		must be sagittal

		Also make sure there can only be 1 registration channel per image resolution
		"""
		any_samples_need_reimaging = any([x['reimaging_this_sample'] for x in imaging_samples.data])
		if not any_samples_need_reimaging:
			raise ValidationError("At least one sample needs to be selected for reimaging to submit this form")
		for ii in range(len(imaging_samples.data)):
			imaging_sample_dict = imaging_samples[ii].data
			sample_name = self.imaging_samples[ii].data['sample_name']
			reimaging_this_sample = self.imaging_samples[ii].data['reimaging_this_sample']
			if not reimaging_this_sample:
				continue
			current_image_resolutions_rendered = []
			if imaging_sample_dict['image_resolution_forms'] == [] and self.submit.data == True:
				raise ValidationError(f"Sample name: {sample_name}, you must set up"
									   " the imaging parameters for at least one image resolution")
			for resolution_form_dict in imaging_sample_dict['image_resolution_forms']:
				image_resolution = resolution_form_dict['image_resolution']
				current_image_resolutions_rendered.append(image_resolution)
				channel_dict_list = resolution_form_dict['channel_forms']
				selected_imaging_modes = [key for channel_dict in channel_dict_list \
					for key in channel_dict if key in current_app.config['IMAGING_MODES'] and channel_dict[key] == True]
				if selected_imaging_modes.count('registration') > 1:
					raise ValidationError("There can only be one registration channel per image resolution")
				if selected_imaging_modes == []:
					raise ValidationError(f"The image resolution table: {image_resolution}"
										  f" for sample name: {sample_name} is empty. Please select at least one option. ")
				if 'registration' in selected_imaging_modes and resolution_form_dict['final_orientation'] != 'sagittal':
					raise ValidationError(f"Sample name: {sample_name}, image resolution table: {image_resolution}:"
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
					  raise ValidationError(f"Sample name: {sample_name}, image resolution table: {image_resolution}"
					  						f" You must select a registration channel"
					  						 " when requesting any of the detection channels")

			if imaging_sample_dict['new_image_resolution_form_submit'] == True:
				image_resolution = imaging_sample_dict['image_resolution_forsetup']
				if image_resolution in current_image_resolutions_rendered:
					raise ValidationError(f"You tried to make a table for image_resolution {image_resolution}"
										  f". But that resolution was already picked for this sample: {sample_name}.")