from flask import url_for,flash,redirect, request
from flask_table import Table, Col, LinkCol, ButtonCol, create_table
from lightserv.main.tables import HeadingCol, ConditionalLinkCol
from functools import partial
from lightserv.main.utils import table_sorter
from lightserv.main.tables import DateTimeCol
from lightserv import db_lightsheet
import os

class AllRequestTable(Table):
    border = True
    allow_sort = True
    no_items = "No Requests Yet"
    html_attrs = {"style":'font-size:18px',} # gets assigned to table header
    table_id = 'vert_table' # override this when you make an instance if you dont want vertical layout by default
    # column_html_attrs = {'style':'text-align: center; min-width:10px', 'bgcolor':"#FF0000"} # gets assigned to both th and td
    column_html_attrs = [] # javascript tableswapper does not preserve these.
    classes = ["table-striped"] # gets assigned to table classes. 
    # Striped is alternating bright and dark rows for visual ease.
    datetime_submitted = DateTimeCol('datetime submitted')

    username = Col('username',column_html_attrs=column_html_attrs)
    request_name = Col('request name',column_html_attrs=column_html_attrs)
    description = Col('description',column_html_attrs=column_html_attrs)
    species = Col('species',column_html_attrs=column_html_attrs)
    number_of_samples = Col('number of samples',column_html_attrs=column_html_attrs)
    fraction_cleared = Col('fraction cleared',column_html_attrs=column_html_attrs)
    fraction_imaged = Col('fraction imaged*',column_html_attrs=column_html_attrs)
    fraction_processed = Col('fraction processed**',column_html_attrs=column_html_attrs)
    
    # sample_prefix = Col('sample prefix')


    url_kwargs = {'username':'username','request_name':'request_name'}
    anchor_attrs = {'target':"_blank",}
    
    samples_link = LinkCol('View request status', 'requests.request_overview',url_kwargs=url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False)
    
    def sort_url(self, col_key, reverse=False):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'
        next_url = os.path.join('/',*request.url.split('?')[0].split('/')[3:])
        next_url += f'?sort={col_key}&direction={direction}&table_id={self.table_id}'
        return next_url


class AllSamplesTable(Table):
    border = True
    allow_sort = True
    no_items = "No Requests Yet"
    html_attrs = {"style":'font-size:18px',} # gets assigned to table header
    table_id = 'vert_table' # override this when you make an instance if you dont want vertical layout by default
    # column_html_attrs = {'style':'text-align: center; min-width:10px', 'bgcolor':"#FF0000"} # gets assigned to both th and td
    column_html_attrs = [] # javascript tableswapper does not preserve these.
    classes = ["table-striped"] # gets assigned to table classes. 
    # Striped is alternating bright and dark rows for visual ease.
    sample_name = Col('sample name',column_html_attrs=column_html_attrs)
    username = Col('username',column_html_attrs=column_html_attrs)
    request_name = Col('request name',column_html_attrs=column_html_attrs)
    species = Col('species',column_html_attrs=column_html_attrs)
    datetime_submitted = DateTimeCol('datetime submitted')

    # fraction_cleared = Col('fraction cleared',column_html_attrs=column_html_attrs)
    # fraction_imaged = Col('fraction imaged*',column_html_attrs=column_html_attrs)
    # fraction_processed = Col('fraction processed**',column_html_attrs=column_html_attrs)

    # url_kwargs = {'username':'username','request_name':'request_name'}
    # anchor_attrs = {'target':"_blank",}
    
    # samples_link = LinkCol('View request status', 'requests.request_overview',url_kwargs=url_kwargs,
    #     anchor_attrs=anchor_attrs,allow_sort=False)
    
    def sort_url(self, col_key, reverse=False):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'
        next_url = os.path.join('/',*request.url.split('?')[0].split('/')[3:])
        next_url += f'?sort={col_key}&direction={direction}&table_id={self.table_id}'
        return next_url

