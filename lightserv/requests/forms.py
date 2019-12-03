from flask import session, current_app
from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
					 SelectField, BooleanField, IntegerField,
					 DecimalField, FieldList,FormField,HiddenField)
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Email, Optional
from wtforms.widgets import html5, HiddenInput
import os
import glob
from lightserv import db_lightsheet

# from lightserv.models import Experiment

def OptionalDateField(description='',validators=[]):
	""" A custom field that makes the DateField optional """
	validators.append(Optional())
	field = DateField(description,validators)
	return field

class ClearingForm(FlaskForm):
	""" A form that is used in ExpForm() via a FormField FieldList
	so I dont have to write the clearing parameters out for each sample 
	"""
	sample_name = HiddenField("sample_name") # helpful for flash message -- keeps track of sample a form error occurred in
	clearing_protocol = SelectField('Clearing Protocol:', choices= \
		[('iDISCO abbreviated clearing','iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
		 ('iDISCO abbreviated clearing (rat)','Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
	     ('iDISCO+_immuno','iDISCO+ (immunostaining)'),
	     ('uDISCO','uDISCO'),('iDISCO_EdU','Wang Lab iDISCO Protocol-EdU')],validators=[InputRequired()]) 
	antibody1 = TextAreaField('Primary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	antibody2 = TextAreaField('Secondary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	perfusion_date = OptionalDateField('Perfusion Date (MM/DD/YYYY; leave blank if unsure):')
	expected_handoff_date = OptionalDateField('Expected date of hand-off (MM/DD/YYYY; leave blank if not sure or not applicable):')
	notes_for_clearer = TextAreaField('Special notes for clearing  -- max 1024 characters --',validators=[Length(max=1024)])

	def validate_antibody1(self,antibody1):
		''' Makes sure that primary antibody is not blank if immunostaining clearing protocol
		is chosen  '''
		if self.clearing_protocol.data == 'iDISCO+_immuno' and antibody1.data == '':
			raise ValidationError('Antibody must be specified because you selected \
				an immunostaining clearing protocol')

class ChannelForm(FlaskForm):
	""" Used by other forms in a FieldList """
	channel_name = HiddenField('Channel Name')
	registration = BooleanField('Registration',default=False)
	injection_detection = BooleanField('Registration',default=False)
	probe_detection = BooleanField('Registration',default=False)
	cell_detection = BooleanField('Registration',default=False)

class ImageResolutionForm(FlaskForm):
	""" A form for each image resolution that a user picks """
	image_resolution = HiddenField('image resolution')
	channels = FieldList(FormField(ChannelForm),min_entries=4,max_entries=4)
	notes_for_imager = TextAreaField('''Special notes for imaging 
		(e.g. z step size, exposure time, suggested tiling scheme -- make sure to specify which channel) -- max 1024 characters --''',
		validators=[Length(max=1024)])

	notes_for_processor = TextAreaField('''Special notes for processing 
		 -- max 1024 characters --''',validators=[Length(max=1024)])
	
	atlas_name = SelectField('Atlas for registration',
		choices=[('allen_2017','Allen atlas (2017)'),('allen_2011','Allen atlas (pre-2017)'),
				 ('princeton_mouse_atlas','Princeton Mouse Atlas')],validators=[InputRequired()])

class ImagingForm(FlaskForm):
	""" A form that is used in ExpForm() via a FormField FieldList
	so I dont have to write the imaging parameters out for each sample
	"""
	sample_name = HiddenField("sample_name") # helpful for flash message -- keeps track of sample a form error occurred in

	image_resolution_forsetup = SelectField('Select an image resolution you want to use:', 
		choices=[('1.3x','1.3x'),
	('4x','4x'),('1.1x','1.1x'),('2x','2x')],default='')   

	image_resolution_forms = FieldList(FormField(ImageResolutionForm),min_entries=0,max_entries=4)

	new_image_resolution_form_submit = SubmitField('Set up imaging parameters') # renders a new resolution table

class NewRequestForm(FlaskForm):
	""" The form for a new request """
	max_number_of_samples = 50
	request_name = StringField('Name of experiment',validators=[InputRequired(),Length(max=100)],default="test")
	description = TextAreaField('Description of experiment',validators=[InputRequired(),Length(max=250)],default='test')
	labname = StringField('Lab name(s) (e.g. Tank/Brody)',validators=[InputRequired(),Length(max=100)],default="Braincogs")
	correspondence_email = StringField('Correspondence email (default is princeton email)',
		validators=[DataRequired(),Length(max=100),Email()])

	species = SelectField('Species:', choices=[('mouse','mouse'),('rat','rat'),('primate','primate'),('marsupial','marsupial')],validators=[InputRequired(),Length(max=50)]) # for choices first element of tuple is the value of the option, the second is the displayed text
	number_of_samples = IntegerField('Number of samples (a.k.a. tubes)',widget=html5.NumberInput(),validators=[InputRequired()],default=1)
	sample_prefix = StringField('Sample prefix (your samples will be named prefix-1, prefix-2, ...)',validators=[InputRequired(),Length(max=32)],default='sample')
	""" Clearing """
	self_clearing = BooleanField('Check if you plan to do the clearing yourself',default=False)
	clearing_samples = FieldList(FormField(ClearingForm),min_entries=0,max_entries=max_number_of_samples)
	uniform_clearing = BooleanField('Check if clearing will be the same for all samples') # setting default=True does not do anything, so I have to do it in the view function:  https://github.com/lepture/flask-wtf/issues/362
	
	""" Imaging """
	self_imaging = BooleanField('Check if you plan to do the imaging yourself',default=False)
	imaging_samples = FieldList(FormField(ImagingForm),min_entries=0,max_entries=max_number_of_samples)
	uniform_imaging = BooleanField('Check if imaging/processing will be the same for all samples')

	sample_submit_button = SubmitField('Setup samples')

	submit = SubmitField('Submit request')	

	def validate_submit(self,submit):
		""" Make sure that user has filled out sample setup section """ 
		print(submit.data)
		if submit.data == True:
			if len(self.clearing_samples.data) == 0 or  len(self.imaging_samples.data) == 0:
				raise ValidationError("You must fill out and submit the 'Samples setup' section first.")

	def validate_number_of_samples(self,number_of_samples):
		""" Make sure number_of_samples is > 0 and < max_number_of_samples """
		if number_of_samples.data > self.max_number_of_samples:
			raise ValidationError(f"Please limit your requested number of samples \
			to {self.max_number_of_samples} or less")
		elif number_of_samples.data < 1:
			raise ValidationError("You must have at least one sample to submit a request")

	def validate_request_name(self,request_name):
		""" Make sure experiment name is unique """
		current_user = session['user']
		current_request_names = (db_lightsheet.Request() & f'username="{current_user}"').fetch('request_name')
		if request_name.data in current_request_names:
			raise ValidationError(f'There already exists an experiment named "{request_name.data}" \
				for your account. Please rename your experiment')

	def validate_clearing_samples(self,clearing_samples):
		""" Make sure that there are no samples where the clearing protocol is impossible
		given the species. 
		"""
		for sample_dict in clearing_samples.data:
			clearing_protocol_sample = sample_dict['clearing_protocol']
			if clearing_protocol_sample == 'iDISCO abbreviated clearing (rat)' and self.species.data != 'rat':
				raise ValidationError("One of the clearing protocols selected can only be used with rats")
			if clearing_protocol_sample != 'iDISCO abbreviated clearing (rat)' and self.species.data == 'rat':
				raise ValidationError(f"""At least one of the clearing protocols you chose is not applicable for rats. 
				 The only clearing protocol currently available for rats is: 
				  'Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)'
				  """)

	def validate_imaging_samples(self,imaging_samples):
		""" make sure that each resolution sub-form has at least
			one option selected, and if that option is one of the 
			detection algorithms, then registration 
			registration selected. 

			Also make sure that user cannot create multiple 
			image resolution sub-forms for the same image resolution. 
		"""
		for sample_dict in imaging_samples.data:
			sample_name = sample_dict['sample_name']
			current_image_resolutions_rendered = []
			if sample_dict['image_resolution_forms'] == [] and self.submit.data == True:
				raise ValidationError(f"Sample name: {sample_name}, you must set up"
									   " the imaging parameters for at least one image resolution")
			for resolution_form_dict in sample_dict['image_resolution_forms']:
				image_resolution = resolution_form_dict['image_resolution']
				current_image_resolutions_rendered.append(image_resolution)
				
				channel_dict_list = resolution_form_dict['channels']
				selected_imaging_modes = [key for channel_dict in channel_dict_list \
					for key in channel_dict if key in current_app.config['IMAGING_MODES'] and channel_dict[key] == True]
				if selected_imaging_modes == []:
					raise ValidationError(f"The image resolution table: {image_resolution}"
										  f" for sample name: {sample_name} is empty. Please select at least one option. ")
				elif ('injection_detection' in selected_imaging_modes or \
					  'probe_detection' in selected_imaging_modes  or \
					  'cell_detection' in selected_imaging_modes) and \
					  'registration' not in selected_imaging_modes:
					  raise ValidationError(f"Sample name: {sample_name}, image resolution table: {image_resolution}"
					  						f" You must select a registration channel"
					  						 " when requesting any of the 'detection' channels")

			if sample_dict['new_image_resolution_form_submit'] == True:
				image_resolution = sample_dict['image_resolution_forsetup']
				if image_resolution in current_image_resolutions_rendered:
					raise ValidationError(f"You tried to make a table for image_resolution {image_resolution}"
										  f". But that resolution was already picked for this sample: {sample_name}.")

	# def validate_imaging_samples(self,imaging_samples):
	# 	""" Make sure that at least one imaging channel was selected for each sample
	# 	and that if a box is checked for an imaging mode, then a resolution must also
	# 	be picked
	# 	"""
	# 	for sample_dict in imaging_samples.data:
	# 		for channel_dict in sample_dict['channels']:
	# 			image_resolution_requested = channel_dict['image_resolution_requested']
	# 			if image_resolution_requested == 'None' or image_resolution_requested == None:
	# 				if any(channel_dict[key] for key in current_app.config['IMAGING_MODES']):
	# 					sample_name = sample_dict['sample_name']
	# 					channel_name = channel_dict['channel_name']
	# 					raise ValidationError(f" You did not specify an image resolution for sample = {sample_name},"
	# 											f" channel = {channel_name}, but you checked one of the imaging boxes")
	# 		''' collect the 0s and 1s from all channel modes '''

	# 		all_mode_values = [sample_dict[key] for key in sample_dict.keys() if 'channel' in key ]
	# 		if not any(all_mode_values): # if all are 0				
	# 			raise ValidationError("Each sample must have at least one imaging channel selected.")

def Directory_validator(form,field):
	''' Makes sure that the raw data directories exist on jukebox  '''
	if not os.path.isdir(field.data):
		raise ValidationError('This is not a valid directory. Please try again')
	elif field.data[0:8] != '/jukebox':
		raise ValidationError('Path must start with "/jukebox" ')
	elif len(glob.glob(field.data + '/*RawDataStack*ome.tif')) == 0:
		raise ValidationError('No raw data files found in that directory. Try again')	

class UpdateNotesForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	
