# import flask_table
from flask import url_for,flash,redirect, request
from flask_table import create_table,Table, Col, LinkCol, ButtonCol
from functools import partial
from lightserv.main.utils import table_sorter

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

class SamplesTable(Table):
    border = True
    allow_sort = True
    no_items = "No Samples"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    table_id = 'vert_table' # override this when you make an instance if you dont want vertical layout by default
    column_html_attrs = [] # javascript tableswapper does not preserve these.
    classes = ["table-striped"] # gets assigned to table classes. 
    # Striped is alternating bright and dark rows for visual ease.
    sample_name = Col('sample_name',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment_name',column_html_attrs=column_html_attrs)
    username = Col('username',column_html_attrs=column_html_attrs)
    clearing_progress = Col('clearing_progress',column_html_attrs)
    clearing_protocol = Col('clearing_protocol',column_html_attrs)
    clearer = Col('clearer',column_html_attrs=column_html_attrs)
    imager = Col('imager',column_html_attrs=column_html_attrs)
    imaging_progress = Col('imaging_progress',column_html_attrs)
    image_resolution = Col("image_resolution",column_html_attrs=column_html_attrs)
    channel488_registration = Col('channel488_registration',column_html_attrs=column_html_attrs)                     
    channel555_registration = Col('channel555_registration',column_html_attrs=column_html_attrs)                     
    channel647_registration = Col('channel647_registration',column_html_attrs=column_html_attrs)                     
    channel790_registration = Col('channel790_registration',column_html_attrs=column_html_attrs)                     
    channel488_injection_detection = Col('channel488_injection_detection',column_html_attrs=column_html_attrs)                     
    channel555_injection_detection = Col('channel555_injection_detection',column_html_attrs=column_html_attrs)                     
    channel647_injection_detection = Col('channel647_injection_detection',column_html_attrs=column_html_attrs)                     
    channel790_injection_detection = Col('channel790_injection_detection',column_html_attrs=column_html_attrs) 
    channel488_probe_detection = Col('channel488_probe_detection',column_html_attrs=column_html_attrs)                     
    channel555_probe_detection = Col('channel555_probe_detection',column_html_attrs=column_html_attrs)                     
    channel647_probe_detection = Col('channel647_probe_detection',column_html_attrs=column_html_attrs)                     
    channel790_probe_detection = Col('channel790_probe_detection',column_html_attrs=column_html_attrs) 
    channel488_cell_detection = Col('channel488_cell_detection',column_html_attrs=column_html_attrs)                     
    channel555_cell_detection = Col('channel555_cell_detection',column_html_attrs=column_html_attrs)                     
    channel647_cell_detection = Col('channel647_cell_detection',column_html_attrs=column_html_attrs)                     
    channel790_cell_detection = Col('channel790_cell_detection',column_html_attrs=column_html_attrs) 
    clearing_url_kwargs = {'username':'username','experiment_name':'experiment_name',
    'sample_name':'sample_name','clearing_protocol':'clearing_protocol'}
    imaging_url_kwargs = {'username':'username','experiment_name':'experiment_name',
    'sample_name':'sample_name'}
    anchor_attrs = {'target':"_blank",}
    start_clearing_link = LinkCol('Start/edit clearing', 'clearing.clearing_entry',url_kwargs=clearing_url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False)
    view_clearing_link = LinkCol('View clearing log', 'clearing.clearing_table',url_kwargs=clearing_url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False)
    start_imaging_link = LinkCol('Start/edit imaging', 'imaging.imaging_entry',url_kwargs=imaging_url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False)
   
    def sort_url(self, col_key, reverse=False,):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'

        next_url = request.url.split('?')[0]
        next_url += f'?sort={col_key}&direction={direction}&table_id={self.table_id}'
        return next_url

def create_dynamic_samples_table(contents,table_id,name='Dynamic Samples Table', **sort_kwargs):
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
    colnames = contents.fetch(as_dict=True)[0].keys()
    """ Add the columns that you want to go first here.
    It is OK if they get duplicated in the loop below -- they
    will not be added twice """
    table_class.add_column('sample_name',Col('sample_name'))
    table_class.add_column('experiment_name',Col('experiment_name'))
    table_class.add_column('username',Col('username'))
    for column_name in colnames:
        if 'channel' in column_name:
            vals = contents.fetch(column_name)
            if not any(vals):
                continue
        table_class.add_column(column_name,Col(column_name))
    """ Now add in the link columns """
    clearing_url_kwargs = {'username':'username','experiment_name':'experiment_name',
    'sample_name':'sample_name','clearing_protocol':'clearing_protocol'}
    imaging_url_kwargs = {'username':'username','experiment_name':'experiment_name',
    'sample_name':'sample_name'}
    anchor_attrs = {'target':"_blank",}
    table_class.add_column('start_clearing_link',
        LinkCol('Start/edit clearing', 'clearing.clearing_entry',url_kwargs=clearing_url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False))
    table_class.add_column('view_clearing_link',LinkCol('View clearing log', 'clearing.clearing_table',url_kwargs=clearing_url_kwargs,
       anchor_attrs=anchor_attrs,allow_sort=False))
    table_class.add_column('start_imaging_link',LinkCol('Start/edit imaging', 'imaging.imaging_entry',url_kwargs=imaging_url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False))
   
    sorted_contents = sorted(contents.fetch(as_dict=True),
            key=partial(table_sorter,sort_key=sort),reverse=reverse)
    table = table_class(sorted_contents)
    table.sort_by = sort
    table.sort_reverse = reverse
    
    return table 

class MicroscopeCalibrationTable(Table):
    ''' Define the microscope objective swap 
    entry log table. Cannot be sorted by date because 
    we allow NULL entries for date. '''
    border = True
    allow_sort = True
    no_items = "No Logs Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped","mb-4"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    entrynum = Col('entrynum',column_html_attrs=column_html_attrs)
    date = Col('date',column_html_attrs=column_html_attrs)
    username = Col('username',column_html_attrs=column_html_attrs)
    old_objective = Col('old_objective',column_html_attrs=column_html_attrs)
    new_objective = Col('new_objective',column_html_attrs=column_html_attrs)
    swapper = Col('swapper',column_html_attrs=column_html_attrs)
    calibration = Col('calibration',column_html_attrs=column_html_attrs)
    notes = Col('notes',column_html_attrs=column_html_attrs)
    kwargs = {'entrynum':'entrynum',}
    anchor_attrs = {'target':"_blank",}

    delete_link = LinkCol('Update entry', 'microscope.update_entry',url_kwargs=kwargs,anchor_attrs=anchor_attrs,allow_sort=False)

    def sort_url(self, col_key, reverse=False):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'
        return url_for('microscope.swap_calibrate_log', sort=col_key, direction=direction)

class ClearingTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment_name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample_name',column_html_attrs=column_html_attrs)
    clearing_protocol = Col('clearing_protocol',column_html_attrs=column_html_attrs)
    clearer = Col('clearer',column_html_attrs=column_html_attrs)
    clearing_progress = Col('clearing_progress',column_html_attrs=column_html_attrs)

class ImagingTable(Table):
    border = True
    no_items = "No Imaging Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment_name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample_name',column_html_attrs=column_html_attrs)
    image_resolution = Col('image_resolution',column_html_attrs=column_html_attrs)
    imager = Col('imager',column_html_attrs=column_html_attrs)
    imaging_progress = Col('imaging_progress',column_html_attrs=column_html_attrs)

class IdiscoPlusTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment_name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample_name',column_html_attrs=column_html_attrs)
    exp_notes = Col('exp_notes')

    time_dehydr_pbs_wash1 = Col('time_dehydr_pbs_wash1',)
    dehydr_pbs_wash1_notes = Col('dehydr_pbs_wash1_notes',)
    
    time_dehydr_pbs_wash2 = Col('time_dehydr_pbs_wash2',)
    dehydr_pbs_wash2_notes = Col('dehydr_pbs_wash2_notes',)
    
    time_dehydr_pbs_wash3 = Col('time_dehydr_pbs_wash3',)
    dehydr_pbs_wash3_notes = Col('dehydr_pbs_wash3_notes',)
    
    time_dehydr_methanol_20percent_wash1           = Col('time_dehydr_methanol_20percent_wash1',)
    dehydr_methanol_20percent_wash1_notes           = Col('dehydr_methanol_20percent_wash1_notes',)
    
    time_dehydr_methanol_40percent_wash1           = Col('time_dehydr_methanol_40percent_wash1',)
    dehydr_methanol_40percent_wash1_notes           = Col('dehydr_methanol_40percent_wash1_notes',)
    
    time_dehydr_methanol_60percent_wash1           = Col('time_dehydr_methanol_60percent_wash1',)
    dehydr_methanol_60percent_wash1_notes           = Col('dehydr_methanol_60percent_wash1_notes',)
    
    time_dehydr_methanol_80percent_wash1           = Col('time_dehydr_methanol_80percent_wash1',)
    dehydr_methanol_80percent_wash1_notes           = Col('dehydr_methanol_80percent_wash1_notes',)
    
    time_dehydr_methanol_100percent_wash1          = Col('time_dehydr_methanol_100percent_wash1',)
    dehydr_methanol_100percent_wash1_notes          = Col('dehydr_methanol_100percent_wash1_notes',)
    
    time_dehydr_methanol_100percent_wash2          = Col('time_dehydr_methanol_100percent_wash2',)
    dehydr_methanol_100percent_wash2_notes          = Col('dehydr_methanol_100percent_wash2_notes',)
    
    time_dehydr_h202_wash1                      = Col('time_dehydr_h202_wash1',)
    dehydr_h202_wash1_notes                      = Col('dehydr_h202_wash1_notes',)
    
    time_rehydr_methanol_100percent_wash1          = Col('time_rehydr_methanol_100percent_wash1',)
    rehydr_methanol_100percent_wash1_notes          = Col('rehydr_methanol_100percent_wash1_notes',)
    
    time_rehydr_methanol_80percent_wash1           = Col('time_rehydr_methanol_80percent_wash1',)
    rehydr_methanol_80percent_wash1_notes           = Col('rehydr_methanol_80percent_wash1_notes',)
    
    time_rehydr_methanol_60percent_wash1           = Col('time_rehydr_methanol_60percent_wash1',)
    rehydr_methanol_60percent_wash1_notes           = Col('rehydr_methanol_60percent_wash1_notes',)
    
    time_rehydr_methanol_40percent_wash1           = Col('time_rehydr_methanol_40percent_wash1',)
    rehydr_methanol_40percent_wash1_notes           = Col('rehydr_methanol_40percent_wash1_notes',)
    
    time_rehydr_methanol_20percent_wash1           = Col('time_rehydr_methanol_20percent_wash1',)
    rehydr_methanol_20percent_wash1_notes           = Col('rehydr_methanol_20percent_wash1_notes',)
    
    time_rehydr_pbs_wash1                       = Col('time_rehydr_pbs_wash1',)
    rehydr_pbs_wash1_notes                       = Col('rehydr_pbs_wash1_notes',)
    
    time_rehydr_sodium_azide_wash1              = Col('time_rehydr_sodium_azide_wash1',)
    rehydr_sodium_azide_wash1_notes              = Col('rehydr_sodium_azide_wash1_notes',)
    
    time_rehydr_sodium_azide_wash2              = Col('time_rehydr_sodium_azide_wash2',)
    rehydr_sodium_azide_wash2_notes              = Col('rehydr_sodium_azide_wash2_notes',)
    
    time_rehydr_glycine_wash1                   = Col('time_rehydr_glycine_wash1',)
    rehydr_glycine_wash1_notes                   = Col('rehydr_glycine_wash1_notes',)
    
    time_blocking_start_roomtemp                = Col('time_blocking_start_roomtemp')
    blocking_start_roomtemp_notes                = Col('blocking_start_roomtemp_notes')
    
    time_blocking_donkey_serum                  = Col('time_blocking_donkey_serum')
    blocking_donkey_serum_notes                  = Col('blocking_donkey_serum_notes')
    
    time_antibody1_start_roomtemp               = Col('time_antibody1_start_roomtemp')
    antibody1_start_roomtemp_notes               = Col('antibody1_start_roomtemp_notes')
    
    time_antibody1_ptwh_wash1                   = Col('time_antibody1_ptwh_wash1')
    antibody1_ptwh_wash1_notes                   = Col('antibody1_ptwh_wash1_notes')
    
    time_antibody1_ptwh_wash2                   = Col('time_antibody1_ptwh_wash2')
    antibody1_ptwh_wash2_notes                   = Col('antibody1_ptwh_wash2_notes')
    
    time_antibody1_added                        = Col('time_antibody1_added')
    antibody1_added_notes                        = Col('antibody1_added_notes')
    
    time_wash1_start_roomtemp                   = Col('time_wash1_start_roomtemp')
    wash1_start_roomtemp_notes                   = Col('wash1_start_roomtemp_notes')
    
    time_wash1_ptwh_wash1                       = Col('time_wash1_ptwh_wash1')
    wash1_ptwh_wash1_notes                       = Col('wash1_ptwh_wash1_notes')
    
    time_wash1_ptwh_wash2                       = Col('time_wash1_ptwh_wash2')
    wash1_ptwh_wash2_notes                       = Col('wash1_ptwh_wash2_notes')
    
    time_wash1_ptwh_wash3                       = Col('time_wash1_ptwh_wash3')
    wash1_ptwh_wash3_notes                       = Col('wash1_ptwh_wash3_notes')
    
    time_wash1_ptwh_wash4                       = Col('time_wash1_ptwh_wash4')
    wash1_ptwh_wash4_notes                       = Col('wash1_ptwh_wash4_notes')
    
    time_wash1_ptwh_wash5                       = Col('time_wash1_ptwh_wash5')
    wash1_ptwh_wash5_notes                       = Col('wash1_ptwh_wash5_notes')
    
    time_antibody2_added                        = Col('time_antibody2_added')
    antibody2_added_notes                        = Col('antibody2_added_notes')
    
    time_wash2_start_roomtemp                   = Col('time_wash2_start_roomtemp')
    wash2_start_roomtemp_notes                   = Col('wash2_start_roomtemp_notes')
    
    time_wash2_ptwh_wash1                       = Col('time_wash2_ptwh_wash1')
    wash2_ptwh_wash1_notes                       = Col('wash2_ptwh_wash1_notes')
    
    time_wash2_ptwh_wash2                       = Col('time_wash2_ptwh_wash2')
    wash2_ptwh_wash2_notes                       = Col('wash2_ptwh_wash2_notes')
    
    time_wash2_ptwh_wash3                       = Col('time_wash2_ptwh_wash3')
    wash2_ptwh_wash3_notes                       = Col('wash2_ptwh_wash3_notes')
    
    time_wash2_ptwh_wash4                       = Col('time_wash2_ptwh_wash4')
    wash2_ptwh_wash4_notes                       = Col('wash2_ptwh_wash4_notes')
    
    time_wash2_ptwh_wash5                       = Col('time_wash2_ptwh_wash5')
    wash2_ptwh_wash5_notes                       = Col('wash2_ptwh_wash5_notes')
    
    time_clearing_methanol_20percent_wash1         = Col('time_clearing_methanol_20percent_wash1')
    clearing_methanol_20percent_wash1_notes         = Col('clearing_methanol_20percent_wash1_notes')
    
    time_clearing_methanol_40percent_wash1         = Col('time_clearing_methanol_40percent_wash1')
    clearing_methanol_40percent_wash1_notes         = Col('clearing_methanol_40percent_wash1_notes')
    
    time_clearing_methanol_60percent_wash1         = Col('time_clearing_methanol_60percent_wash1')
    clearing_methanol_60percent_wash1_notes         = Col('clearing_methanol_60percent_wash1_notes')
    
    time_clearing_methanol_80percent_wash1         = Col('time_clearing_methanol_80percent_wash1')
    clearing_methanol_80percent_wash1_notes         = Col('clearing_methanol_80percent_wash1_notes')
    
    time_clearing_methanol_100percent_wash1        = Col('time_clearing_methanol_100percent_wash1')
    clearing_methanol_100percent_wash1_notes        = Col('clearing_methanol_100percent_wash1_notes')
    
    time_clearing_methanol_100percent_wash2        = Col('time_clearing_methanol_100percent_wash2')
    clearing_methanol_100percent_wash2_notes        = Col('clearing_methanol_100percent_wash2_notes')
    
    time_clearing_dcm_66percent_methanol_33percent = Col('time_clearing_dcm_66percent_methanol_33percent')
    clearing_dcm_66percent_methanol_33percent_notes = Col('clearing_dcm_66percent_methanol_33percent_notes')
    
    time_clearing_dcm_wash1                     = Col('time_clearing_dcm_wash1')
    clearing_dcm_wash1_notes                     = Col('clearing_dcm_wash1_notes')
    
    time_clearing_dcm_wash2                     = Col('time_clearing_dcm_wash2')
    clearing_dcm_wash2_notes                     = Col('clearing_dcm_wash2_notes')
    
    time_clearing_dbe                           = Col('time_clearing_dbe')
    clearing_dbe_notes                           = Col('clearing_dbe_notes')
    
    time_clearing_new_tubes                     = Col('time_clearing_new_tubes')
    clearing_new_tubes_notes                     = Col('clearing_new_tubes_notes')
    
    clearing_notes                              = Col('clearing_notes')
   
class IdiscoAbbreviatedTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment_name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample_name',column_html_attrs=column_html_attrs)
    exp_notes = Col('exp_notes')
    time_pbs_wash1 = Col('time_pbs_wash1',)
    pbs_wash1_notes = Col('pbs_wash1_notes',)
    time_pbs_wash2 = Col('time_pbs_wash2',)
    pbs_wash2_notes = Col('pbs_wash2_notes',)
    time_pbs_wash3 = Col('time_pbs_wash3',)
    pbs_wash3_notes = Col('pbs_wash3_notes',)
    
    time_dehydr_methanol_20percent_wash1           = Col('time_dehydr_methanol_20percent_wash1',)
    dehydr_methanol_20percent_wash1_notes          = Col('dehydr_methanol_20percent_wash1_notes',)
    
    time_dehydr_methanol_40percent_wash1           = Col('time_dehydr_methanol_40percent_wash1',)
    dehydr_methanol_40percent_wash1_notes          = Col('dehydr_methanol_40percent_wash1_notes',)
    
    time_dehydr_methanol_60percent_wash1           = Col('time_dehydr_methanol_60percent_wash1',)
    dehydr_methanol_60percent_wash1_notes          = Col('dehydr_methanol_60percent_wash1_notes',)
    
    time_dehydr_methanol_80percent_wash1           = Col('time_dehydr_methanol_80percent_wash1',)
    dehydr_methanol_80percent_wash1_notes          = Col('dehydr_methanol_80percent_wash1_notes',)
    
    time_dehydr_methanol_100percent_wash1          = Col('time_dehydr_methanol_100percent_wash1',)
    dehydr_methanol_100percent_wash1_notes         = Col('dehydr_methanol_100percent_wash1_notes',)
    
    time_dehydr_methanol_100percent_wash2          = Col('time_dehydr_methanol_100percent_wash2',)
    dehydr_methanol_100percent_wash2_notes         = Col('dehydr_methanol_100percent_wash2_notes',)
    
    time_dehydr_dcm_66percent_methanol_33percent   = Col('time_dehydr_dcm_66percent_methanol_33percent',)
    dehydr_dcm_66percent_methanol_33percent_notes  = Col('dehydr_dcm_66percent_methanol_33percent_notes',)
    
    time_dehydr_dcm_wash1   = Col('time_dehydr_dcm_wash1')
    dehydr_dcm_wash1_notes  = Col('dehydr_dcm_wash1_notes')
    
    time_dehydr_dcm_wash2   = Col('time_dehydr_dcm_wash2')
    dehydr_dcm_wash2_notes  = Col('dehydr_dcm_wash2_notes')
    
    time_dehydr_dbe_wash1   = Col('time_dehydr_dbe_wash1')
    dehydr_dbe_wash1_notes  = Col('dehydr_dbe_wash1_notes')
    
    time_dehydr_dbe_wash2   = Col('time_dehydr_dbe_wash2')
    dehydr_dbe_wash2_notes  = Col('dehydr_dbe_wash2_notes')
    clearing_notes          = Col('clearing_notes')

class IdiscoAbbreviatedRatTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment_name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample_name',column_html_attrs=column_html_attrs)
    exp_notes = Col('exp_notes')

    time_pbs_wash1 = Col('time_pbs_wash1',)
    pbs_wash1_notes = Col('pbs_wash1_notes',)
    
    time_pbs_wash2 = Col('time_pbs_wash2',)
    pbs_wash2_notes = Col('pbs_wash2_notes',)
    
    time_pbs_wash3 = Col('time_pbs_wash3',)
    pbs_wash3_notes = Col('pbs_wash3_notes',)
    
    time_dehydr_methanol_20percent_wash1           = Col('time_dehydr_methanol_20percent_wash1',)
    dehydr_methanol_20percent_wash1_notes           = Col('dehydr_methanol_20percent_wash1_notes',)
    
    time_dehydr_methanol_20percent_wash2           = Col('time_dehydr_methanol_20percent_wash2',)
    dehydr_methanol_20percent_wash2_notes           = Col('dehydr_methanol_20percent_wash2_notes',)
    
    time_dehydr_methanol_40percent_wash1           = Col('time_dehydr_methanol_40percent_wash1',)
    dehydr_methanol_40percent_wash1_notes           = Col('dehydr_methanol_40percent_wash1_notes',)
    
    time_dehydr_methanol_40percent_wash2           = Col('time_dehydr_methanol_40percent_wash2',)
    dehydr_methanol_40percent_wash2_notes           = Col('dehydr_methanol_40percent_wash2_notes',)
    
    time_dehydr_methanol_60percent_wash1           = Col('time_dehydr_methanol_60percent_wash1',)
    dehydr_methanol_60percent_wash1_notes           = Col('dehydr_methanol_60percent_wash1_notes',)
    
    time_dehydr_methanol_80percent_wash1           = Col('time_dehydr_methanol_80percent_wash1',)
    dehydr_methanol_80percent_wash1_notes           = Col('dehydr_methanol_80percent_wash1_notes',)
    
    time_dehydr_methanol_80percent_wash2           = Col('time_dehydr_methanol_80percent_wash2',)
    dehydr_methanol_80percent_wash2_notes           = Col('dehydr_methanol_80percent_wash2_notes',)
    
    time_dehydr_methanol_100percent_wash1          = Col('time_dehydr_methanol_100percent_wash1',)
    dehydr_methanol_100percent_wash1_notes          = Col('dehydr_methanol_100percent_wash1_notes',)
    
    time_dehydr_methanol_100percent_wash2          = Col('time_dehydr_methanol_100percent_wash2',)
    dehydr_methanol_100percent_wash2_notes          = Col('dehydr_methanol_100percent_wash2_notes',)

    time_dehydr_h202_wash1 = Col('time_dehydr_h202_wash1')
    dehydr_h202_wash1_notes = Col('dehydr_h202_wash1_notes')
    
    time_dehydr_methanol_100percent_wash3 = Col('time_dehydr_methanol_100percent_wash3')
    dehydr_methanol_100percent_wash3_notes = Col('dehydr_methanol_100percent_wash3_notes')
    
    time_dehydr_methanol_100percent_wash4 = Col('time_dehydr_methanol_100percent_wash4')
    dehydr_methanol_100percent_wash4_notes = Col('dehydr_methanol_100percent_wash4_notes')
    
    time_dehydr_methanol_100percent_wash5 = Col('time_dehydr_methanol_100percent_wash5')
    dehydr_methanol_100percent_wash5_notes = Col('dehydr_methanol_100percent_wash5_notes')

    time_dehydr_dcm_66percent_methanol_33percent = Col('time_dehydr_dcm_66percent_methanol_33percent')
    dehydr_dcm_66percent_methanol_33percent_notes = Col('dehydr_dcm_66percent_methanol_33percent_notes')
    
    time_dehydr_dcm_wash1 = Col('time_dehydr_dcm_wash1')
    dehydr_dcm_wash1_notes = Col('dehydr_dcm_wash1_notes')
    
    time_dehydr_dcm_wash2 = Col('time_dehydr_dcm_wash2')
    dehydr_dcm_wash2_notes = Col('dehydr_dcm_wash2_notes')
    
    time_dehydr_dbe_wash1 = Col('time_dehydr_dbe_wash1')
    dehydr_dbe_wash1_notes = Col('dehydr_dbe_wash1_notes')
    
    time_dehydr_dbe_wash2 = Col('time_dehydr_dbe_wash2')
    dehydr_dbe_wash2_notes = Col('dehydr_dbe_wash2_notes')
    
    clearing_notes                              = Col('clearing_notes')

class UdiscoTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment_name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample_name',column_html_attrs=column_html_attrs)
    exp_notes = Col('exp_notes')

    time_dehydr_pbs_wash1 = Col('time_dehydr_pbs_wash1')
    dehydr_pbs_wash1_notes = Col('dehydr_pbs_wash1_notes')
    
    time_dehydr_butanol_30percent = Col('time_dehydr_butanol_30percent')
    dehydr_butanol_30percent_notes = Col('dehydr_butanol_30percent_notes')
    
    time_dehydr_butanol_50percent = Col('time_dehydr_butanol_50percent')
    dehydr_butanol_50percent_notes = Col('dehydr_butanol_50percent_notes')
    
    time_dehydr_butanol_70percent = Col('time_dehydr_butanol_70percent')
    dehydr_butanol_70percent_notes = Col('dehydr_butanol_70percent_notes')
    
    time_dehydr_butanol_80percent = Col('time_dehydr_butanol_80percent')
    dehydr_butanol_80percent_notes = Col('dehydr_butanol_80percent_notes')
    
    time_dehydr_butanol_90percent = Col('time_dehydr_butanol_90percent')
    dehydr_butanol_90percent_notes = Col('dehydr_butanol_90percent_notes')
    
    time_dehydr_butanol_96percent = Col('time_dehydr_butanol_96percent')
    dehydr_butanol_96percent_notes = Col('dehydr_butanol_96percent_notes')
    
    time_dehydr_butanol_100percent = Col('time_dehydr_butanol_100percent')
    dehydr_butanol_100percent_notes = Col('dehydr_butanol_100percent_notes')
    
    time_clearing_dcm_wash1 = Col('time_clearing_dcm_wash1')
    clearing_dcm_wash1_notes = Col('clearing_dcm_wash1_notes')
    
    time_clearing_babb_wash1 = Col('time_clearing_babb_wash1')
    clearing_babb_wash1_notes = Col('clearing_babb_wash1_notes')
    clearing_notes = Col('clearing_notes')

class IdiscoEdUTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment_name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample_name',column_html_attrs=column_html_attrs)
    exp_notes = Col('exp_notes')

    time_dehydr_pbs_wash1 = Col('time_dehydr_pbs_wash1',)
    dehydr_pbs_wash1_notes = Col('dehydr_pbs_wash1_notes',)

    time_dehydr_pbs_wash2 = Col('time_dehydr_pbs_wash2',)
    dehydr_pbs_wash2_notes = Col('dehydr_pbs_wash2_notes',)

    time_dehydr_pbs_wash3 = Col('time_dehydr_pbs_wash3',)
    dehydr_pbs_wash3_notes = Col('dehydr_pbs_wash3_notes',)

    time_dehydr_methanol_20percent_wash1           = Col('time_dehydr_methanol_20percent_wash1',)
    dehydr_methanol_20percent_wash1_notes           = Col('dehydr_methanol_20percent_wash1_notes',)

    time_dehydr_methanol_40percent_wash1           = Col('time_dehydr_methanol_40percent_wash1',)
    dehydr_methanol_40percent_wash1_notes           = Col('dehydr_methanol_40percent_wash1_notes',)

    time_dehydr_methanol_60percent_wash1           = Col('time_dehydr_methanol_60percent_wash1',)
    dehydr_methanol_60percent_wash1_notes           = Col('dehydr_methanol_60percent_wash1_notes',)

    time_dehydr_methanol_80percent_wash1           = Col('time_dehydr_methanol_80percent_wash1',)
    dehydr_methanol_80percent_wash1_notes           = Col('dehydr_methanol_80percent_wash1_notes',)

    time_dehydr_methanol_100percent_wash1          = Col('time_dehydr_methanol_100percent_wash1',)
    dehydr_methanol_100percent_wash1_notes          = Col('dehydr_methanol_100percent_wash1_notes',)

    time_dehydr_methanol_100percent_wash2          = Col('time_dehydr_methanol_100percent_wash2',)
    dehydr_methanol_100percent_wash2_notes          = Col('dehydr_methanol_100percent_wash2_notes',)

    time_dehydr_h202_wash1                      = Col('time_dehydr_h202_wash1',)
    dehydr_h202_wash1_notes                      = Col('dehydr_h202_wash1_notes',)

    time_rehydr_methanol_100percent_wash1          = Col('time_rehydr_methanol_100percent_wash1',)
    rehydr_methanol_100percent_wash1_notes          = Col('rehydr_methanol_100percent_wash1_notes',)

    time_rehydr_methanol_80percent_wash1           = Col('time_rehydr_methanol_80percent_wash1',)
    rehydr_methanol_80percent_wash1_notes           = Col('rehydr_methanol_80percent_wash1_notes',)

    time_rehydr_methanol_60percent_wash1           = Col('time_rehydr_methanol_60percent_wash1',)
    rehydr_methanol_60percent_wash1_notes           = Col('rehydr_methanol_60percent_wash1_notes',)

    time_rehydr_methanol_40percent_wash1           = Col('time_rehydr_methanol_40percent_wash1',)
    rehydr_methanol_40percent_wash1_notes           = Col('rehydr_methanol_40percent_wash1_notes',)

    time_rehydr_methanol_20percent_wash1           = Col('time_rehydr_methanol_20percent_wash1',)
    rehydr_methanol_20percent_wash1_notes           = Col('rehydr_methanol_20percent_wash1_notes',)

    time_rehydr_pbs_wash1                       = Col('time_rehydr_pbs_wash1',)
    rehydr_pbs_wash1_notes                       = Col('rehydr_pbs_wash1_notes',)

    time_rehydr_sodium_azide_wash1              = Col('time_rehydr_sodium_azide_wash1',)
    rehydr_sodium_azide_wash1_notes              = Col('rehydr_sodium_azide_wash1_notes',)

    time_rehydr_sodium_azide_wash2              = Col('time_rehydr_sodium_azide_wash2',)
    rehydr_sodium_azide_wash2_notes              = Col('rehydr_sodium_azide_wash2_notes',)

    time_rehydr_glycine_wash1                   = Col('time_rehydr_glycine_wash1',)
    rehydr_glycine_wash1_notes                   = Col('rehydr_glycine_wash1_notes',)

    time_wash1_start_roomtemp                   = Col('time_wash1_start_roomtemp')
    wash1_start_roomtemp_notes                   = Col('wash1_start_roomtemp_notes')

    time_wash1_ptwh_wash1                       = Col('time_wash1_ptwh_wash1')
    wash1_ptwh_wash1_notes                       = Col('wash1_ptwh_wash1_notes')

    time_wash1_ptwh_wash2                       = Col('time_wash1_ptwh_wash2')
    wash1_ptwh_wash2_notes                       = Col('wash1_ptwh_wash2_notes')

    time_wash1_ptwh_wash3                       = Col('time_wash1_ptwh_wash3')
    wash1_ptwh_wash3_notes                       = Col('wash1_ptwh_wash3_notes')

    time_wash1_ptwh_wash4                       = Col('time_wash1_ptwh_wash4')
    wash1_ptwh_wash4_notes                       = Col('wash1_ptwh_wash4_notes')

    time_wash1_ptwh_wash5                       = Col('time_wash1_ptwh_wash5')
    wash1_ptwh_wash5_notes                       = Col('wash1_ptwh_wash5_notes')

    time_edu_click_chemistry                    = Col('time_edu_click_chemistry')
    edu_click_chemistry_notes                    = Col('edu_click_chemistry_notes')

    time_wash2_ptwh_wash1                       = Col('time_wash2_ptwh_wash1')
    wash2_ptwh_wash1_notes                       = Col('wash2_ptwh_wash1_notes')

    time_wash2_ptwh_wash2                       = Col('time_wash2_ptwh_wash2')
    wash2_ptwh_wash2_notes                       = Col('wash2_ptwh_wash2_notes')

    time_wash2_ptwh_wash3                       = Col('time_wash2_ptwh_wash3')
    wash2_ptwh_wash3_notes                       = Col('wash2_ptwh_wash3_notes')

    time_wash2_ptwh_wash4                       = Col('time_wash2_ptwh_wash4')
    wash2_ptwh_wash4_notes                       = Col('wash2_ptwh_wash4_notes')

    time_wash2_ptwh_wash5                       = Col('time_wash2_ptwh_wash5')
    wash2_ptwh_wash5_notes                       = Col('wash2_ptwh_wash5_notes')

    time_clearing_methanol_20percent_wash1         = Col('time_clearing_methanol_20percent_wash1')
    clearing_methanol_20percent_wash1_notes         = Col('clearing_methanol_20percent_wash1_notes')

    time_clearing_methanol_40percent_wash1         = Col('time_clearing_methanol_40percent_wash1')
    clearing_methanol_40percent_wash1_notes         = Col('clearing_methanol_40percent_wash1_notes')

    time_clearing_methanol_60percent_wash1         = Col('time_clearing_methanol_60percent_wash1')
    clearing_methanol_60percent_wash1_notes         = Col('clearing_methanol_60percent_wash1_notes')

    time_clearing_methanol_80percent_wash1         = Col('time_clearing_methanol_80percent_wash1')
    clearing_methanol_80percent_wash1_notes         = Col('clearing_methanol_80percent_wash1_notes')

    time_clearing_methanol_100percent_wash1        = Col('time_clearing_methanol_100percent_wash1')
    clearing_methanol_100percent_wash1_notes        = Col('clearing_methanol_100percent_wash1_notes')

    time_clearing_methanol_100percent_wash2        = Col('time_clearing_methanol_100percent_wash2')
    clearing_methanol_100percent_wash2_notes        = Col('clearing_methanol_100percent_wash2_notes')

    time_clearing_dcm_66percent_methanol_33percent = Col('time_clearing_dcm_66percent_methanol_33percent')
    clearing_dcm_66percent_methanol_33percent_notes = Col('clearing_dcm_66percent_methanol_33percent_notes')

    time_clearing_dcm_wash1                     = Col('time_clearing_dcm_wash1')
    clearing_dcm_wash1_notes                     = Col('clearing_dcm_wash1_notes')

    time_clearing_dcm_wash2                     = Col('time_clearing_dcm_wash2')
    clearing_dcm_wash2_notes                     = Col('clearing_dcm_wash2_notes')

    time_clearing_dbe                           = Col('time_clearing_dbe')
    clearing_dbe_notes                           = Col('clearing_dbe_notes')

    time_clearing_new_tubes                     = Col('time_clearing_new_tubes')
    clearing_new_tubes_notes                     = Col('clearing_new_tubes_notes')

    clearing_notes                              = Col('clearing_notes')