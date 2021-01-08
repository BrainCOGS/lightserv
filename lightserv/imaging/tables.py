from flask import request
from flask_table import create_table,Table, Col, LinkCol, ButtonCol
from functools import partial
from lightserv.main.utils import table_sorter
from lightserv.main.tables import (BooltoStringCol, DateTimeCol,
    DesignatedRoleCol, ProgressCol)
import os

def dynamic_imaging_management_table(contents,table_id,ignore_columns=[],
    name='Dynamic Imaging Management Table', **sort_kwargs):
    def dynamic_sort_url(self, col_key, reverse=False):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'

        next_url = os.path.join('/',*request.url.split('?')[0].split('/')[3:])
        next_url += f'?sort={col_key}&direction={direction}&table_id={table_id}'
        return next_url
    
    # def dynamic_get_tr_attrs(self, item, reverse=False):
    #     if item['imaging_request_number'] > 1:
    #         return {'bgcolor':'#757680'} # gray
    #     else:
    #         return {}

    options = dict(
        border = True,
        allow_sort = True,
        no_items = "No samples at the moment",
        html_attrs = {"style":'font-size:16px; width=100%'}, 
        table_id = table_id,
        classes = ["table-striped","mb-4"]
        ) 
    column_html_attrs = {'style':'word-wrap: break-word; max-width:150px;'}

    table_class = create_table(name,options=options)
    # table_class.get_tr_attrs = dynamic_get_tr_attrs
    table_class.sort_url = dynamic_sort_url
    sort = sort_kwargs.get('sort_by','datetime_submitted')
    reverse = sort_kwargs.get('sort_reverse',False)
    """ Add the columns that you want to go first here.
    It is OK if they get duplicated in the loop below -- they
    will not be added twice """

    ''' Now only add the start_imaging_link if the table is being imaged or ready to image '''
    imaging_url_kwargs = {'username':'username','request_name':'request_name',
        'imaging_batch_number':'imaging_batch_number',
        'imaging_request_number':'imaging_request_number'}

    # anchor_attrs = {'target':"_blank",}
    anchor_attrs = {}
    if table_id == 'horizontal_ready_to_image_table':
        table_class.add_column('start_imaging_link',LinkCol('Start imaging',
         'imaging.imaging_batch_entry',url_kwargs=imaging_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False,
            column_html_attrs=column_html_attrs))
    elif table_id == 'horizontal_being_imaged_table':
        table_class.add_column('continue_imaging_link',LinkCol('Continue imaging',
         'imaging.imaging_batch_entry',url_kwargs=imaging_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False,
            column_html_attrs=column_html_attrs))
   
    table_class.add_column('datetime_submitted',DateTimeCol('datetime submitted',
        column_html_attrs=column_html_attrs))
    table_class.add_column('request_name',Col('request name',
        column_html_attrs=column_html_attrs))
    # table_class.add_column('sample_name',Col('sample name',
    #     column_html_attrs=column_html_attrs))
    table_class.add_column('username',Col('username',
        column_html_attrs=column_html_attrs))    
    # table_class.add_column('imaging_request_number',Col('imaging request number',
    #     column_html_attrs=column_html_attrs))
    # if table_id == 'horizontal_ready_to_image_table':
    table_class.add_column('imaging_request_number',Col('imaging request number',
        column_html_attrs=column_html_attrs))
    table_class.add_column('imaging_batch_number',Col('imaging batch number',
        column_html_attrs=column_html_attrs))
    table_class.add_column('number_in_imaging_batch',Col('number in batch',
        column_html_attrs=column_html_attrs))

    if table_class.table_id == 'horizontal_on_deck_table':
        table_class.add_column('clearer',DesignatedRoleCol('clearer',
            column_html_attrs=column_html_attrs))
   
    table_class.add_column('imager',DesignatedRoleCol('imager',
        column_html_attrs=column_html_attrs))
    table_class.add_column('species',Col('species',
        column_html_attrs=column_html_attrs))    

   
    if type(contents) != list:
        sorted_contents = sorted(contents.fetch(as_dict=True),
                key=partial(table_sorter,sort_key=sort),reverse=reverse)
    else:
        sorted_contents = sorted(contents,
                key=partial(table_sorter,sort_key=sort),reverse=reverse)
    table = table_class(sorted_contents)
    table.sort_by = sort
    table.sort_reverse = reverse
    
    return table 

