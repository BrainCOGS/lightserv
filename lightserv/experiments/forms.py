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
	""" The form for clearing a single sample within an experiment """
	# Basic info
	clearing_protocol = SelectField('Clearing Protocol:', choices= \
		[('iDISCO abbreviated clearing','iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
		 ('iDISCO abbreviated clearing (rat)','Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
	     ('iDISCO+_immuno','iDISCO+ (immunostaining)'),
	     ('uDISCO','uDISCO'),('iDISCO_EdU','Wang Lab iDISCO Protocol-EdU')],validators=[InputRequired()]) 
	antibody1 = TextAreaField('Primary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	antibody2 = TextAreaField('Secondary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	perfusion_date = OptionalDateField('Perfusion Date (leave blank if unsure):')
	expected_handoff_date = OptionalDateField('Expected date of hand-off (leave blank if not applicable or unsure):')

	def validate_antibody1(self,antibody1):
		''' Makes sure that primary antibody is not blank if immunostaining clearing protocol
		is chosen  '''
		if self.clearing_protocol.data == 'iDISCO+_immuno' and antibody1.data == '':
			raise ValidationError('Antibody must be specified because you selected \
				an immunostaining clearing protocol')

class ImagingForm(FlaskForm):
	""" The form for imaging a single sample within an experiment """
	# Basic info
	image_resolution = SelectField('Image Resolution:', 
		choices=[('1.3x','1.3x (low-res: good for site detection, whole brain c-fos quantification, or registration)'),
	('4x','4x (high-res: good for tracing, cell detection)')],validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
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

class ExpForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	# Basic info
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
	uniform_imaging = BooleanField('Check if imaging will be the same for all samples',default=False)
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

class OldExpForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """

	# Basic info
	title = StringField('Title',validators=[DataRequired(),Length(max=100)])
	description = TextAreaField('Description',validators=[DataRequired(),Length(max=250)])
	labname = StringField('Lab name(s) (e.g. Tank/Brody)',validators=[DataRequired(),Length(max=100)])
	correspondence_email = StringField('Correspondence email (default is princeton email)',
		validators=[DataRequired(),Length(max=100),Email()])

	species = SelectField('Species:', choices=[('mouse','mouse'),('rat','rat'),('primate','primate'),('marsupial','marsupial')],validators=[InputRequired(),Length(max=50)]) # for choices first element of tuple is the value of the option, the second is the displayed text
	# Clearing info

	perfusion_date = OptionalDateField('Perfusion Date (leave blank if unsure):')
	expected_handoff_date = OptionalDateField('Expected date of hand-off (leave blank if not applicable or unsure):')
	self_clearing = BooleanField('Check if you plan to do the clearing yourself',default=False)
	clearing_protocol = SelectField('Clearing Protocol:', choices= \
		[('iDISCO abbreviated clearing','iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
		 ('iDISCO abbreviated clearing (rat)','Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
	     ('iDISCO+_immuno','iDISCO+ (immunostaining)'),
	     ('uDISCO','uDISCO'),('iDISCO_EdU','Wang Lab iDISCO Protocol-EdU')],validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	antibody1 = TextAreaField('Primary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	antibody2 = TextAreaField('Secondary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	
	# Imaging info
	channel488 = SelectField('488 nm channel purpose',choices=[
							('','None'),
							('registration','registration'),
							('injection_detection','injection_detection'),
							('probe_detection','probe_detection'),
							('cell_detection','cell_detection')]
							)
	channel555 = SelectField('555 nm channel purpose',choices=[
							('','None'),
							('registration','registration'),
							('injection_detection','injection_detection'),
							('probe_detection','probe_detection'),
							('cell_detection','cell_detection')]
							)
	channel647 = SelectField('647 nm channel purpose',choices=[
							('','None'),
							('registration','registration'),
							('injection_detection','injection_detection'),
							('probe_detection','probe_detection'),
							('cell_detection','cell_detection')]
							)
	channel790 = SelectField('790 nm channel purpose',choices=[
							('','None'),
							('registration','registration'),
							('injection_detection','injection_detection'),
							('probe_detection','probe_detection'),
							('cell_detection','cell_detection')]
							)
	image_resolution = SelectField('Image Resolution:', 
		choices=[('1.3x','1.3x (low-res: good for site detection, whole brain c-fos quantification, or registration)'),
	('4x','4x (high-res: good for tracing, cell detection)')],validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	submit = SubmitField('Submit Request')	

	def validate_antibody1(self,antibody1):
		''' Makes sure that primary antibody is not blank if immunostaining clearing protocol
		is chosen  '''
		if self.clearing_protocol.data == 'iDISCO+_immuno' and antibody1.data == '':
			raise ValidationError('Antibody must be specified because you selected \
				an immunostaining clearing protocol')

	def validate_clearing_protocol(self,clearing_protocol):
		''' Makes sure that the clearing protocol selected is appropriate for the species selected. '''
		if clearing_protocol.data == 'iDISCO abbreviated clearing' and self.species.data == 'rat':
			raise ValidationError('This clearing protocol is not allowed for rats. \
				Did you mean to choose: Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)?')
		elif clearing_protocol.data == 'iDISCO abbreviated clearing (rat)' and self.species.data != 'rat':
			raise ValidationError('This clearing protocol is only allowed for rats. \
				Did you mean to choose: iDISCO for non-oxidizable fluorophores (abbreviated clearing)?')

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
