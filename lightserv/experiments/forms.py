from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError
# from lightserv.models import Experiment

class ExpForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """

	title = StringField('Title',validators=[DataRequired(),Length(max=100)])
	description = TextAreaField('Description',validators=[DataRequired(),Length(max=250)])
	species = SelectField('Species:', choices=[('mouse','mouse'),('rat','rat'),('primate','primate'),('marsupial','marsupial')],validators=[InputRequired(),Length(max=50)]) # for choices first element of tuple is the value of the option, the second is the displayed text
	clearing_protocol = SelectField('Clearing Protocol:', choices= \
		[('iDISCO abbreviated clearing','iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
	('iDISCO+_immuno','iDISCO+ (immunostaining)'),
	('uDISCO','uDISCO'),('iDISCO+','iDISCO+'),('iDISCO_EdU','Wang Lab iDISCO Protocol-EdU')],validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	fluorophores = TextAreaField('Fluorophores/dyes involved (E.g. AlexaFluor 647 or Thy1-YFP mouse)',validators=[Length(max=100)])
	primary_antibody = TextAreaField('Primary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	secondary_antibody = TextAreaField('Secondary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	''' Imaging parameters '''
	image_resolution = SelectField('Image Resolution:', 
		choices=[('1.3x','1.3x (low-res: good for site detection, whole brain c-fos quantification, or registration)'),
	('4x','4x (high-res: good for tracing, cell detection)')],validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	cell_detection = BooleanField('Perform cell detection',default=False)
	registration = BooleanField('Register to atlas',default=False)
	probe_detection = BooleanField('Probe/fiber placement detection',default=False)
	injection_detection = BooleanField('Injection site detection',default=False)
	submit = SubmitField('Start experiment')	

	# def validate_dataset_hex(self,dataset_hex):
	# 	''' Checks to see if dataset_hex already in db '''
	# 	exp = Experiment.query.filter_by(dataset_hex=dataset_hex.data).first()
	# 	if exp: 
	# 		raise ValidationError('dataset ID is already in use. \
	# 			Please enter a different one, or view the status of the existing dataset at its own page.')

	def validate_primary_antibody(self,primary_antibody):
		''' Makes sure that primary antibody is not blank if immunostaining clearing protocol
		is chosen  '''
		if self.clearing_protocol.data == 'iDISCO+_immuno' and primary_antibody.data == '':
			raise ValidationError('Antibody must be specified because you selected \
				an immunostaining clearing protocol')

class UpdateNotesForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('Notes',validators=[Length(max=250)])
	submit = SubmitField('Submit Changes')	
