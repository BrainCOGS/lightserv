from flask import request
from flask_table import Table, Col, LinkCol, ButtonCol, create_table
from functools import partial
from lightserv.main.utils import table_sorter
from lightserv.main.tables import (DateTimeCol, DesignatedRoleCol,
    BooltoStringCol, ProgressCol,ChannelPurposeCol,DorsalOrVentralCol)
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
        html_attrs = {"style":'font-size:16px; width=100%'}, 
        table_id = table_id,
        classes = ["table-striped"]
        ) 
    column_html_attrs = {'style':'word-wrap: break-word; max-width:150px;'}

    table_class = create_table(name,options=options)
    table_class.get_tr_attrs = dynamic_get_tr_attrs
    table_class.sort_url = dynamic_sort_url
    sort = sort_kwargs.get('sort_by','datetime_submitted')
    reverse = sort_kwargs.get('sort_reverse',False)
    """ Add the columns that you want to go first here.
    It is OK if they get duplicated in the loop below -- they
    will not be added twice """

    ''' Now only add the start_imaging_link if the table is being imaged or ready to image '''
    processing_url_kwargs = {'username':'username','request_name':'request_name',
        'sample_name':'sample_name','imaging_request_number':'imaging_request_number',
        'processing_request_number':'processing_request_number'}

    anchor_attrs = {}
    if table_id == 'horizontal_ready_to_process_table':
        table_class.add_column('start_processing_link',LinkCol('Start processing',
         'processing.processing_entry',url_kwargs=processing_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
    elif table_id == 'horizontal_being_processed_table':
        table_class.add_column('continue_processing_link',LinkCol('Continue processing',
         'processing.processing_entry',url_kwargs=processing_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
    elif table_id == 'horizontal_already_processed_table':
        table_class.add_column('view_processing_link',LinkCol('View processing log',
         'processing.processing_entry',url_kwargs=processing_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
    table_class.add_column('datetime_submitted',DateTimeCol('datetime submitted'))
    table_class.add_column('request_name',Col('request name',
        column_html_attrs=column_html_attrs))
    table_class.add_column('sample_name',Col('sample name',
        column_html_attrs=column_html_attrs))
    table_class.add_column('username',Col('username',
        column_html_attrs=column_html_attrs))    
    table_class.add_column('imaging_request_number',Col('imaging request number',
        column_html_attrs=column_html_attrs))    
    table_class.add_column('processing_request_number',Col('processing request number',
        column_html_attrs=column_html_attrs))    

    if not table_class.table_id == 'horizontal_ready_to_process_table':
        table_class.add_column('processing_progress',Col('processing progress'))

    if table_class.table_id == 'horizontal_on_deck_table':
        table_class.add_column('imager',DesignatedRoleCol('imager'))

    table_class.add_column('processor',DesignatedRoleCol('processor'))
    table_class.add_column('species',Col('species'))    
    
         
    sorted_contents = sorted(contents.fetch(as_dict=True),
            key=partial(table_sorter,sort_key=sort),reverse=reverse)
    table = table_class(sorted_contents)
    table.sort_by = sort
    table.sort_reverse = reverse
    
    return table 

def create_dynamic_processing_overview_table(contents,table_id,ignore_columns=[],
    name='Dynamic Channels Table for Processing'):
    options = dict(
        border = True,
        allow_sort = False,
        no_items = "No Samples",
        html_attrs = {"style":'font-size:16px; width=100%'}, 
        table_id = table_id,
        classes = ["table-striped"]
        ) 
    column_html_attrs = {'style':'word-wrap: break-word; max-width:150px;'}

    table_class = create_table(name,options=options)
    """ Add the columns that you want to go first here.
    It is OK if they get duplicated in the loop below -- they
    will not be added twice """
    table_class.add_column('username',Col('username',column_html_attrs=column_html_attrs))
    table_class.add_column('request_name',Col('request name',column_html_attrs=column_html_attrs))
    table_class.add_column('sample_name',Col('sample name',column_html_attrs=column_html_attrs))
    table_class.add_column('image_resolution',Col('image resolution',column_html_attrs=column_html_attrs))
    table_class.add_column('imaging_request_number',Col('imaging request number',column_html_attrs=column_html_attrs))
    table_class.add_column('processing_request_number',Col('processing request number',column_html_attrs=column_html_attrs))
    table_class.add_column('ventral_up',DorsalOrVentralCol('Dorsal up or Ventral up?',column_html_attrs=column_html_attrs))
    table_class.add_column('processor',Col('processor',column_html_attrs=column_html_attrs))
    table_class.add_column('processing_progress',ProgressCol('processing progress',column_html_attrs=column_html_attrs))

    table = table_class(contents)
    
    return table 

def dynamic_pystripe_management_table(contents,table_id,ignore_columns=[],
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
        html_attrs = {"style":'font-size:16px; width=100%'}, 
        table_id = table_id,
        classes = ["table-striped"]
        ) 
    column_html_attrs = {'style':'word-wrap: break-word; max-width:150px;'}

    table_class = create_table(name,options=options)
    table_class.get_tr_attrs = dynamic_get_tr_attrs
    table_class.sort_url = dynamic_sort_url
    sort = sort_kwargs.get('sort_by','datetime_submitted')
    reverse = sort_kwargs.get('sort_reverse',False)
    """ Add the columns that you want to go first here.
    It is OK if they get duplicated in the loop below -- they
    will not be added twice """

    ''' Now only add the start_imaging_link if the table is being imaged or ready to image '''
    pystripe_url_kwargs = {'username':'username','request_name':'request_name',
        'sample_name':'sample_name','imaging_request_number':'imaging_request_number'}

    anchor_attrs = {}
    if table_id == 'horizontal_ready_to_pystripe_table':
        table_class.add_column('start_pystripe_link',LinkCol('Start form',
         'processing.pystripe_entry',url_kwargs=pystripe_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
    elif table_id == 'horizontal_currently_being_pystriped_table':
        table_class.add_column('continue_form_link',LinkCol('Continue form',
         'processing.pystripe_entry',url_kwargs=pystripe_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
    # table_class.add_column('datetime_submitted',DateTimeCol('datetime submitted'))
    table_class.add_column('request_name',Col('request name',
        column_html_attrs=column_html_attrs))
    table_class.add_column('sample_name',Col('sample name',
        column_html_attrs=column_html_attrs))
    table_class.add_column('username',Col('username',
        column_html_attrs=column_html_attrs))    
    table_class.add_column('imaging_request_number',Col('imaging request number',
        column_html_attrs=column_html_attrs))    

    sorted_contents = sorted(contents.fetch(as_dict=True),
            key=partial(table_sorter,sort_key=sort),reverse=reverse)
    table = table_class(sorted_contents)
    table.sort_by = sort
    table.sort_reverse = reverse
    
    return table 


class ImagingOverviewTable(Table):
    """ A table to show an overview of the imaging 
    performed for a given imaging_request_number """ 
    border = True
    allow_sort=False
    no_items = "No imaging requested yet"
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
    generic_imaging = BooltoStringCol('generic imaging',column_html_attrs=column_html_attrs)
    atlas_name = Col('atlas name',column_html_attrs=column_html_attrs)

class ProcessingChannelTable(Table):
    """ A table to show the ProcessingChannel() entries """ 
    border = True
    allow_sort=False
    no_items = "No channels processed yet"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    image_resolution = Col('image resolution',column_html_attrs=column_html_attrs)
    channel_name = Col('channel name',column_html_attrs=column_html_attrs)
    lightsheet_channel_str = ChannelPurposeCol('channel purpose',column_html_attrs=column_html_attrs)
    datetime_processing_started = DateTimeCol('datetime started',column_html_attrs=column_html_attrs)
    # registration = BooltoStringCol('registration',column_html_attrs=column_html_attrs)
    # injection_detection = BooltoStringCol('injection detection',column_html_attrs=column_html_attrs)
    # probe_detection = BooltoStringCol('probe detection',column_html_attrs=column_html_attrs)
    # cell_detection = BooltoStringCol('cell detection',column_html_attrs=column_html_attrs)
    # generic_imaging = BooltoStringCol('generic imaging',column_html_attrs=column_html_attrs)
    # atlas_name = Col('atlas name',column_html_attrs=column_html_attrs)