from flask_table import Table, Col, LinkCol, ButtonCol


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