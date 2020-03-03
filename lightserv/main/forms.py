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
	clearing_rating = RadioField('Clearing:',choices=rating_choices,coerce=int) # required field, but a bug prevents me from using InputRequired() so I handle it in html
	clearing_notes = TextAreaField('Specific feedback on clearing (e.g. clarity of samples, anticipated versus actual time to clear):',validators=[Length(max=256)])
	imaging_rating = RadioField('Imaging:',choices=rating_choices,validators=[InputRequired()],coerce=int)
	imaging_notes = TextAreaField('Specific feedback on imaging (e.g. clarity of images, satisfied with Signal-to-Noise Ratio?):',validators=[Length(max=256)])
	processing_rating = RadioField('Processing:',choices=rating_choices,validators=[InputRequired()],coerce=int)
	processing_notes = TextAreaField('Specific feedback on processing (e.g. quality of registration, signal detection):',validators=[Length(max=256)])
	other_notes = TextAreaField('Any other feedback for this request:',validators=[Length(max=256)])
	submit = SubmitField("Submit Feedback")
	