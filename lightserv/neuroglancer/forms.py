from flask import session, current_app
from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
					 SelectField, BooleanField, IntegerField,
					 DecimalField, FieldList,FormField,HiddenField)
# from wtforms.fields.html5 import DateField
from wtforms.validators import (DataRequired, Length, InputRequired,
	ValidationError, Optional)

class ChannelForm(FlaskForm):
	""" A sub-form for each channel in an ImageResolutionForm """
	channel_name = HiddenField('Channel Name')
	viz_left_lightsheet = BooleanField("Visualize?",default=1)
	viz_right_lightsheet = BooleanField("Visualize?")

class ImageResolutionForm(FlaskForm):
	""" A sub-form for each image resolution in RawDataSetupForm """
	image_resolution = HiddenField('image resolution')
	channel_forms = FieldList(FormField(ChannelForm),min_entries=0,max_entries=4)

	
class RawDataSetupForm(FlaskForm):
	""" A form for setting up how user wants to visualize
	their raw data for a given imaging request in Neuroglancer
	"""
	image_resolution_forms = FieldList(FormField(ImageResolutionForm),min_entries=0,max_entries=4)
	submit = SubmitField('Submit') # renders a new resolution table
	
	def validate_image_resolution_forms(self,image_resolution_forms):
		""" Check to make sure at least one checkbox was checked """
		any_checked = False
		for image_resolution_dict in self.image_resolution_forms.data:
			for channel_dict in image_resolution_dict['channel_forms']:
				if channel_dict['viz_left_lightsheet'] or channel_dict['viz_right_lightsheet']:
					any_checked=True
		if not any_checked:
			raise ValidationError("No light sheets were chosen for display."
								  " You must choose at least one in order to proceed.")


class StitchedDataSetupForm(FlaskForm):
	""" A form for setting up how user wants to visualize
	their stitched (but still raw) data for a given imaging request in Neuroglancer.
	"""
	image_resolution_forms = FieldList(FormField(ImageResolutionForm),min_entries=0,max_entries=4)
	submit = SubmitField('Submit') # renders a new resolution table
	
	def validate_image_resolution_forms(self,image_resolution_forms):
		""" Check to make sure at least one checkbox was checked """
		any_checked = False
		for image_resolution_dict in self.image_resolution_forms.data:
			for channel_dict in image_resolution_dict['channel_forms']:
				if channel_dict['viz_left_lightsheet'] or channel_dict['viz_right_lightsheet']:
					any_checked=True
		if not any_checked:
			raise ValidationError("No light sheets were chosen for display."
								  " You must choose at least one in order to proceed.")


