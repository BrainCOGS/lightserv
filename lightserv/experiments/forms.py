from flask import session
from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
					 SelectField, BooleanField, IntegerField,
					 DecimalField, FieldList,FormField)
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
	""" A form that is used in ExpForm() via a FormField Fieldlist
	so I dont have to write the clearing parameters out for each sample 
	"""
	clearing_protocol = SelectField('Clearing Protocol:', choices= \
		[('iDISCO abbreviated clearing','iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
		 ('iDISCO abbreviated clearing (rat)','Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
	     ('iDISCO+_immuno','iDISCO+ (immunostaining)'),
	     ('uDISCO','uDISCO'),('iDISCO_EdU','Wang Lab iDISCO Protocol-EdU')],validators=[InputRequired()]) 
	antibody1 = TextAreaField('Primary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	antibody2 = TextAreaField('Secondary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	perfusion_date = OptionalDateField('Perfusion Date (MM/DD/YYYY; leave blank if unsure):')
	expected_handoff_date = OptionalDateField('Expected date of hand-off (MM/DD/YYYY; leave blank if not sure or not applicable):')
	notes_for_clearer = TextAreaField('Notes for clearing  -- max 1024 characters --',validators=[Length(max=1024)])

	def validate_antibody1(self,antibody1):
		''' Makes sure that primary antibody is not blank if immunostaining clearing protocol
		is chosen  '''
		if self.clearing_protocol.data == 'iDISCO+_immuno' and antibody1.data == '':
			raise ValidationError('Antibody must be specified because you selected \
				an immunostaining clearing protocol')

class ImagingForm(FlaskForm):
	""" A form that is used in ExpForm() via a FormField Fieldlist
	so I dont have to write the imaging parameters out for each sample
	"""
	image_resolution = SelectField('Image Resolution:', 
		choices=[('1.3x','1.3x'),
	('4x','4x'),('1.1x','1.1x'),('2x','2x')],validators=[InputRequired()]) 
	channel488_registration = BooleanField('Registration',default=False)
	channel488_injection_detection = BooleanField('Registration',default=False)
	channel488_probe_detection = BooleanField('Registration',default=False)
	channel488_cell_detection = BooleanField('Registration',default=False)
	channel555_registration = BooleanField('Registration',default=False)
	channel555_injection_detection = BooleanField('Registration',default=False)
	channel555_probe_detection = BooleanField('Registration',default=False)
	channel555_cell_detection = BooleanField('Registration',default=False)
	channel647_registration = BooleanField('Registration',default=False)
	channel647_injection_detection = BooleanField('Registration',default=False)
	channel647_probe_detection = BooleanField('Registration',default=False)
	channel647_cell_detection = BooleanField('Registration',default=False)
	channel790_registration = BooleanField('Registration',default=False)
	channel790_injection_detection = BooleanField('Registration',default=False)
	channel790_probe_detection = BooleanField('Registration',default=False)
	channel790_cell_detection = BooleanField('Registration',default=False)
	notes_for_imager = TextAreaField('''Notes for imaging 
		(e.g. exposure time, tiling scheme) -- max 1024 characters --''',validators=[Length(max=1024)])
	stitching_method = SelectField('Stitching method',choices=[('blending','blending'),
		('terastitcher','terastitcher')],validators=[InputRequired()])
	blend_type = SelectField('Blend type',choices=[('sigmoidal','sigmoidal'),('flat','flat')],
		validators=[InputRequired()])
	atlas_name = SelectField('Atlas for registration',
		choices=[('allen_2017','Allen atlas (2017)'),('allen_2011','Allen atlas (pre-2017)'),
				 ('princeton_mouse_atlas','Princeton Mouse Atlas')],validators=[InputRequired()])
	tiling_overlap = DecimalField('Tiling overlap (number between 0.0 and 1.0; leave as default if unsure or not using tiling)',
		places=2,validators=[Optional()],default=0.1) 
	intensity_correction = BooleanField('Perform intensity correction? (leave as default if unsure)',default=True)

	def validate_tiling_overlap(self,tiling_overlap):
		try:
			if tiling_overlap.data < 0 or tiling_overlap.data >= 1:
				raise ValidationError("Tiling overlap must be between 0.0 and 1.0")
		except:
			raise ValidationError("Tiling overlap must be a number between 0.0 and 1.0")

class NewRequestForm(FlaskForm):
	""" The form for a new request """
	max_number_of_samples = 50
	experiment_name = StringField('Name of experiment',validators=[InputRequired(),Length(max=100)])
	description = TextAreaField('Description of experiment',validators=[InputRequired(),Length(max=250)])
	labname = StringField('Lab name(s) (e.g. Tank/Brody)',validators=[InputRequired(),Length(max=100)])
	correspondence_email = StringField('Correspondence email (default is princeton email)',
		validators=[DataRequired(),Length(max=100),Email()])

	species = SelectField('Species:', choices=[('mouse','mouse'),('rat','rat'),('primate','primate'),('marsupial','marsupial')],validators=[InputRequired(),Length(max=50)]) # for choices first element of tuple is the value of the option, the second is the displayed text
	number_of_samples = IntegerField('Number of samples (a.k.a. tubes)',widget=html5.NumberInput(),validators=[InputRequired()])
	sample_prefix = StringField('Sample prefix (your samples will be named prefix-1, prefix-2, ...)',validators=[InputRequired(),Length(max=32)])
	""" Clearing """
	self_clearing = BooleanField('Check if you plan to do the clearing yourself',default=False)
	clearing_samples = FieldList(FormField(ClearingForm),min_entries=0,max_entries=max_number_of_samples)
	uniform_clearing = BooleanField('Check if clearing will be the same for all samples',default=False)
	
	""" Imaging """
	self_imaging = BooleanField('Check if you plan to do the imaging yourself',default=False)
	imaging_samples = FieldList(FormField(ImagingForm),min_entries=0,max_entries=max_number_of_samples)
	uniform_imaging = BooleanField('Check if imaging/processing will be the same for all samples',default=False)

	sample_submit_button = SubmitField('Setup samples')

	submit = SubmitField('Submit request')	

	def validate_submit(self,submit):
		""" Make sure that user has filled out sample setup section """ 
		if self.submit.data == True:
			if len(self.clearing_samples.data) == 0 or  len(self.imaging_samples.data) == 0:
				raise ValidationError("You must fill out and submit the 'Samples setup' section first.")

	def validate_number_of_samples(self,number_of_samples):
		""" Make sure number_of_samples is > 0 and < max_number_of_samples """
		if number_of_samples.data > self.max_number_of_samples:
			raise ValidationError(f"Please limit your requested number of samples \
			to {self.max_number_of_samples} or less")
		elif number_of_samples.data < 1:
			raise ValidationError("You must have at least one sample to submit a request")

	def validate_experiment_name(self,experiment_name):
		""" Make sure experiment name is unique """
		username = session['user']
		current_experiment_names = (db_lightsheet.Experiment() & f'username="{username}"').fetch('experiment_name')
		if experiment_name.data in current_experiment_names:
			raise ValidationError(f'There already exists an experiment name "{experiment_name.data}" \
				for your username. Please rename your experiment')

	def validate_clearing_samples(self,clearing_samples):
		print(clearing_samples.data)
		for sample_dict in clearing_samples.data:
			clearing_protocol_sample = sample_dict['clearing_protocol']
			if clearing_protocol_sample == 'iDISCO abbreviated clearing (rat)' and self.species.data != 'rat':
				raise ValidationError("This clearing protocol can only be used with rats")
			if clearing_protocol_sample != 'iDISCO abbreviated clearing (rat)' and self.species.data == 'rat':
				raise ValidationError(f"""At least one of the clearing protocols you chose is not applicable for rats. 
				 The only clearing protocol currently available for rats is: 
				  'Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)'
				  """)

def Directory_validator(form,field):
	''' Makes sure that the raw data directories exist on jukebox  '''
	if not os.path.isdir(field.data):
		raise ValidationError('This is not a valid directory. Please try again')
	elif field.data[0:8] != '/jukebox':
		raise ValidationError('Path must start with "/jukebox" ')
	elif len(glob.glob(field.data + '/*RawDataStack*ome.tif')) == 0:
		raise ValidationError('No raw data files found in that directory. Try again')	

class StartProcessingForm(FlaskForm):
	""" The form for requesting to start the data processing """
	stitching_method = SelectField('Stitching method',choices=[('blending','blending')],
		validators=[InputRequired()])
	blend_type = SelectField('Blend type',choices=[('sigmoidal','sigmoidal'),('flat','flat')],
		validators=[InputRequired()])
	atlas_name = SelectField('Atlas for registration',
		choices=[('allen_2017','Allen atlas (2017)'),('allen_2011','Allen atlas (pre-2017)'),
				 ('princeton_mouse_atlas','Princeton Mouse Atlas')],validators=[InputRequired()])
	tiling_overlap = DecimalField('Tiling overlap (leave blank if no tiling used)',
		places=2,validators=[Optional()]) 
	intensity_correction = BooleanField('Perform intensity correction? (leave as default if unsure)',default=True)
	
	submit = SubmitField('Start the processing')	
	
	def validate_tiling_overlap(self,tiling_overlap):
		try:
			if tiling_overlap.data < 0 or tiling_overlap.data >= 1:
				raise ValidationError("Tiling overlap must be between 0.0 and 1.0")
		except:
			raise ValidationError("Tiling overlap must be a number between 0.0 and 1.0")

	
		
class OldStartProcessingForm(FlaskForm):
	""" The form for requesting to start the data processing """

	rawdata_directory_channel488 = TextAreaField(\
		'Channel 488 raw data directory (on /jukebox)',validators=[Optional(),Length(max=500),Directory_validator])
	rawdata_directory_channel555 = TextAreaField(\
		'Channel 555 raw data directory (on /jukebox)',validators=[Optional(),Length(max=500),Directory_validator])
	rawdata_directory_channel647 = TextAreaField(\
		'Channel 647 raw data directory (on /jukebox)',validators=[Optional(),Length(max=500),Directory_validator])
	rawdata_directory_channel790 = TextAreaField(\
		'Channel 790 raw data directory (on /jukebox)',validators=[Optional(),Length(max=500),Directory_validator])

	submit = SubmitField('Start the processing')	

class UpdateNotesForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	
