from flask import url_for,flash,redirect, request, Markup
from flask_table import Table, Col, LinkCol, ButtonCol, create_table, NestedTableCol
from functools import partial
from lightserv.main.utils import table_sorter
from lightserv.main.tables import (DateTimeCol, ImagingRequestLinkCol,
	ProcessingRequestLinkCol, element,NewProcessingRequestLinkCol,
	AbbrevDescriptionCol,BooltoStringCol,NewImagingRequestLinkCol,
	NotAssignedCol,ConditionalDeleteLinkCol)
from lightserv import db_lightsheet
import os

class ClearingTableLinkCol(LinkCol):
	""" A convenience column used to show 
	the link to either the clearing log route
	or to the clearing spreadsheet if the request
	is an archival one """
	
	def td_contents(self, item, attr_list):
		if item['clearing_progress'] == 'complete':
			if item['is_archival']:
				return '<a href="{url}" target="_blank">{text}</a>'.format(
					url=item['link_to_clearing_spreadsheet'],
					text='link')
			else:	
				return '<a href="{url}" target="_blank">{text}</a>'.format(
					url=self.url(item),
					text=self.td_format(self.text(item, attr_list)))
		else:
			return "N/A"

class AllRequestTable(Table):
	""" The table shown at the all_requests() route """
	border = True
	allow_sort = True
	no_items = "No Requests Yet"
	html_attrs = {"style":'font-size:16px',} # gets assigned to table header
	table_id = 'vert_table' # override this when you make an instance if you dont want vertical layout by default
	# column_html_attrs = {'style':'text-align: center; min-width:10px', 'bgcolor':"#FF0000"} # gets assigned to both th and td
	# column_html_attrs = [] # javascript tableswapper does not preserve these.
	column_html_attrs = {'style':'word-wrap: break-word; max-width:120px;'}
	classes = [] # gets assigned to table classes. 
	# Striped is alternating bright and dark rows for visual ease.
	datetime_submitted = DateTimeCol('datetime submitted')

	username = Col('username',column_html_attrs=column_html_attrs)
	request_name = Col('request name',column_html_attrs=column_html_attrs)
	description = AbbrevDescriptionCol('description',column_html_attrs=column_html_attrs)
	species = Col('species',column_html_attrs=column_html_attrs)
	archival_tooltip_text = ('An archival request is a request '
		'that was not submitted through this web portal, '
		'but was manually entered after the experiment '
		 'was already done. As a result, information may be incomplete '
		 'and not all data products or visualizations may be available.')
	archival_html_attrs = {'class':'infolink','title':archival_tooltip_text}
	is_archival = BooltoStringCol('archival?',column_html_attrs=column_html_attrs,
		th_html_attrs=archival_html_attrs)
	number_of_samples = Col('number of samples',column_html_attrs=column_html_attrs)
	fraction_cleared = Col('fraction cleared',column_html_attrs=column_html_attrs)
	fraction_imaged = Col('fraction imaged*',column_html_attrs=column_html_attrs)
	fraction_processed = Col('fraction processed**',column_html_attrs=column_html_attrs)

	url_kwargs = {'username':'username','request_name':'request_name'}
	# anchor_attrs = {'target':"_blank",}
	anchor_attrs = {}
	
	samples_link = LinkCol('View request status', 'requests.request_overview',url_kwargs=url_kwargs,
		anchor_attrs=anchor_attrs,allow_sort=False)
	delete_request_kwargs = {'username':'username','request_name':'request_name'}
	delete_request_tooltip_text = ('If this column shows "N/A" '
		'then you can no longer delete the request at this point. '
		'This is because at least one of the clearing batches '
		'in this request either is currently undergoing clearing or has already been cleared. '
		 'Contact lightservhelper@gmail.com if you still need to delete this request. ')
	delete_request_html_attrs = {'class':'infolink','title':delete_request_tooltip_text}
	
	delete_request_link = ConditionalDeleteLinkCol('Delete request?', 'requests.delete_request',url_kwargs=delete_request_kwargs,
		anchor_attrs={
        "data-toggle":"modal",
        "data-target":"#deleteModal",
        "id":"delete_modal"
		},th_html_attrs=delete_request_html_attrs,
		allow_sort=False)
	
	def get_tr_attrs(self, item, reverse=False):
		fraction_cleared_str = item['fraction_cleared']
		n_cleared,n_possible_to_clear = map(int,fraction_cleared_str.split("/"))

		fraction_imaged_str = item['fraction_imaged']
		n_imaged,n_possible_to_image = map(int,fraction_imaged_str.split("/"))

		fraction_processed_str = item['fraction_processed']
		n_processed,n_possible_to_process = map(int,fraction_processed_str.split("/"))
		
		if n_cleared == n_possible_to_clear and n_imaged == n_possible_to_image and \
			n_processed == n_possible_to_process: # request was completely fulfilled
			return {'bgcolor':'#A4FCAC'} # green
		elif n_cleared > 0: # in progress
			return {'bgcolor':'#A4FCFA'} # cyan
		else: # nothing done yet
			return {'bgcolor':'#FCA5A4'} # red
		   
	def sort_url(self, col_key, reverse=False):
		if reverse:
			direction = 'desc'
		else:
			direction = 'asc'
		next_url = os.path.join('/',*request.url.split('?')[0].split('/')[3:])
		next_url += f'?sort={col_key}&direction={direction}&table_id={self.table_id}'
		return next_url

