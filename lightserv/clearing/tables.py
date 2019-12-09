from flask import request
from flask_table import create_table,Table, Col, LinkCol, ButtonCol
from functools import partial
from lightserv.main.utils import table_sorter
from lightserv.main.tables import BoldTextCol, DateTimeCol, DesignatedRoleCol

def dynamic_clearing_management_table(contents,table_id,ignore_columns=[],
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
        if item['clearing_protocol'] == 'iDISCO abbreviated clearing':
            return {'bgcolor':'#FCA5A4'} # red
        elif item['clearing_protocol'] == 'iDISCO abbreviated clearing (rat)':
            return {'bgcolor':'#A4FCAC'} # green
        elif item['clearing_protocol'] == 'iDISCO+_immuno':
            return {'bgcolor':'#A4FCFA'} # cyan
        elif item['clearing_protocol'] == 'uDISCO':
            return {'bgcolor':'#B5B9D4'} # gray-blue
        elif item['clearing_protocol'] == 'iDISCO_EdU':
            return {'bgcolor':'#F4F96A'}
        else:
            return {}
        
    options = dict(
        border = True,
        allow_sort = True,
        no_items = "No samples at the moment",
        html_attrs = {"style":'font-size:18px; table-layout: fixed; width: 100%;',}, 
        table_id = table_id,
        classes = ['mb-4']
        ) 

    table_class = create_table(name,options=options)
    table_class.get_tr_attrs = dynamic_get_tr_attrs
    table_class.sort_url = dynamic_sort_url
    sort = sort_kwargs.get('sort_by','datetime_submitted')
    reverse = sort_kwargs.get('sort_reverse',False)
    """ Now loop through all columns and add them to the table,
    only adding the imaging modes if they are used in at least one
    sample """
    """ Add the columns that you want to go first here.
    It is OK if they get duplicated in the loop below -- they
    will not be added twice """
    table_class.add_column('datetime_submitted',DateTimeCol('datetime submitted'))
    table_class.add_column('clearing_protocol',Col('clearing protocol'))
    table_class.add_column('antibody1',Col('antibody1'))
    table_class.add_column('antibody2',Col('antibody2'))
    table_class.add_column('request_name',Col('request name'))
    table_class.add_column('username',Col('username'))
    table_class.add_column('clearer',DesignatedRoleCol('clearer'))
    
    if table_class.table_id == 'horizontal_ready_to_clear_table':
        table_class.add_column('clearing_progress',BoldTextCol('clearing progress'))
    else: 
        table_class.add_column('clearing_progress',Col('clearing progress'))

    table_class.add_column('species',Col('species'))    
    table_class.add_column('number_in_batch',Col('number in batch'))    

    ''' Now only add the start_imaging_link if the table is being imaged or ready to image '''
    clearing_url_kwargs = {'username':'username','request_name':'request_name',
        'sample_name':'sample_name','clearing_protocol':'clearing_protocol'}
    anchor_attrs = {'target':"_blank",}
    if table_id == 'horizontal_ready_to_clear_table':
        table_class.add_column('start_clearing_link',LinkCol('Start clearing',
         'clearing.clearing_entry',url_kwargs=clearing_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
    elif table_id == 'horizontal_being_cleared_table':
        table_class.add_column('continue_clearing_link',LinkCol('Continue clearing',
         'clearing.clearing_entry',url_kwargs=clearing_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
    elif table_id == 'horizontal_already_cleared_table':
        table_class.add_column('view_clearing_link',LinkCol('View clearing',
         'clearing.clearing_entry',url_kwargs=clearing_url_kwargs,
            anchor_attrs=anchor_attrs,allow_sort=False))
         
    sorted_contents = sorted(contents.fetch(as_dict=True),
            key=partial(table_sorter,sort_key=sort),reverse=reverse)
    table = table_class(sorted_contents)
    table.sort_by = sort
    table.sort_reverse = reverse
    
    return table 

class ClearingTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    request_name = Col('request_name',column_html_attrs=column_html_attrs)
    sample_name = Col('sample_name',column_html_attrs=column_html_attrs)
    clearing_protocol = Col('clearing_protocol',column_html_attrs=column_html_attrs)
    clearer = Col('clearer',column_html_attrs=column_html_attrs)
    clearing_progress = Col('clearing_progress',column_html_attrs=column_html_attrs)

class IdiscoPlusTable(Table):
    border = True
    no_items = "No Clearing Yet"
    html_attrs = {"style":'font-size:14px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    request_name = Col('request_name',column_html_attrs=column_html_attrs)
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
    request_name = Col('request_name',column_html_attrs=column_html_attrs)
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
    request_name = Col('request_name',column_html_attrs=column_html_attrs)
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
    request_name = Col('request_name',column_html_attrs=column_html_attrs)
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
    request_name = Col('request_name',column_html_attrs=column_html_attrs)
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