class RequestOverviewTable(Table):
    border = True
    allow_sort = True
    no_items = "No Requests Yet"
    html_attrs = {"style":'font-size:18px',} # gets assigned to table header
    table_id = 'vert_table' # override this when you make an instance if you dont want vertical layout by default
    # column_html_attrs = {'style':'text-align: center; min-width:10px', 'bgcolor':"#FF0000"} # gets assigned to both th and td
    column_html_attrs = [] # javascript tableswapper does not preserve these.
    classes = ["table-striped"] # gets assigned to table classes. 
    # Striped is alternating bright and dark rows for visual ease.
    datetime_submitted = DateTimeCol('datetime submitted')

    username = Col('username',column_html_attrs=column_html_attrs)
    request_name = Col('request name',column_html_attrs=column_html_attrs)
    description = Col('description',column_html_attrs=column_html_attrs)
    species = Col('species',column_html_attrs=column_html_attrs)
    number_of_samples = Col('number of samples',column_html_attrs=column_html_attrs)

        
    def sort_url(self, col_key, reverse=False):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'
        next_url = os.path.join('/',*request.url.split('?')[0].split('/')[3:])
        next_url += f'?sort={col_key}&direction={direction}&table_id={self.table_id}'
        return next_url

def create_dynamic_samples_table(contents,table_id,ignore_columns=[],name='Dynamic Samples Table', **sort_kwargs):
    def dynamic_sort_url(self, col_key, reverse=False):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'

        next_url = os.path.join('/',*request.url.split('?')[0].split('/')[3:])
        next_url += f'?sort={col_key}&direction={direction}&table_id={table_id}'
        return next_url

    options = dict(
        border = True,
        allow_sort = True,
        no_items = "No Samples",
        html_attrs = {"style":'font-size:18px;'}, 
        table_id = table_id,
        classes = ["table-striped","mb-4"]
        ) 

    table_class = create_table(name,options=options)
    table_class.sort_url = dynamic_sort_url
    sort = sort_kwargs.get('sort_by','sample_name')
    reverse = sort_kwargs.get('sort_reverse',False)
    """ Now loop through all columns and add them to the table,
    only adding the imaging modes if they are used in at least one
    sample """
    colnames = contents.heading.names
    """ Add the columns that you want to go first here.
    It is OK if they get duplicated in the loop below -- they
    will not be added twice """
    table_class.add_column('sample_name',Col('sample name'))    
    table_class.add_column('request_name',Col('request name'))
    table_class.add_column('username',Col('username'))
    table_class.add_column('imaging_request_number',Col('imaging request number'))
    # table_class.add_column('perfusion_date',Col('perfusion date'))
    # table_class.add_column('expected_handoff_date',Col('expected handoff date'))
    # table_class.add_column('clearer',Col('clearer'))
    table_class.add_column('clearing_protocol',Col('clearing protocol'))
    # table_class.add_column('clearing_progress',Col('clearing progress'))
    table_class.add_column('antibody1',Col('antibody 1'))
    table_class.add_column('antibody2',Col('antibody 2'))
    table_class.add_column('imaging_progress',Col('imaging progress'))

    """ Now add in the link columns """
    # clearing_url_kwargs = {'username':'username','request_name':'request_name',
    # 'sample_name':'sample_name','clearing_protocol':'clearing_protocol',
    # 'antibody1':'antibody1','antibody2':'antibody2'}
    imaging_url_kwargs = {'username':'username','request_name':'request_name',
    'sample_name':'sample_name',}
    processing_url_kwargs = {'username':'username','request_name':'request_name',
    'sample_name':'sample_name','imaging_request_number':'imaging_request_number'}
    anchor_attrs = {'target':"_blank",}
    # table_class.add_column('view_clearing_link',
    #      LinkCol('View clearing log', 
    #     'clearing.clearing_table',url_kwargs=clearing_url_kwargs,
    #    anchor_attrs=anchor_attrs,allow_sort=False))
    
    table_class.add_column('new imaging request',
        LinkCol('New imaging request', 
        'imaging.new_imaging_request',url_kwargs=imaging_url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False))
   
    table_class.add_column('new processing request',
        LinkCol('New processing request', 
        'processing.new_processing_request',url_kwargs=processing_url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False))
   
    sorted_contents = sorted(contents.fetch(as_dict=True),
            key=partial(table_sorter,sort_key=sort),reverse=reverse)
    table = table_class(sorted_contents)
    table.sort_by = sort
    table.sort_reverse = reverse
    
    return table 