class AllSamplesTable(Table):
	""" The table shown at the all_samples() route """
	border = True
	allow_sort = True
	no_items = "No Samples Yet"
	html_attrs = {"style":'font-size:18px',} # gets assigned to table header
	table_id = 'vert_table' # override this when you make an instance if you dont want vertical layout by default
	# column_html_attrs = {'style':'text-align: center; min-width:10px', 'bgcolor':"#FF0000"} # gets assigned to both th and td
	# column_html_attrs = [] # javascript tableswapper does not preserve these.
	column_html_attrs = {'style':'word-wrap: break-word; max-width:200px;'}

	classes = ["table-striped"] # gets assigned to table classes. 
	# Striped is alternating bright and dark rows for visual ease.
	sample_name = Col('sample name',column_html_attrs=column_html_attrs)
	request_name = Col('request name',column_html_attrs=column_html_attrs)
	username = Col('username',column_html_attrs=column_html_attrs)
	archival_tooltip_text = ('An archival request is a request '
		'that was not submitted through this web portal, '
		'but was manually entered after the experiment '
		 'was already done. As a result, information may be incomplete '
		 'and not all data products or visualizations may be available.')
	archival_html_attrs = {'class':'infolink','title':archival_tooltip_text}
	is_archival = BooltoStringCol('archival?',column_html_attrs=column_html_attrs,
		th_html_attrs=archival_html_attrs)
	species = Col('species',column_html_attrs=column_html_attrs)
	clearing_protocol = Col('clearing protocol')
	clearer = NotAssignedCol('clearer')
	clearing_progress = Col('clearing progress')
	# antibody1 = Col('antibody1')
	# antibody2 = Col('antibody2')
	clearing_url_kwargs = {'username':'username','request_name':'request_name',
	'clearing_protocol':'clearing_protocol',
	'antibody1':'antibody1','antibody2':'antibody2','clearing_batch_number':'clearing_batch_number'}
	anchor_attrs = {}
	clearing_log = ClearingTableLinkCol('Clearing log', 
		'clearing.clearing_table',url_kwargs=clearing_url_kwargs,
	   anchor_attrs=anchor_attrs,allow_sort=False)
	datetime_submitted = DateTimeCol('datetime submitted')
	imaging_url_kwargs = {'username':'username','request_name':'request_name','sample_name':'sample_name'}
	new_imaging_request_tooltip_text = ('Not available for archival requests. '
		'Please only request additional imaging for this sample '
		'if your original request did not cover the sufficient imaging. '
		 'To see what imaging you have already requested, '
		 'click on the existing imaging request number(s) for this sample. '
		 'If this field shows "N/A" it is because no processing is possible for this sample.')
	new_imaging_request_html_attrs = {'class':'infolink','title':new_imaging_request_tooltip_text}

	new_imaging_request = NewImagingRequestLinkCol('Request additional imaging',
		'imaging.new_imaging_request',url_kwargs=imaging_url_kwargs,
		th_html_attrs=new_imaging_request_html_attrs,allow_sort=False)

	""" Imaging requests subtable setup """
	imaging_request_subtable_options = {
	'table_id':f'imaging_requests',
	'border':True,
	}
	imaging_requests_subtable_class = create_table('imaging_request_subtable',
		options=imaging_request_subtable_options)
	imaging_request_url_kwargs = {'username':'username',
		'request_name':'request_name','sample_name':'sample_name',
		'imaging_request_number':'imaging_request_number'}
	imaging_requests_subtable_class.add_column('imaging_request_number',
		ImagingRequestLinkCol('imaging request number','imaging.imaging_table',
			url_kwargs=imaging_request_url_kwargs))
	imaging_requests_subtable_class.add_column('imager',
		NotAssignedCol('imager'))
	imaging_requests_subtable_class.add_column('imaging_progress',
		Col('imaging progress'))
	processing_url_kwargs = {'username':'username','request_name':'request_name',
	'sample_name':'sample_name','imaging_request_number':'imaging_request_number'}
	new_processing_request_tooltip_text = ('Not available for archival requests. '
		'Please only request additional processing for this sample and imaging request '
		'if your original request did not cover the sufficient processing. '
		 'To see what processing you have already requested, '
		 'click on the existing processing request number(s) corresponding to this imaging request. '
		 'If this field shows "N/A" it is because no processing is possible for this sample.')
	new_processing_request_html_attrs = {'class':'infolink','title':new_processing_request_tooltip_text}
	imaging_requests_subtable_class.add_column('new processing request',
		NewProcessingRequestLinkCol('request additional processing',
			'processing.new_processing_request',url_kwargs=processing_url_kwargs,
			allow_sort=False,th_html_attrs=new_processing_request_html_attrs))
	
	""" Processing requests subtable setup """
	processing_request_subtable_options = {
	'table_id':f'processing_requests',
	'border':True,
	}
	processing_requests_subtable_class = create_table('processing_request_subtable',
		options=processing_request_subtable_options)
	processing_request_url_kwargs = {'username':'username',
		'request_name':'request_name','sample_name':'sample_name',
		'imaging_request_number':'imaging_request_number',
		'processing_request_number':'processing_request_number'}
	processing_requests_subtable_class.add_column('processing_request_number',
		ProcessingRequestLinkCol('processing request number','processing.processing_table',
			url_kwargs=processing_request_url_kwargs))
	processing_requests_subtable_class.add_column('processor',
		NotAssignedCol('processor'))
	processing_requests_subtable_class.add_column('processing_progress',
		Col('processing progress'))
	processing_requests_subtable_class.add_column('visualization',
		LinkCol('Viz', 'neuroglancer.general_data_setup',
			url_kwargs=processing_request_url_kwargs,
			allow_sort=False)
	)
	
	imaging_requests_subtable_class.add_column('processing_requests',
		NestedTableCol('Processing Requests',processing_requests_subtable_class,allow_sort=False))
	
	""" Finally add the imaging requests column to the main table 
	(which is a nested table containing a nested table ) """
	imaging_requests = NestedTableCol('Imaging Requests',
		imaging_requests_subtable_class,allow_sort=False)
	
	
	def sort_url(self, col_key, reverse=False):
		if reverse:
			direction = 'desc'
		else:
			direction = 'asc'
		next_url = os.path.join('/',*request.url.split('?')[0].split('/')[3:])
		next_url += f'?sort={col_key}&direction={direction}&table_id={self.table_id}'
		return next_url

