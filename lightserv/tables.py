# import flask_table
from flask import url_for,flash,redirect
from flask_table import Table, Col, LinkCol

class UserTable(Table):
    border = True
    username = Col('username')
    email = Col('email')

class ExpTable(Table):
    border = True
    allow_sort = True
    no_items = "No Experiments Yet"
    html_attrs = {"style":'font-size:10px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    title = Col('title',column_html_attrs=column_html_attrs,)
    description = Col('description',column_html_attrs=column_html_attrs)
    species = Col('species',column_html_attrs=column_html_attrs)
    clearing_protocol = Col('clearing_protocol',column_html_attrs=column_html_attrs)
    clearing_progress = Col('clearing_progress',column_html_attrs=column_html_attrs)
    fluorophores = Col('fluorophores',column_html_attrs=column_html_attrs)
    primary_antibody = Col('primary_antibody',column_html_attrs=column_html_attrs)
    secondary_antibody = Col('secondary_antibody',column_html_attrs=column_html_attrs)
    image_resolution = Col('image_resolution',column_html_attrs=column_html_attrs)
    cell_detection = Col('cell_detection',column_html_attrs=column_html_attrs)
    registration = Col('registration',column_html_attrs=column_html_attrs)
    probe_detection = Col('probe_detection',column_html_attrs=column_html_attrs)
    injection_detection = Col('injection_detection',column_html_attrs=column_html_attrs)

    url_kwargs = {'clearing_protocol':'clearing_protocol','experiment_id':'experiment_id',}
    anchor_attrs = {'target':"_blank",}
    
    clearing_link = LinkCol('Edit clearing','clearing.clearing_entry',url_kwargs=url_kwargs,anchor_attrs=anchor_attrs)
    experiment_link = LinkCol('View experiment', 'experiments.exp',url_kwargs=url_kwargs,anchor_attrs=anchor_attrs)
    
    def sort_url(self, col_key, reverse=False):
        if col_key == 'experiment_link':
            return url_for('main.home')
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'
        return url_for('main.home', sort=col_key, direction=direction)


class ClearingTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:12px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    title = Col('title',column_html_attrs=column_html_attrs,)
    description = Col('description',column_html_attrs=column_html_attrs)
    clearing_protocol = Col('clearing_protocol',column_html_attrs=column_html_attrs)
    clearing_progress = Col('clearing_progress',column_html_attrs=column_html_attrs)

    # clearing_notes = Col('notes',column_html_attrs=column_html_attrs)

    # species = Col('species',column_html_attrs=column_html_attrs)
    # clearing_protocol = Col('clearing_protocol',column_html_attrs=column_html_attrs)


class MicroscopeCalibrationTable(Table):
    border = True
    allow_sort = True
    no_items = "No Logs Yet"
    html_attrs = {"style":'font-size:10px'} # gets assigned to table header
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

    delete_link = LinkCol('Update entry', 'microscope.update_entry',url_kwargs=kwargs,anchor_attrs=anchor_attrs)

   
    def sort_url(self, col_key, reverse=False):
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'
        return url_for('microscope.swap_calibrate_log', sort=col_key, direction=direction)

class IdiscoPlusTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:12px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    time_dehydr_pbs_wash1 = Col('time_dehydr_pbs_wash1',)
    time_dehydr_pbs_wash2 = Col('time_dehydr_pbs_wash2',)
    time_dehydr_pbs_wash3 = Col('time_dehydr_pbs_wash3',)
    time_dehydr_ch3oh_20percent_wash1           = Col('time_dehydr_ch3oh_20percent_wash1',)
    time_dehydr_ch3oh_40percent_wash1           = Col('time_dehydr_ch3oh_40percent_wash1',)
    time_dehydr_ch3oh_60percent_wash1           = Col('time_dehydr_ch3oh_60percent_wash1',)
    time_dehydr_ch3oh_80percent_wash1           = Col('time_dehydr_ch3oh_80percent_wash1',)
    time_dehydr_ch3oh_100percent_wash1          = Col('time_dehydr_ch3oh_100percent_wash1',)
    time_dehydr_ch3oh_100percent_wash2          = Col('time_dehydr_ch3oh_100percent_wash2',)
    time_dehydr_h202_wash1                      = Col('time_dehydr_h202_wash1',)
    time_rehydr_ch3oh_100percent_wash1          = Col('time_rehydr_ch3oh_100percent_wash1',)
    time_rehydr_ch3oh_80percent_wash1           = Col('time_rehydr_ch3oh_80percent_wash1',)
    time_rehydr_ch3oh_60percent_wash1           = Col('time_rehydr_ch3oh_60percent_wash1',)
    time_rehydr_ch3oh_40percent_wash1           = Col('time_rehydr_ch3oh_40percent_wash1',)
    time_rehydr_ch3oh_20percent_wash1           = Col('time_rehydr_ch3oh_20percent_wash1',)
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
    time_clearing_ch3oh_20percent_wash1         = Col('time_clearing_ch3oh_20percent_wash1')
    time_clearing_ch3oh_40percent_wash1         = Col('time_clearing_ch3oh_40percent_wash1')
    time_clearing_ch3oh_60percent_wash1         = Col('time_clearing_ch3oh_60percent_wash1')
    time_clearing_ch3oh_80percent_wash1         = Col('time_clearing_ch3oh_80percent_wash1')
    time_clearing_ch3oh_100percent_wash1        = Col('time_clearing_ch3oh_100percent_wash1')
    time_clearing_ch3oh_100percent_wash2        = Col('time_clearing_ch3oh_100percent_wash2')
    time_clearing_dcm_66percent_ch3oh_33percent = Col('time_clearing_dcm_66percent_ch3oh_33percent')
    time_clearing_dcm_wash1                     = Col('time_clearing_dcm_wash1')
    time_clearing_dcm_wash2                     = Col('time_clearing_dcm_wash2')
    time_clearing_dbe                           = Col('time_clearing_dbe')
    time_clearing_new_tubes                     = Col('time_clearing_new_tubes')
    clearing_notes                              = Col('clearing_notes')
   
class IdiscoAbbreviatedTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:12px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    time_pbs_wash1 = Col('time_pbs_wash1',)
    time_pbs_wash2 = Col('time_pbs_wash2',)
    time_pbs_wash3 = Col('time_pbs_wash3',)
    time_dehydr_ch3oh_20percent_wash1           = Col('time_dehydr_ch3oh_20percent_wash1',)
    time_dehydr_ch3oh_40percent_wash1           = Col('time_dehydr_ch3oh_40percent_wash1',)
    time_dehydr_ch3oh_60percent_wash1           = Col('time_dehydr_ch3oh_60percent_wash1',)
    time_dehydr_ch3oh_80percent_wash1           = Col('time_dehydr_ch3oh_80percent_wash1',)
    time_dehydr_ch3oh_100percent_wash1          = Col('time_dehydr_ch3oh_100percent_wash1',)
    time_dehydr_ch3oh_100percent_wash2          = Col('time_dehydr_ch3oh_100percent_wash2',)
    time_dehydr_dcm_66percent_ch3oh_33percent   = Col('time_dehydr_dcm_66percent_ch3oh_33percent',)
    time_dehydr_dcm_wash1   = Col('time_dehydr_dcm_wash1')
    time_dehydr_dcm_wash2   = Col('time_dehydr_dcm_wash2')
    time_dehydr_dbe_wash1   = Col('time_dehydr_dbe_wash1')
    time_dehydr_dbe_wash2   = Col('time_dehydr_dbe_wash2')
    clearing_notes                              = Col('clearing_notes')

class IdiscoAbbreviatedRatTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:12px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    time_pbs_wash1 = Col('time_pbs_wash1',)
    time_pbs_wash2 = Col('time_pbs_wash2',)
    time_pbs_wash3 = Col('time_pbs_wash3',)
    time_dehydr_ch3oh_20percent_wash1           = Col('time_dehydr_ch3oh_20percent_wash1',)
    time_dehydr_ch3oh_40percent_wash1           = Col('time_dehydr_ch3oh_40percent_wash1',)
    time_dehydr_ch3oh_60percent_wash1           = Col('time_dehydr_ch3oh_60percent_wash1',)
    time_dehydr_ch3oh_80percent_wash1           = Col('time_dehydr_ch3oh_80percent_wash1',)
    time_dehydr_ch3oh_100percent_wash1          = Col('time_dehydr_ch3oh_100percent_wash1',)
    time_dehydr_ch3oh_100percent_wash2          = Col('time_dehydr_ch3oh_100percent_wash2',)

    time_dehydr_h202_wash1 = Col('time_dehydr_h202_wash1')
    time_dehydr_ch3oh_100percent_wash3 = Col('time_dehydr_ch3oh_100percent_wash3')
    time_dehydr_ch3oh_100percent_wash4 = Col('time_dehydr_ch3oh_100percent_wash4')
    time_dehydr_ch3oh_100percent_wash5 = Col('time_dehydr_ch3oh_100percent_wash5')

    time_dehydr_dcm_66percent_ch3oh_33percent = Col('time_dehydr_dcm_66percent_ch3oh_33percent')
    time_dehydr_dcm_wash1 = Col('time_dehydr_dcm_wash1')
    time_dehydr_dcm_wash2 = Col('time_dehydr_dcm_wash2')
    time_dehydr_dbe_wash1 = Col('time_dehydr_dbe_wash1')
    time_dehydr_dbe_wash2 = Col('time_dehydr_dbe_wash2')
    clearing_notes                              = Col('clearing_notes')
