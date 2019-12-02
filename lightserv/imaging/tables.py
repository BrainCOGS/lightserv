from flask import request
from flask_table import create_table,Table, Col, LinkCol, ButtonCol
from functools import partial
from lightserv.main.utils import table_sorter

def dynamic_imaging_management_table(contents,table_id,ignore_columns=[],
    name='Dynamic Imaging Management Table', **sort_kwargs):
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
        no_items = "No samples at the moment",
        html_attrs = {"style":'font-size:18px'}, 
        table_id = table_id,
        classes = ["table-striped"]
        ) 

    table_class = create_table(name,options=options)
    table_class.get_tr_attrs = dynamic_get_tr_attrs
    table_class.sort_url = dynamic_sort_url
    sort = sort_kwargs.get('sort_by','datetime_submitted')
    reverse = sort_kwargs.get('sort_reverse',False)
    """ Now loop through all columns and add them to the table,
    only adding the imaging modes if they are used in at least one
    sample """
    colnames = contents.heading.attributes.keys()
    """ Add the columns that you want to go first here.
    It is OK if they get duplicated in the loop below -- they
    will not be added twice """
    table_class.add_column('datetime_submitted',Col('datetime submitted'))
    table_class.add_column('experiment_name',Col('experiment name'))
    table_class.add_column('sample_name',Col('sample name'))
    table_class.add_column('username',Col('username'))    
    table_class.add_column('imaging_request_number',Col('imaging request number'))    
    
    if table_class == 'horizontal_ready_to_image_table':
        table_class.add_column('imaging_progress',BoldTextCol('imaging_progress'))
    else: 
        table_class.add_column('clearing_progress',Col('clearing progress'))
        table_class.add_column('imaging_progress',Col('imaging progress'))
    table_class.add_column('imager',Col('imager'))
    table_class.add_column('species',Col('species'))    

    ''' Now only add the start_imaging_link if the table is being imaged or ready to image '''
    imaging_url_kwargs = {'username':'username','experiment_name':'experiment_name',
        'sample_name':'sample_name','imaging_request_number':'imaging_request_number'}

    anchor_attrs = {'target':"_blank",}
    if table_id == 'horizontal_ready_to_image_table':
        print(imaging_url_kwargs)
        table_class.add_column('start_imaging_link',LinkCol('Start imaging',
         'imaging.imaging_entry',url_kwargs=imaging_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
    elif table_id == 'horizontal_being_imaged_table':
        table_class.add_column('continue_imaging_link',LinkCol('Continue imaging',
         'imaging.imaging_entry',url_kwargs=imaging_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
         
    sorted_contents = sorted(contents.fetch(as_dict=True),
            key=partial(table_sorter,sort_key=sort),reverse=reverse)
    table = table_class(sorted_contents)
    table.sort_by = sort
    table.sort_reverse = reverse
    
    return table 


class ImagingTable(Table):
    border = True
    no_items = "No Imaging Yet"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample name',column_html_attrs=column_html_attrs)
    imager = Col('imager',column_html_attrs=column_html_attrs)
    imaging_request_number = Col('imaging request number',column_html_attrs=column_html_attrs)
    # imaging_progress = Col('imaging_progress',column_html_attrs=column_html_attrs)

class SampleTable(Table):
    border = True
    no_items = "No Sample Yet"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample name',column_html_attrs=column_html_attrs)


class ExistingImagingTable(Table):
    """ A table to show the existing imaging already
    requested for a given sample """ 
    border = True
    no_items = "No imaging requested yet"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    image_resolution = Col('image resolution',column_html_attrs=column_html_attrs)
    imaging_request_number = Col('imaging request number',column_html_attrs=column_html_attrs)
    channel_name = Col('channel name',column_html_attrs=column_html_attrs)