class RequestOverviewTable(Table):
	""" A table for showing a brief overview of a request """
	border = True
	allow_sort = False
	no_items = "No Requests Yet"
	html_attrs = {"style":'font-size:18px',} # gets assigned to table header
	table_id = 'vert_table' # override this when you make an instance if you dont want vertical layout by default
	# column_html_attrs = {'style':'text-align: center; min-width:10px', 'bgcolor':"#FF0000"} # gets assigned to both th and td
	# column_html_attrs = [] # javascript tableswapper does not preserve these.
	column_html_attrs = {'style':'word-wrap: break-word; max-width:200px;'}

	classes = ["table-striped"] # gets assigned to table classes. 
	# Striped is alternating bright and dark rows for visual ease.
	datetime_submitted = DateTimeCol('datetime submitted')

	username = Col('username',column_html_attrs=column_html_attrs)
	request_name = Col('request name',column_html_attrs=column_html_attrs)
	description = Col('description',column_html_attrs=column_html_attrs)
	species = Col('species',column_html_attrs=column_html_attrs)
	number_of_samples = Col('number of samples',column_html_attrs=column_html_attrs)

def create_dynamic_samples_table(contents,table_id,ignore_columns=[],name='Dynamic Samples Table', **sort_kwargs):
	""" Table showing all samples of a given request, used in the 
	request_overview() route """
	def dynamic_sort_url(self, col_key, reverse=False):
		if reverse:
			direction = 'desc'
		else:
			direction = 'asc'

		next_url = os.path.join('/',*request.url.split('?')[0].split('/')[3:])
		next_url += f'?sort={col_key}&direction={direction}'
		return next_url

	options = dict(
		border = True,
		allow_sort = True,
		no_items = "No Samples",
		html_attrs = {"style":'font-size:18px;'},
		table_id = table_id,
		classes = ["table-striped","mb-4"]
		) 
	column_html_attrs = {'style':'word-wrap: break-word; max-width:200px;'}
	table_class = create_table(name,options=options)
	table_class.sort_url = dynamic_sort_url
	sort = sort_kwargs.get('sort_by','sample_name')
	reverse = sort_kwargs.get('sort_reverse',False)
	""" Now loop through all columns and add them to the table,
	only adding the imaging modes if they are used in at least one
	sample """
	""" Add the columns that you want to go first here.
	It is OK if they get duplicated in the loop below -- they
	will not be added twice """
	table_class.add_column('sample_name',Col('sample name',column_html_attrs=column_html_attrs))    
	table_class.add_column('request_name',Col('request name',column_html_attrs=column_html_attrs))
	table_class.add_column('username',Col('username',column_html_attrs=column_html_attrs))
	archival_tooltip_text = ('An archival request is a request '
		'that was not submitted through this web portal, '
		'but was manually entered after the experiment '
		 'was already done. As a result, information may be incomplete '
		 'and not all data products or visualizations may be available.')
	archival_html_attrs = {'class':'infolink','title':archival_tooltip_text}
	table_class.add_column('is_archival',BooltoStringCol('archival?',column_html_attrs=column_html_attrs,
		th_html_attrs=archival_html_attrs))
	table_class.add_column('clearing_protocol',
		Col('clearing protocol',column_html_attrs=column_html_attrs))
	
	table_class.add_column('clearer',
		NotAssignedCol('clearer',column_html_attrs=column_html_attrs))
	table_class.add_column('clearing_progress',
		Col('clearing progress',column_html_attrs=column_html_attrs))

	clearing_url_kwargs = {'username':'username','request_name':'request_name',
		'clearing_protocol':'clearing_protocol',
		'antibody1':'antibody1','antibody2':'antibody2','clearing_batch_number':'clearing_batch_number'}
	anchor_attrs = {}
	table_class.add_column('view_clearing_link',
		 ClearingTableLinkCol('Clearing log', 
		'clearing.clearing_table',url_kwargs=clearing_url_kwargs,
	   anchor_attrs=anchor_attrs,allow_sort=False,column_html_attrs=column_html_attrs))
	
	imaging_request_subtable_options = {
	'table_id':f'imaging_requests',
	'border':True,
	}
	imaging_requests_subtable_class = create_table('imaging_request_subtable',
		options=imaging_request_subtable_options)
	imaging_request_url_kwargs = {'username':'username',
		'request_name':'request_name','sample_name':'sample_name',
		'imaging_request_number':'imaging_request_number'}
	imaging_requests_subtable_class.add_column('imaging_request_number',
		ImagingRequestLinkCol('imaging request number','imaging.imaging_table',
			url_kwargs=imaging_request_url_kwargs,column_html_attrs=column_html_attrs))
	imaging_requests_subtable_class.add_column('imager',
		NotAssignedCol('imager',column_html_attrs=column_html_attrs))
	imaging_requests_subtable_class.add_column('imaging_progress',
		Col('imaging progress',column_html_attrs=column_html_attrs))
	imaging_url_kwargs = {'username':'username','request_name':'request_name','sample_name':'sample_name'}
	new_imaging_request_tooltip_text = ('Not available for archival requests. '
		'Please only request additional imaging for this sample '
		'if your original request did not cover the sufficient imaging. '
		 'To see what imaging you have already requested, '
		 'click on the existing imaging request number(s) for this sample. '
		 'If this field shows "N/A" it is because no additional imaging is possible for this sample.')
	new_imaging_request_html_attrs = {'class':'infolink','title':new_imaging_request_tooltip_text}

	table_class.add_column('new imaging request',
		NewImagingRequestLinkCol('request additional imaging','imaging.new_imaging_request',
			url_kwargs=imaging_url_kwargs,th_html_attrs=new_imaging_request_html_attrs,
			allow_sort=False,column_html_attrs=column_html_attrs))

	processing_request_subtable_options = {
	'table_id':f'processing_requests',
	'border':True,
	}

	processing_requests_subtable_class = create_table('processing_request_subtable',
		options=processing_request_subtable_options)
	processing_request_url_kwargs = {'username':'username',
		'request_name':'request_name','sample_name':'sample_name',
		'imaging_request_number':'imaging_request_number',
		'processing_request_number':'processing_request_number'}
	processing_requests_subtable_class.add_column('processing_request_number',
		ProcessingRequestLinkCol('processing request number','processing.processing_table',
			url_kwargs=processing_request_url_kwargs,
			column_html_attrs=column_html_attrs))
	processing_requests_subtable_class.add_column('processor',
		NotAssignedCol('processor',
		column_html_attrs=column_html_attrs))
	processing_requests_subtable_class.add_column('processing_progress',
		Col('processing progress',
		column_html_attrs=column_html_attrs))
	processing_requests_subtable_class.add_column('visualization',
		LinkCol('Viz', 'neuroglancer.general_data_setup',
			url_kwargs=processing_request_url_kwargs,
			allow_sort=False,
			column_html_attrs=column_html_attrs))
	processing_url_kwargs = {'username':'username','request_name':'request_name',
	'sample_name':'sample_name','imaging_request_number':'imaging_request_number'}
	new_processing_request_tooltip_text = ('Not available for archival requests. '
		'Please only request additional processing for this sample and imaging request '
		'if your original request did not cover the sufficient processing. '
		 'To see what processing you have already requested, '
		 'click on the existing processing request number(s) corresponding to this imaging request. '
		 'If this field shows "N/A" it is because no processing is possible for this sample.')
	new_processing_request_html_attrs = {'class':'infolink','title':new_processing_request_tooltip_text}
	
	imaging_requests_subtable_class.add_column('new processing request',
		NewProcessingRequestLinkCol('request additional processing','processing.new_processing_request',
			url_kwargs=processing_url_kwargs,th_html_attrs=new_processing_request_html_attrs,
			column_html_attrs=column_html_attrs))
	imaging_requests_subtable_class.add_column('processing_requests',
		NestedTableCol('Processing Requests',processing_requests_subtable_class))

	table_class.add_column('imaging_requests',
		NestedTableCol('Imaging Requests',imaging_requests_subtable_class,
			allow_sort=False))
	
	sorted_contents = sorted(contents,
			key=partial(table_sorter,sort_key=sort),reverse=reverse)
	table = table_class(sorted_contents)
	table.sort_by = sort
	table.sort_reverse = reverse
	
	return table 
