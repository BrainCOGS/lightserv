from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError

class iDiscoPlusImmunoForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('iDISCO+_immuno Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	

class iDiscoAbbreviatedForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('iDISCO Abbreviated Clearing Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	

class uDiscoForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('uDISCO Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	

class iDiscoPlusForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('iDISCO+ Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	

class iDiscoEduForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('iDISCO_EdU Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	