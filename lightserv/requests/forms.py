from flask import session, current_app
from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
					 SelectField, BooleanField, IntegerField,
					 DecimalField, FieldList,FormField,HiddenField)
# from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Email, Optional
from wtforms.widgets import html5, HiddenInput
import os
import glob
from lightserv import db_lightsheet,db_subject
from wtforms import DateField
from datetime import datetime

def date_validator(form, field):	
	datetime_obj = datetime.strptime(field.data,'%Y-%m-%d')

class ClearingForm(FlaskForm):
	""" A form that is used in ExpForm() via a FormField FieldList
	so I dont have to write the clearing parameters out for each sample 
	"""
	sample_name = StringField("Sample name",validators=[InputRequired()]) # helpful for flash message -- keeps track of sample a form error occurred in
	subject_fullname_unique_list = sorted(list(set(db_subject.Subject().fetch('subject_fullname'))))
	subject_fullname_choices = [('','')] + [(x,x) for x in subject_fullname_unique_list]
	subject_fullname = SelectField('subject_fullname in u19_subject table:',
		choices=subject_fullname_choices,default='') 
	clearing_protocol = SelectField('Clearing Protocol:', choices= \
		[('iDISCO abbreviated clearing','iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
		 ('iDISCO abbreviated clearing (rat)','Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
	     ('iDISCO+_immuno','iDISCO+ (immunostaining)'),
	     ('uDISCO','uDISCO'),('uDISCO (rat)','uDISCO (rat)'),('iDISCO_EdU','Wang Lab iDISCO Protocol-EdU'),
	     ('experimental','experimental')],validators=[InputRequired()]) 
	antibody1 = TextAreaField('Primary antibody and concentrations desired (if doing immunostaining)',
		validators=[Length(max=100)])
	antibody2 = TextAreaField('Secondary antibody and concentrations desired (if doing immunostaining)',
		validators=[Length(max=100)])
	perfusion_date = StringField('Perfusion Date (YYYY-MM-DD); leave blank if unsure):',
		validators=[Optional(),date_validator])
	expected_handoff_date = StringField(
		'Expected date of hand-off (YYYY-MM-DD; please provide unless you plan to clear yourself):',
		validators=[Optional(),date_validator])
	notes_for_clearer = TextAreaField(
		'Special notes for clearing  -- max 400 characters --',validators=[Length(max=400)])

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
	injection_detection = BooleanField('Injection Detection',default=False)
	probe_detection = BooleanField('Probe Detection',default=False)
	cell_detection = BooleanField('Cell Detection',default=False)
	generic_imaging = BooleanField('Generic imaging',default=False)

class ImageResolutionForm(FlaskForm):
	""" A form for each image resolution that a user picks """
	image_resolution = HiddenField('image resolution')
	channel_forms = FieldList(FormField(ChannelForm),min_entries=4,max_entries=4)
	notes_for_imager = TextAreaField('''Special notes for imaging 
		(e.g. z step size, brain orientation, region of brain to image, exposure time, \
			suggested tiling scheme -- make sure to specify which channel(s) these apply to) -- max 1024 characters --''',
		validators=[Length(max=1024)])

	notes_for_processor = TextAreaField('''Special notes for processing 
		 -- max 1024 characters --''',validators=[Length(max=1024)])
	
	atlas_name = SelectField('Atlas for registration',
		choices=[('allen_2017','Allen atlas (2017)'),('allen_2011','Allen atlas (pre-2017)'),
				 ('princeton_mouse_atlas','Princeton Mouse Atlas')],validators=[Optional()])
	final_orientation = SelectField('Output orientation',
		choices=[('sagittal','sagittal'),('coronal','coronal'),
				 ('horizontal','horizontal')],default='sagittal',validators=[Optional()])

class ImagingForm(FlaskForm):
	""" A form that is used in ExpForm() via a FormField FieldList
	so I dont have to write the imaging parameters out for each sample
	"""
	image_resolution_forsetup = SelectField('Select an image resolution you want to use:', 
		choices=[('1.1x','1.1x (LaVision)'),('1.3x','1.3x (LaVision, for continuity with older experiments)'),
	('2x','2x (LaVision)'),('3.6x','3.6x (SmartSPIM)'),
	('4x','4x (LaVision, for continuity with older experiments)')],validators=[Optional()],default='')   

	image_resolution_forms = FieldList(FormField(ImageResolutionForm),min_entries=0,max_entries=5)

	new_image_resolution_form_submit = SubmitField('Set up imaging parameters') # renders a new resolution table

class NewRequestForm(FlaskForm):
	""" The form for a new request """
	max_number_of_samples = 50
	enter_for_otheruser = BooleanField('Check if you are filling out this form for someone else',default=False)
	other_username = StringField('Netid of that person',
		validators=[Length(max=20)])
	request_name = StringField(
		'Request_name - a unique identifier for this request -- max 64 characters --',
		validators=[InputRequired(),Length(max=64)])
	
	description = TextAreaField('What is the goal of this request? -- max 250 characters --',
		validators=[InputRequired(),Length(max=250)])
	
	labname = StringField('Lab name(s) (e.g. Tank/Brody)',
		validators=[InputRequired(),Length(max=100)],)
	
	correspondence_email = StringField('Correspondence email (default is your princeton email)',
		validators=[DataRequired(),Length(max=100),Email()])

	species = SelectField('Species:', choices=[('mouse','mouse'),('rat','rat'),
		('primate','primate'),('marsupial','marsupial')],
		validators=[InputRequired(),Length(max=50)],
		default="mouse") # for choices first element of tuple is the value of the option, the second is the displayed text
	
	number_of_samples = IntegerField('Number of samples (a.k.a. tubes)',widget=html5.NumberInput(),validators=[InputRequired()],default=1)
	# sample_prefix = StringField('Sample prefix (your samples will be named prefix-1, prefix-2, ...)',validators=[InputRequired(),Length(max=32)],default='sample')
	# subject_fullnames_known = BooleanField("Check if any of your samples have subject_fullname entries in the u19_subject database table")
	# subject_fullnames = FieldList(StringField('subject name - the subject_fullname entry in the u19_subject database table (leave blank if unknown) --',
		# validators=[InputRequired(),Length(max=100)]),min_entries=0,max_entries=max_number_of_samples)
	testing = BooleanField("Check if this request is for testing purposes (e.g. new clearing protocol, processing technique)")
	""" Clearing """
	self_clearing = BooleanField('Check if you plan to do the clearing yourself',default=False)
	clearing_samples = FieldList(FormField(ClearingForm),min_entries=0,max_entries=max_number_of_samples)
	uniform_clearing_submit_button = SubmitField('Apply these clearing parameters to all samples') # setting default=True does not do anything, so I have to do it in the view function:  https://github.com/lepture/flask-wtf/issues/362
	
	""" Imaging """
	self_imaging = BooleanField('Check if you plan to do the imaging yourself',default=False)
	imaging_samples = FieldList(FormField(ImagingForm),min_entries=0,max_entries=max_number_of_samples)
	uniform_imaging_submit_button = SubmitField('Apply these imaging/processing parameters to all samples') # setting default=True does not do anything, so I have to do it in the view function:  https://github.com/lepture/flask-wtf/issues/362

	custom_sample_names = BooleanField("Check if you want to give custom names to each of your samples. "
		          					   "If unchecked, your sample names will be {request_name}-sample-001, "
		          					   "{request_name}-sample-002, ...")
	""" Processing """

	sample_submit_button = SubmitField('Setup samples')

	""" Submission """

	submit = SubmitField('Submit request')	

	""" Custom validators """

	def validate_submit(self,submit):
		""" Make sure that user has filled out sample setup section

		Also make sure that expected handoff dates are filled unless self clearing is selected.""" 
		if submit.data == True:
			if len(self.clearing_samples.data) == 0 or  len(self.imaging_samples.data) == 0:
				raise ValidationError("You must fill out and submit the Samples setup section first.")
			if not self.self_clearing.data:
				samples_missing_expected_handoff_date_str = \
					', '.join([d['sample_name'] for d in self.clearing_samples.data if not d['expected_handoff_date']])
				if samples_missing_expected_handoff_date_str != '':
					raise ValidationError(f"Expected handoff date required for samples: {samples_missing_expected_handoff_date_str}")

	def validate_number_of_samples(self,number_of_samples):
		""" Make sure number_of_samples is > 0 and < max_number_of_samples """
		if number_of_samples.data > self.max_number_of_samples:
			raise ValidationError(f"Please limit your requested number of samples \
			to {self.max_number_of_samples} or less")
		elif number_of_samples.data < 1:
			raise ValidationError("You must have at least one sample to submit a request")

	def validate_request_name(self,request_name):
		""" Make sure request name is unique """
		if self.other_username.data:
			username = self.other_username.data
		else:
			username = session['user']
		if ' ' in request_name.data:
			raise ValidationError("Request_name must not contain any blank spaces")
		current_request_names = (db_lightsheet.Request() & f'username="{username}"').fetch('request_name')
		if request_name.data in current_request_names:
			raise ValidationError(f'There already exists a request named "{request_name.data}" '
								  f'under the account of {username}. Please rename the request')

	def validate_clearing_samples(self,clearing_samples):
		""" Make sure that there are no samples where the clearing protocol is impossible
		given the species. 

		Also make sure that the sample names are unique
		"""
		all_sample_names = []
		for sample_dict in clearing_samples.data:
			sample_name = sample_dict['sample_name']
			if sample_name in all_sample_names:
				raise ValidationError(f"Sample name: {sample_name} is duplicated. \
				 Make sure to pick unique names for each sample")
			all_sample_names.append(sample_name)

			clearing_protocol_sample = sample_dict['clearing_protocol']
			if clearing_protocol_sample == 'iDISCO abbreviated clearing (rat)' and self.species.data != 'rat':
				raise ValidationError(f"Sample_name: {sample_name}. Clearing protocol: {clearing_protocol_sample} "
					                  f"can only be used with rat subjects. You specified species={self.species.data}")
			if (clearing_protocol_sample not in ['iDISCO abbreviated clearing (rat)','uDISCO (rat)','experimental'])  and self.species.data == 'rat':
				raise ValidationError(f"Sample_name: {sample_name}. The clearing protocol you selected: {clearing_protocol_sample} "
				                        "is not valid for species=rat. The only clearing protocol currently available for rat subjects is: " 
				  						"Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)")


	def validate_imaging_samples(self,imaging_samples):
		""" make sure that each resolution sub-form has at least
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
		for ii in range(len(imaging_samples.data)):
			imaging_sample_dict = imaging_samples[ii].data
			sample_name = self.clearing_samples[ii].data['sample_name']
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

class UpdateNotesForm(FlaskForm):
	""" The form for updating notes field"""
	notes = TextAreaField('Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	


class ConfirmDeleteForm(FlaskForm):
	# form_name = HiddenField('Form Name')
	request_name = StringField('Type the request name you want to delete:', validators=[InputRequired()]) 
	submit = SubmitField('Yes, delete this request.')

	def validate_request_name(self,request_name):
		request_names = db_lightsheet.Request().fetch('request_name')
		if request_name.data not in request_names:
			raise ValidationError("Request name is not valid. Please try again.")