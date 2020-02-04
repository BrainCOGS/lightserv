from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
					 SelectField, BooleanField, IntegerField,
					 DecimalField, FieldList,FormField,HiddenField,
					 RadioField)
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Email, Optional
from wtforms.widgets import html5, HiddenInput

class SpockConnectionTesterForm(FlaskForm):
	submit = SubmitField("Test connection")
	

class FeedbackForm(FlaskForm):
	rating_choices = [(x,x) for x in range(1,6)]
	clearing_rating = RadioField('Clearing:',choices=rating_choices,validators=[InputRequired()])
	clearing_notes = TextAreaField('Specific feedback on clearing:',validators=[Length(max=256)])
	imaging_rating = RadioField('Imaging:',choices=rating_choices,validators=[InputRequired()])
	imaging_notes = TextAreaField('Specific feedback on imaging:',validators=[Length(max=256)])
	processing_rating = RadioField('Processing:',choices=rating_choices,validators=[InputRequired()])
	processing_notes = TextAreaField('Specific feedback on processing:',validators=[Length(max=256)])
	submit = SubmitField("Submit Feedback")
	