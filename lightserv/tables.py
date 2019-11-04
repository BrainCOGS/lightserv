# import flask_table
from flask import url_for,flash,redirect
from flask_table import Table, Col, LinkCol

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
        if col_key == 'experiment_link':
            return url_for('main.home')
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'
        return url_for('main.home', sort=col_key, direction=direction)

class SamplesTable(Table):
    border = True
    allow_sort = True
    no_items = "No Samples"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    table_id = 'vert_table' # override this when you make an instance if you dont want vertical layout by default
    column_html_attrs = [] # javascript tableswapper does not preserve these.
    classes = ["table-striped"] # gets assigned to table classes. 
    # Striped is alternating bright and dark rows for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_name = Col('experiment_name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample_name',column_html_attrs=column_html_attrs)
    clearer = Col('clearer',column_html_attrs=column_html_attrs)
    imager = Col('imager',column_html_attrs=column_html_attrs)
    image_resolution = Col("image image_resolution",column_html_attrs=column_html_attrs)
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

    url_kwargs = {'username':'username','experiment_name':'experiment_name'}
    anchor_attrs = {'target':"_blank",}
    
    experiment_link = LinkCol('View experiment', 'experiments.exp',url_kwargs=url_kwargs,
        anchor_attrs=anchor_attrs,allow_sort=False)
    
    def sort_url(self, col_key, reverse=False):
        if col_key == 'experiment_link':
            return url_for('main.home')
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'
        return url_for('main.home', sort=col_key, direction=direction)

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
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    title = Col('title',column_html_attrs=column_html_attrs,)
    description = Col('description',column_html_attrs=column_html_attrs)
    clearing_protocol = Col('clearing_protocol',column_html_attrs=column_html_attrs)
    clearing_progress = Col('clearing_progress',column_html_attrs=column_html_attrs)

class IdiscoPlusTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    time_dehydr_pbs_wash1 = Col('time_dehydr_pbs_wash1',)
    time_dehydr_pbs_wash2 = Col('time_dehydr_pbs_wash2',)
    time_dehydr_pbs_wash3 = Col('time_dehydr_pbs_wash3',)
    time_dehydr_methanol_20percent_wash1           = Col('time_dehydr_methanol_20percent_wash1',)
    time_dehydr_methanol_40percent_wash1           = Col('time_dehydr_methanol_40percent_wash1',)
    time_dehydr_methanol_60percent_wash1           = Col('time_dehydr_methanol_60percent_wash1',)
    time_dehydr_methanol_80percent_wash1           = Col('time_dehydr_methanol_80percent_wash1',)
    time_dehydr_methanol_100percent_wash1          = Col('time_dehydr_methanol_100percent_wash1',)
    time_dehydr_methanol_100percent_wash2          = Col('time_dehydr_methanol_100percent_wash2',)
    time_dehydr_h202_wash1                      = Col('time_dehydr_h202_wash1',)
    time_rehydr_methanol_100percent_wash1          = Col('time_rehydr_methanol_100percent_wash1',)
    time_rehydr_methanol_80percent_wash1           = Col('time_rehydr_methanol_80percent_wash1',)
    time_rehydr_methanol_60percent_wash1           = Col('time_rehydr_methanol_60percent_wash1',)
    time_rehydr_methanol_40percent_wash1           = Col('time_rehydr_methanol_40percent_wash1',)
    time_rehydr_methanol_20percent_wash1           = Col('time_rehydr_methanol_20percent_wash1',)
    time_rehydr_pbs_wash1                       = Col('time_rehydr_pbs_wash1',)
    time_rehydr_sodium_azide_wash1              = Col('time_rehydr_sodium_azide_wash1',)
    time_rehydr_sodium_azide_wash2              = Col('time_rehydr_sodium_azide_wash2',)
    time_rehydr_glycine_wash1                   = Col('time_rehydr_glycine_wash1',)
    time_blocking_start_roomtemp                = Col('time_blocking_start_roomtemp')
    time_blocking_donkey_serum                  = Col('time_blocking_donkey_serum')
    time_antibody1_start_roomtemp               = Col('time_antibody1_start_roomtemp')
    time_antibody1_ptwh_wash1                   = Col('time_antibody1_ptwh_wash1')
    time_antibody1_ptwh_wash2                   = Col('time_antibody1_ptwh_wash2')
    time_antibody1_added                        = Col('time_antibody1_added')
    time_wash1_start_roomtemp                   = Col('time_wash1_start_roomtemp')
    time_wash1_ptwh_wash1                       = Col('time_wash1_ptwh_wash1')
    time_wash1_ptwh_wash2                       = Col('time_wash1_ptwh_wash2')
    time_wash1_ptwh_wash3                       = Col('time_wash1_ptwh_wash3')
    time_wash1_ptwh_wash4                       = Col('time_wash1_ptwh_wash4')
    time_wash1_ptwh_wash5                       = Col('time_wash1_ptwh_wash5')
    time_antibody2_added                        = Col('time_antibody2_added')
    time_wash2_start_roomtemp                   = Col('time_wash2_start_roomtemp')
    time_wash2_ptwh_wash1                       = Col('time_wash2_ptwh_wash1')
    time_wash2_ptwh_wash2                       = Col('time_wash2_ptwh_wash2')
    time_wash2_ptwh_wash3                       = Col('time_wash2_ptwh_wash3')
    time_wash2_ptwh_wash4                       = Col('time_wash2_ptwh_wash4')
    time_wash2_ptwh_wash5                       = Col('time_wash2_ptwh_wash5')
    time_clearing_methanol_20percent_wash1         = Col('time_clearing_methanol_20percent_wash1')
    time_clearing_methanol_40percent_wash1         = Col('time_clearing_methanol_40percent_wash1')
    time_clearing_methanol_60percent_wash1         = Col('time_clearing_methanol_60percent_wash1')
    time_clearing_methanol_80percent_wash1         = Col('time_clearing_methanol_80percent_wash1')
    time_clearing_methanol_100percent_wash1        = Col('time_clearing_methanol_100percent_wash1')
    time_clearing_methanol_100percent_wash2        = Col('time_clearing_methanol_100percent_wash2')
    time_clearing_dcm_66percent_methanol_33percent = Col('time_clearing_dcm_66percent_methanol_33percent')
    time_clearing_dcm_wash1                     = Col('time_clearing_dcm_wash1')
    time_clearing_dcm_wash2                     = Col('time_clearing_dcm_wash2')
    time_clearing_dbe                           = Col('time_clearing_dbe')
    time_clearing_new_tubes                     = Col('time_clearing_new_tubes')
    clearing_notes                              = Col('clearing_notes')
   
class IdiscoAbbreviatedTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    time_pbs_wash1 = Col('time_pbs_wash1',)
    time_pbs_wash2 = Col('time_pbs_wash2',)
    time_pbs_wash3 = Col('time_pbs_wash3',)
    time_dehydr_methanol_20percent_wash1           = Col('time_dehydr_methanol_20percent_wash1',)
    time_dehydr_methanol_40percent_wash1           = Col('time_dehydr_methanol_40percent_wash1',)
    time_dehydr_methanol_60percent_wash1           = Col('time_dehydr_methanol_60percent_wash1',)
    time_dehydr_methanol_80percent_wash1           = Col('time_dehydr_methanol_80percent_wash1',)
    time_dehydr_methanol_100percent_wash1          = Col('time_dehydr_methanol_100percent_wash1',)
    time_dehydr_methanol_100percent_wash2          = Col('time_dehydr_methanol_100percent_wash2',)
    time_dehydr_dcm_66percent_methanol_33percent   = Col('time_dehydr_dcm_66percent_methanol_33percent',)
    time_dehydr_dcm_wash1   = Col('time_dehydr_dcm_wash1')
    time_dehydr_dcm_wash2   = Col('time_dehydr_dcm_wash2')
    time_dehydr_dbe_wash1   = Col('time_dehydr_dbe_wash1')
    time_dehydr_dbe_wash2   = Col('time_dehydr_dbe_wash2')
    clearing_notes                              = Col('clearing_notes')

class IdiscoAbbreviatedRatTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    time_pbs_wash1 = Col('time_pbs_wash1',)
    time_pbs_wash2 = Col('time_pbs_wash2',)
    time_pbs_wash3 = Col('time_pbs_wash3',)
    time_dehydr_methanol_20percent_wash1           = Col('time_dehydr_methanol_20percent_wash1',)
    time_dehydr_methanol_20percent_wash2           = Col('time_dehydr_methanol_20percent_wash2',)
    time_dehydr_methanol_40percent_wash1           = Col('time_dehydr_methanol_40percent_wash1',)
    time_dehydr_methanol_40percent_wash2           = Col('time_dehydr_methanol_40percent_wash1',)
    time_dehydr_methanol_60percent_wash1           = Col('time_dehydr_methanol_60percent_wash1',)
    time_dehydr_methanol_80percent_wash1           = Col('time_dehydr_methanol_80percent_wash1',)
    time_dehydr_methanol_80percent_wash2           = Col('time_dehydr_methanol_80percent_wash2',)
    time_dehydr_methanol_100percent_wash1          = Col('time_dehydr_methanol_100percent_wash1',)
    time_dehydr_methanol_100percent_wash2          = Col('time_dehydr_methanol_100percent_wash2',)

    time_dehydr_h202_wash1 = Col('time_dehydr_h202_wash1')
    time_dehydr_methanol_100percent_wash3 = Col('time_dehydr_methanol_100percent_wash3')
    time_dehydr_methanol_100percent_wash4 = Col('time_dehydr_methanol_100percent_wash4')
    time_dehydr_methanol_100percent_wash5 = Col('time_dehydr_methanol_100percent_wash5')

    time_dehydr_dcm_66percent_methanol_33percent = Col('time_dehydr_dcm_66percent_methanol_33percent')
    time_dehydr_dcm_wash1 = Col('time_dehydr_dcm_wash1')
    time_dehydr_dcm_wash2 = Col('time_dehydr_dcm_wash2')
    time_dehydr_dbe_wash1 = Col('time_dehydr_dbe_wash1')
    time_dehydr_dbe_wash2 = Col('time_dehydr_dbe_wash2')
    clearing_notes                              = Col('clearing_notes')

class UdiscoTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    time_dehydr_pbs_wash1 = Col('time_dehydr_pbs_wash1')
    time_dehydr_butanol_30percent = Col('time_dehydr_butanol_30percent')
    time_dehydr_butanol_50percent = Col('time_dehydr_butanol_50percent')
    time_dehydr_butanol_70percent = Col('time_dehydr_butanol_70percent')
    time_dehydr_butanol_80percent = Col('time_dehydr_butanol_80percent')
    time_dehydr_butanol_90percent = Col('time_dehydr_butanol_90percent')
    time_dehydr_butanol_96percent = Col('time_dehydr_butanol_96percent')
    time_dehydr_butanol_100percent = Col('time_dehydr_butanol_100percent')
    time_clearing_dcm_wash1 = Col('time_clearing_dcm_wash1')
    time_clearing_babb_wash1 = Col('time_clearing_babb_wash1')
    clearing_notes = Col('clearing_notes')