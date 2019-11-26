from flask import url_for,flash,redirect, request
from flask_table import Table, Col, LinkCol, ButtonCol, create_table


class ExpTable(Table):
    border = True
    allow_sort = True
    no_items = "No Experiments Yet"
    html_attrs = {"style":'font-size:18px',} # gets assigned to table header
    table_id = 'vert_table' # override this when you make an instance if you dont want vertical layout by default
    # column_html_attrs = {'style':'text-align: center; min-width:10px', 'bgcolor':"#FF0000"} # gets assigned to both th and td
    column_html_attrs = [] # javascript tableswapper does not preserve these.
    classes = ["table-striped"] # gets assigned to table classes. 
    # Striped is alternating bright and dark rows for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment_name',column_html_attrs=column_html_attrs)
    description = Col('description',column_html_attrs=column_html_attrs)
    species = Col('species',column_html_attrs=column_html_attrs)
    number_of_samples = Col('number of samples',column_html_attrs=column_html_attrs)
    sample_prefix = Col('sample prefix')
    date_submitted = Col('date submitted')
    time_submitted = Col('time submitted')

    url_kwargs = {'username':'username','experiment_name':'experiment_name'}
    anchor_attrs = {'target':"_blank",}
    
    experiment_link = LinkCol('View experiment', 'experiments.exp',url_kwargs=url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False)
    
    def sort_url(self, col_key, reverse=False):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'
        next_url = request.url.split('?')[0]
        next_url += f'?sort={col_key}&direction={direction}&table_id={self.table_id}'
        return next_url


def create_dynamic_samples_table(contents,table_id,ignore_columns=[],name='Dynamic Samples Table', **sort_kwargs):
    def dynamic_sort_url(self, col_key, reverse=False):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'

        next_url = request.url.split('?')[0]
        next_url += f'?sort={col_key}&direction={direction}&table_id={table_id}'
        return next_url

    options = dict(
        border = True,
        allow_sort = True,
        no_items = "No Samples",
        html_attrs = {"style":'font-size:18px'}, 
        table_id = table_id,
        classes = ["table-striped"]
        ) 

    table_class = create_table(name,options=options)
    table_class.sort_url = dynamic_sort_url
    sort = sort_kwargs.get('sort_by','sample_name')
    reverse = sort_kwargs.get('sort_reverse',False)
    """ Now loop through all columns and add them to the table,
    only adding the imaging modes if they are used in at least one
    sample """
    colnames = contents.heading.attributes.keys()
    """ Add the columns that you want to go first here.
    It is OK if they get duplicated in the loop below -- they
    will not be added twice """
    table_class.add_column('sample_name',Col('sample_name'))
    table_class.add_column('experiment_name',Col('experiment_name'))
    table_class.add_column('username',Col('username'))
    for column_name in colnames:
        if column_name in ignore_columns:
            continue
        if column_name == 'clearer':
             table_class.add_column('clearing',HeadingCol('Clearing parameters',endpoint='main.welcome'))
        if column_name == 'imager':
             table_class.add_column('imaging',HeadingCol('Imaging parameters',endpoint='main.home'))
        if column_name == 'processor':
             table_class.add_column('processing',HeadingCol('Image processing parameters',endpoint='main.home'))
        if 'channel' in column_name:
            vals = contents.fetch(column_name)
            if not any(vals):
                continue
        table_class.add_column(column_name,Col(column_name),)
    """ Now add in the link columns """
    clearing_url_kwargs = {'username':'username','experiment_name':'experiment_name',
    'sample_name':'sample_name','clearing_protocol':'clearing_protocol'}
    imaging_url_kwargs = {'username':'username','experiment_name':'experiment_name',
    'sample_name':'sample_name'}
    processing_url_kwargs = {'username':'username','experiment_name':'experiment_name','sample_name':'sample_name','clearing_protocol':'clearing_protocol'}
    anchor_attrs = {'target':"_blank",}
    table_class.add_column('start_clearing_link',
        LinkCol('Start/edit clearing', 'clearing.clearing_entry',url_kwargs=clearing_url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False))
    table_class.add_column('view_clearing_link',LinkCol('View clearing log', 
        'clearing.clearing_table',url_kwargs=clearing_url_kwargs,
       anchor_attrs=anchor_attrs,allow_sort=False))
    table_class.add_column('start_imaging_link',LinkCol('Start/edit imaging',
     'imaging.imaging_entry',url_kwargs=imaging_url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False))
    table_class.add_column('data_processing_link',LinkCol('Start processing pipeline', 
        'processing.start_processing',url_kwargs=processing_url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False))
   
    sorted_contents = sorted(contents.fetch(as_dict=True),
            key=partial(table_sorter,sort_key=sort),reverse=reverse)
    table = table_class(sorted_contents)
    table.sort_by = sort
    table.sort_reverse = reverse
    
    return table 
