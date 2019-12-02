from flask_table import Table, Col, LinkCol, ButtonCol, create_table



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
    """ Now loop through all columns and add them to the table,
    only adding the imaging modes if they are used in at least one
    sample """
    sample_colnames = contents.heading.attributes.keys()
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