class ImagingTable(Table):
    border = True
    no_items = "No Imaging Yet"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    # column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    column_html_attrs = {'style':'word-wrap: break-word; max-width:200px;'}

    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    request_name = Col('request name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample name',column_html_attrs=column_html_attrs)
    imager = Col('imager',column_html_attrs=column_html_attrs)
    imaging_request_number = Col('imaging request number',column_html_attrs=column_html_attrs)
    clearing_protocol = Col('clearing protocol',column_html_attrs=column_html_attrs)
    antibody1 = Col('antibody1',column_html_attrs=column_html_attrs)
    antibody2 = Col('antibody2',column_html_attrs=column_html_attrs)
    imaging_progress = ProgressCol('imaging progress',column_html_attrs=column_html_attrs)

class ImagingBatchTable(Table):
    border = True
    no_items = "No Batch Yet"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    # column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    column_html_attrs = {'style':'word-wrap: break-word; max-width:200px;'}

    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    request_name = Col('request name',column_html_attrs=column_html_attrs)
    imaging_batch_number = Col('imaging batch number',column_html_attrs=column_html_attrs)
    number_in_imaging_batch = Col('number of samples in batch',column_html_attrs=column_html_attrs)
    imager = Col('imager',column_html_attrs=column_html_attrs)

class SampleTable(Table):
    border = True
    no_items = "No Sample Yet"

    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    # column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    column_html_attrs = {'style':'word-wrap: break-word; max-width:200px;'}
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    request_name = Col('request name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample name',column_html_attrs=column_html_attrs)

class RequestSummaryTable(Table):
    border = True
    no_items = "No Sample Yet"

    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    # column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    column_html_attrs = {'style':'word-wrap: break-word; max-width:200px;'}
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    request_name = Col('request name',column_html_attrs=column_html_attrs)
    description = Col('description',column_html_attrs=column_html_attrs)
    species = Col('species',column_html_attrs=column_html_attrs)
    number_of_samples = Col('number of samples',column_html_attrs=column_html_attrs)
    url_kwargs = {'username':'username','request_name':'request_name'}
    anchor_attrs = {'target':"_blank",}
    
    samples_link = LinkCol('View request status', 'requests.request_overview',url_kwargs=url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False)


class ExistingImagingTable(Table):
    """ A table to show the existing imaging already
    requested for a request sample """ 
    border = True
    allow_sort=False
    no_items = "No imaging requested yet"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    # column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    column_html_attrs = {'style':'word-wrap: break-word; max-width:200px;'}
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.

    sample_name = Col('sample_name',column_html_attrs=column_html_attrs)
    imaging_request_number = Col('imaging request number',column_html_attrs=column_html_attrs)
    image_resolution = Col('image resolution',column_html_attrs=column_html_attrs)
    channel_name = Col('channel name',column_html_attrs=column_html_attrs)
    registration = BooltoStringCol('registration',column_html_attrs=column_html_attrs)
    injection_detection = BooltoStringCol('injection detection',column_html_attrs=column_html_attrs)
    probe_detection = BooltoStringCol('probe detection',column_html_attrs=column_html_attrs)
    cell_detection = BooltoStringCol('cell detection',column_html_attrs=column_html_attrs)

class ImagingChannelTable(Table):
    """ A table that shows the ImagingChannel() db contents """
    border = True
    no_items = "No Imaging Yet"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    # column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    column_html_attrs = {'style':'word-wrap: break-word; max-width:200px;'}
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
   
    image_resolution = Col('image resolution',column_html_attrs=column_html_attrs)
    channel_name = Col('channel name',column_html_attrs=column_html_attrs)
    image_orientation = Col('image_orientation',column_html_attrs=column_html_attrs)
    tiling_scheme = Col('tiling_scheme',column_html_attrs=column_html_attrs)
    tiling_overlap = Col('tiling_overlap',column_html_attrs=column_html_attrs)
    z_step = Col('z_step',column_html_attrs=column_html_attrs)
    number_of_z_planes = Col('number_of_z_planes',column_html_attrs=column_html_attrs)
    rawdata_subfolder = Col('rawdata_subfolder',column_html_attrs=column_html_attrs)