from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Email
import os
import glob
from lightserv import db
# from lightserv.models import Experiment

class ExpForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	title = StringField('Title',validators=[DataRequired(),Length(max=100)])
	description = TextAreaField('Description',validators=[DataRequired(),Length(max=250)])
	labname = StringField('Lab name(s) (e.g. Tank/Brody)',validators=[DataRequired(),Length(max=100)])
	correspondence_email = StringField('Correspondence email (default is princeton email)',
		validators=[DataRequired(),Length(max=100),Email()])

	species = SelectField('Species:', choices=[('mouse','mouse'),('rat','rat'),('primate','primate'),('marsupial','marsupial')],validators=[InputRequired(),Length(max=50)]) # for choices first element of tuple is the value of the option, the second is the displayed text
	clearing_protocol = SelectField('Clearing Protocol:', choices= \
		[('iDISCO abbreviated clearing','iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
		 ('iDISCO abbreviated clearing (rat)','Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
	     ('iDISCO+_immuno','iDISCO+ (immunostaining)'),
	     ('uDISCO','uDISCO'),('iDISCO_EdU','Wang Lab iDISCO Protocol-EdU')],validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	fluorophores = TextAreaField('Fluorophores/dyes involved (E.g. AlexaFluor 647 or Thy1-YFP mouse)',validators=[Length(max=100)])
	channel488 = SelectField('488 nm channel purpose',choices=[('registration','registration'),
							('injection_detection','injection_detection','probe_detection','probe_detection','cell_detection','cell_detection')])
	channel555 = SelectField('555 nm channel purpose',choices=[('registration','registration'),
							('injection_detection','injection_detection','probe_detection','probe_detection','cell_detection','cell_detection')])
	channel647 = SelectField('647 nm channel purpose',choices=[('registration','registration'),
							('injection_detection','injection_detection','probe_detection','probe_detection','cell_detection','cell_detection')])
	channel790 = SelectField('790 nm channel purpose',choices=[('registration','registration'),
							('injection_detection','injection_detection','probe_detection','probe_detection','cell_detection','cell_detection')])
	
	antibody1 = TextAreaField('Primary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	antibody2 = TextAreaField('Secondary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	''' Imaging parameters '''
	image_resolution = SelectField('Image Resolution:', 
		choices=[('1.3x','1.3x (low-res: good for site detection, whole brain c-fos quantification, or registration)'),
	('4x','4x (high-res: good for tracing, cell detection)')],validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	cell_detection = BooleanField('Perform cell detection',default=False)
	registration = BooleanField('Register to atlas',default=False)
	probe_detection = BooleanField('Probe/fiber placement detection',default=False)
	injection_detection = BooleanField('Injection site detection',default=False)
	submit = SubmitField('Start experiment')	

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

class StartProcessingForm(FlaskForm):
	""" The form for requesting to start the data processing """
	rawdata_directory_registration = TextAreaField(\
		'Registration channel raw data directory (on /jukebox)',validators=[DataRequired(),Length(max=500)])
	rawdata_directory_injection_detection = TextAreaField(\
		'Injection channel raw data directory (on /jukebox)',validators=[DataRequired(),Length(max=500)])
	rawdata_directory_probe_detection = TextAreaField(\
		'Injection channel raw data directory (on /jukebox)',validators=[DataRequired(),Length(max=500)])
	rawdata_directory_cell_detection = TextAreaField(\
		'Cell channel raw data directory (on /jukebox)',validators=[DataRequired(),Length(max=500)])

	submit = SubmitField('Start the processing')	

	def validate_rawdata_directory(self,rawdata_directory):
		''' Makes sure that primary antibody is not blank if immunostaining clearing protocol
		is chosen  '''
		if not os.path.isdir(rawdata_directory.data):
			raise ValidationError('This is not a valid directory. Please try again')
		elif rawdata_directory.data[0:8] != '/jukebox':
			raise ValidationError('Path must start with "/jukebox" ')
		elif len(glob.glob(rawdata_directory.data + '/*RawDataStack*ome.tif')) == 0:
			raise ValidationError('No raw data files found in that directory. Try again')

class UpdateNotesForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	
