from flask import url_for,flash,redirect, request, Markup
from flask_table import Table, Col

class ImagingRequestTable(Table):
	border = True
	allow_sort = False
	no_items = "No Imaging Request Yet"
	html_attrs = {"style":'font-size:18px',} # gets assigned to table header
	# column_html_attrs = {'style':'text-align: center; min-width:10px', 'bgcolor':"#FF0000"} # gets assigned to both th and td
	column_html_attrs = [] # javascript tableswapper does not preserve these.
	classes = ["table-striped"] # gets assigned to table classes. 
	# Striped is alternating bright and dark rows for visual ease.

	username = Col('username',column_html_attrs=column_html_attrs)
	request_name = Col('request name',column_html_attrs=column_html_attrs)
	sample_name = Col('sample name',column_html_attrs=column_html_attrs)
	imaging_request_number = Col('imaging request number',column_html_attrs=column_html_attrs)

class ProcessingRequestTable(Table):
	border = True
	allow_sort = False
	no_items = "No Imaging Request Yet"
	html_attrs = {"style":'font-size:18px',} # gets assigned to table header
	# column_html_attrs = {'style':'text-align: center; min-width:10px', 'bgcolor':"#FF0000"} # gets assigned to both th and td
	column_html_attrs = [] # javascript tableswapper does not preserve these.
	classes = ["table-striped"] # gets assigned to table classes. 
	# Striped is alternating bright and dark rows for visual ease.

	username = Col('username',column_html_attrs=column_html_attrs)
	request_name = Col('request name',column_html_attrs=column_html_attrs)
	sample_name = Col('sample name',column_html_attrs=column_html_attrs)
	imaging_request_number = Col('imaging request number',column_html_attrs=column_html_attrs)
	processing_request_number = Col('processing request number',column_html_attrs=column_html_attrs)

class CloudVolumeLayerTable(Table):
	""" Table showing cloudvolume layer names,
	their layer path on bucket
	and their data path on bucket
	so the user can easily go to where their data 
	lives """
	border = True
	allow_sort = False
	no_items = "No Layers!"
	html_attrs = {"style":'font-size:18px',} # gets assigned to table header
	# column_html_attrs = {'style':'text-align: center; min-width:10px', 'bgcolor':"#FF0000"} # gets assigned to both th and td
	column_html_attrs = [] # javascript tableswapper does not preserve these.
	classes = ["table-striped"] # gets assigned to table classes. 
	# Striped is alternating bright and dark rows for visual ease.

	image_resolution = Col('Image resolution',column_html_attrs=column_html_attrs)
	cv_name = Col('Layer name',column_html_attrs=column_html_attrs)
	data_path = Col('Path to data on bucket',column_html_attrs=column_html_attrs)
	cv_path = Col('Path to precomputed layer on bucket',column_html_attrs=column_html_attrs)

class MultiLightSheetCloudVolumeLayerTable(Table):
	""" Table showing cloudvolume layer names,
	their layer path on bucket
	and their data path on bucket
	so the user can easily go to where their data 
	lives """
	border = True
	allow_sort = False
	no_items = "No Layers!"
	html_attrs = {"style":'font-size:18px',} # gets assigned to table header
	# column_html_attrs = {'style':'text-align: center; min-width:10px', 'bgcolor':"#FF0000"} # gets assigned to both th and td
	column_html_attrs = [] # javascript tableswapper does not preserve these.
	classes = ["table-striped"] # gets assigned to table classes. 
	# Striped is alternating bright and dark rows for visual ease.

	image_resolution = Col('Image resolution',column_html_attrs=column_html_attrs)
	lightsheet = Col('Lightsheet',column_html_attrs=column_html_attrs)
	cv_name = Col('Layer name',column_html_attrs=column_html_attrs)
	data_path = Col('Path to data on bucket',column_html_attrs=column_html_attrs)
	cv_path = Col('Path to precomputed layer on bucket',column_html_attrs=column_html_attrs)