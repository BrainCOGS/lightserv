from flask import request
from flask_table import Table, Col, LinkCol, ButtonCol, create_table
from functools import partial
from lightserv.main.utils import table_sorter

def dynamic_processing_management_table(contents,table_id,ignore_columns=[],
    name='Dynamic Processing Management Table', **sort_kwargs):
    def dynamic_sort_url(self, col_key, reverse=False):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'

        next_url = request.url.split('?')[0]
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
        no_items = "No jobs at the moment",
        html_attrs = {"style":'font-size:18px'}, 
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
    table_class.add_column('datetime_submitted',Col('datetime submitted'))
    table_class.add_column('request_name',Col('experiment name'))
    table_class.add_column('sample_name',Col('sample name'))
    table_class.add_column('username',Col('username'))    
    table_class.add_column('imaging_request_number',Col('imaging request number'))    
    
    if table_class == 'horizontal_ready_to_process_table':
        table_class.add_column('processing_progress',BoldTextCol('processing_progress'))
    else: 
        table_class.add_column('imaging_progress',Col('imaging progress'))
    table_class.add_column('imager',Col('imager'))
    table_class.add_column('species',Col('species'))    

    ''' Now only add the start_imaging_link if the table is being imaged or ready to image '''
    processing_url_kwargs = {'username':'username','request_name':'request_name',
        'sample_name':'sample_name','imaging_request_number':'imaging_request_number'}

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
    table_class.add_column('channel_name',Col('channel_name'))
    table_class.add_column('tiling_scheme',Col('tiling_scheme'))
    table_class.add_column('processor',Col('processor'))
    table_class.add_column('processing_progress',Col('processing_progress'))

    table = table_class(contents)
    
    return table 
