from flask import request
from flask_table import Table, Col, LinkCol, ButtonCol, create_table
from functools import partial
from lightserv.main.utils import table_sorter
from lightserv.main.tables import DateTimeCol, BoldTextCol,DesignatedRoleCol, BooltoStringCol
import os

def dynamic_processing_management_table(contents,table_id,ignore_columns=[],
    name='Dynamic Processing Management Table', **sort_kwargs):
    def dynamic_sort_url(self, col_key, reverse=False):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'

        next_url = os.path.join('/',*request.url.split('?')[0].split('/')[3:])
        next_url += f'?sort={col_key}&direction={direction}&table_id={table_id}'
        return next_url
    
    def dynamic_get_tr_attrs(self, item, reverse=False):
        if item['imaging_request_number'] > 1:
            return {'bgcolor':'#FCA5A4'} # red
        else:
            return {}

    options = dict(
        border = True,
        allow_sort = True,
        no_items = "No samples at the moment",
        html_attrs = {"style":'font-size:18px;'}, 
        table_id = table_id,
        classes = ["table-striped"]
        ) 

    table_class = create_table(name,options=options)
    table_class.get_tr_attrs = dynamic_get_tr_attrs
    table_class.sort_url = dynamic_sort_url
    sort = sort_kwargs.get('sort_by','datetime_submitted')
    reverse = sort_kwargs.get('sort_reverse',False)
    """ Add the columns that you want to go first here.
    It is OK if they get duplicated in the loop below -- they
    will not be added twice """
    table_class.add_column('datetime_submitted',DateTimeCol('datetime submitted'))
    table_class.add_column('request_name',Col('request name'))
    table_class.add_column('sample_name',Col('sample name'))
    table_class.add_column('username',Col('username'))    
    table_class.add_column('imaging_request_number',Col('imaging request number'))    
    table_class.add_column('processing_request_number',Col('processing request number'))    

    if not table_class.table_id == 'horizontal_ready_to_process_table':
        table_class.add_column('processing_progress',Col('processing progress'))

    if table_class.table_id == 'horizontal_on_deck_table':
        table_class.add_column('imager',DesignatedRoleCol('imager'))

    table_class.add_column('processor',DesignatedRoleCol('processor'))
    table_class.add_column('species',Col('species'))    

    ''' Now only add the start_imaging_link if the table is being imaged or ready to image '''
    processing_url_kwargs = {'username':'username','request_name':'request_name',
        'sample_name':'sample_name','imaging_request_number':'imaging_request_number',
        'processing_request_number':'processing_request_number'}

    anchor_attrs = {'target':"_blank",}
    if table_id == 'horizontal_ready_to_process_table':
        table_class.add_column('start_processing_link',LinkCol('Start processing',
         'processing.processing_entry',url_kwargs=processing_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
    elif table_id == 'horizontal_being_processing_table':
        table_class.add_column('continue_processing_link',LinkCol('Continue processing',
         'processing.processing_entry',url_kwargs=processing_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
    elif table_id == 'horizontal_already_imaged_table':
        table_class.add_column('view_processing_link',LinkCol('View processing log',
         'processing.processing_entry',url_kwargs=processing_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
         
    sorted_contents = sorted(contents.fetch(as_dict=True),
            key=partial(table_sorter,sort_key=sort),reverse=reverse)
    table = table_class(sorted_contents)
    table.sort_by = sort
    table.sort_reverse = reverse
    
    return table 

def create_dynamic_channels_table_for_processing(contents,table_id,ignore_columns=[],
    name='Dynamic Channels Table for Processing'):
    options = dict(
        border = True,
        allow_sort = False,
        no_items = "No Samples",
        html_attrs = {"style":'font-size:18px'}, 
        table_id = table_id,
        classes = ["table-striped"]
        ) 

    table_class = create_table(name,options=options)
    """ Add the columns that you want to go first here.
    It is OK if they get duplicated in the loop below -- they
    will not be added twice """
    table_class.add_column('username',Col('username'))
    table_class.add_column('request_name',Col('request_name'))
    table_class.add_column('sample_name',Col('sample_name'))
    table_class.add_column('image_resolution',Col('image_resolution'))
    table_class.add_column('imaging_request_number',Col('imaging request number'))
    table_class.add_column('processing_request_number',Col('processing request number'))
    # table_class.add_column('channel_name',Col('channel_name'))
    # table_class.add_column('tiling_scheme',Col('tiling_scheme'))
    table_class.add_column('processor',Col('processor'))
    table_class.add_column('processing_progress',Col('processing progress'))

    table = table_class(contents)
    
    return table 

class ImagingOverviewTable(Table):
    """ A table to show an overview of the imaging 
    performed for a given imaging_request_number """ 
    border = True
    allow_sort=False
    no_items = "No processing requested yet"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    imaging_request_number = Col('imaging request number',column_html_attrs=column_html_attrs)
    username = Col('username',column_html_attrs=column_html_attrs)
    request_name = Col('request name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample name',column_html_attrs=column_html_attrs)
    image_resolution = Col('image resolution',column_html_attrs=column_html_attrs)
    channel_name = Col('channel name',column_html_attrs=column_html_attrs)


class ExistingProcessingTable(Table):
    """ A table to show the existing processing already
    requested for a given sample """ 
    border = True
    allow_sort=False
    no_items = "No processing requested yet"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    imaging_request_number = Col('imaging request number',column_html_attrs=column_html_attrs)
    processing_request_number = Col('processing request number',column_html_attrs=column_html_attrs)
    image_resolution = Col('image resolution',column_html_attrs=column_html_attrs)
    channel_name = Col('channel name',column_html_attrs=column_html_attrs)
    registration = BooltoStringCol('registration',column_html_attrs=column_html_attrs)
    injection_detection = BooltoStringCol('injection detection',column_html_attrs=column_html_attrs)
    probe_detection = BooltoStringCol('probe detection',column_html_attrs=column_html_attrs)
    cell_detection = BooltoStringCol('cell detection',column_html_attrs=column_html_attrs)
    atlas_name = Col('atlas name',column_html_attrs=column_html_attrs)