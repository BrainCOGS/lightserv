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
    # classes = ["table-wrapper-scroll-x"]
    # classes = ["table","table-striped","table-bordered","table-sm"]
    html_attrs = {"style":'font-size:10px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    # td_html_attrs = {"align":"center"}
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    # html_attrs = {'style':'width:100%',"text-align":"center"}
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    title = Col('title',column_html_attrs=column_html_attrs,)
    description = Col('description',column_html_attrs=column_html_attrs)
    # notes = Col('notes',column_html_attrs=column_html_attrs)
    species = Col('species',column_html_attrs=column_html_attrs)
    clearing_protocol = Col('clearing_protocol',column_html_attrs=column_html_attrs)
    fluorophores = Col('fluorophores',column_html_attrs=column_html_attrs)
    primary_antibody = Col('primary_antibody',column_html_attrs=column_html_attrs)
    secondary_antibody = Col('secondary_antibody',column_html_attrs=column_html_attrs)
    image_resolution = Col('image_resolution',column_html_attrs=column_html_attrs)
    cell_detection = Col('cell_detection',column_html_attrs=column_html_attrs)
    registration = Col('registration',column_html_attrs=column_html_attrs)
    probe_detection = Col('probe_detection',column_html_attrs=column_html_attrs)
    injection_detection = Col('injection_detection',column_html_attrs=column_html_attrs)
    # kwargs = {'animal_id': 'animal_id', 'surgery_id': 'surgery_id'}
    kwargs = {'experiment_id':'experiment_id',}
    anchor_attrs = {'target':"_blank",}
    # anchor_attrs = {'target':"_blank",'data-toggle':'modal','data-target':'#deleteModal'}
    
    experiment_link = LinkCol('View experiment', 'experiments.exp',url_kwargs=kwargs,anchor_attrs=anchor_attrs)
    
    def sort_url(self, col_key, reverse=False):
        if col_key == 'experiment_link':
            # flash("Ah ah ah, you didn't say the magic word. Ah Ah Ah.",'danger')
            return url_for('main.home')
        if reverse:
            direction = 'desc'
        else:
            direction = 'asc'
        return url_for('main.home', sort=col_key, direction=direction)


class ClearingTable(Table):
    border = True
    no_items = "No Clearing Yet"
    # classes = ["table-wrapper-scroll-x"]
    # classes = ["table","table-striped","table-bordered","table-sm"]
    html_attrs = {"style":'font-size:10px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    # td_html_attrs = {"align":"center"}
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    # html_attrs = {'style':'width:100%',"text-align":"center"}
    username = Col('username',column_html_attrs=column_html_attrs)
    experiment_id = Col('experiment_id',column_html_attrs=column_html_attrs)
    title = Col('title',column_html_attrs=column_html_attrs,)
    # description = Col('description',column_html_attrs=column_html_attrs)
    clearing_notes = Col('notes',column_html_attrs=column_html_attrs)
    # species = Col('species',column_html_attrs=column_html_attrs)
    clearing_protocol = Col('clearing_protocol',column_html_attrs=column_html_attrs)


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

# class SelectCol(flask_table.Col):
#     def td_format(self, content):
#         html = '<select name="{}">'.format(content['name'])
#         html += '<option></option>'
#         for option, value in zip(content['options'], content.get('values',
#                                                                  content['options'])):
#             html += '<option value="{}"{}>{}</option>'.format(value, ' selected' if
#             option == content.get('default', None) else '', option)
#         html += "</select>"
#         return html


# class CheckBoxCol(flask_table.Col):
#     def __init__(self, *args, checked=False, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.checked = checked

#     def td_format(self, content):
#         html = '<input type="checkbox" name="{}" value="{}"{}>'.format(content['name'],
#                                                                        content['value'],
#                                                                        ' checked' if self.checked else '')
#         return html


# class CheckMarkCol(flask_table.Col):
#     def td_format(self, content):
#         return '<span class ="glyphicon {}" ></span>'.format('glyphicon-ok' if content
#                                                               else 'glyphicon-remove')


# class SimpleCheckMarkCol(flask_table.Col):
#     def td_format(self, content):
#         return '{}'.format('yes' if content else '')

# class KeyColumn(flask_table.Col):
#     def td_format(self, content):
#         key = {name: content[name][0] for name in content.dtype.names}  # recarray to dict
#         return '<code>{}</code>'.format(key)


# class CorrectionTable(flask_table.Table):
#     classes = ['Relation']
#     animal_id = flask_table.Col('Animal Id')
#     session = flask_table.Col('Session')
#     scan_idx = flask_table.Col('Scan Idx')
#     pipe_version = flask_table.Col('Pipe Version')
#     field = flask_table.Col('Field')

#     channel = SelectCol('Channel')


# class StackCorrectionTable(flask_table.Table):
#     classes = ['Relation']
#     animal_id = flask_table.Col('Animal Id')
#     session = flask_table.Col('Session')
#     stack_idx = flask_table.Col('Stack Idx')

#     channel = SelectCol('Channel')


# class SegmentationTable(flask_table.Table):
#     classes = ['Relation']
#     animal_id = flask_table.Col('Animal Id')
#     session = flask_table.Col('Session')
#     scan_idx = flask_table.Col('Scan')
#     pipe_version = flask_table.Col('Pipe Version')
#     field = flask_table.Col('Field')
#     channel = flask_table.Col('Channel')

#     compartment = SelectCol('Compartment')
#     ignore = CheckBoxCol('Ignore')


# class ProgressTable(flask_table.Table):
#     classes = ['Relation']
#     table = flask_table.Col('Table')
#     processed = flask_table.Col('Processed')
#     percentage = flask_table.Col('Percentage')


# class JobTable(flask_table.Table):
#     classes = ['Relation']
#     table_name = flask_table.Col('Table Name')
#     status = flask_table.Col('Status')
#     key = KeyColumn('Key')
#     user = flask_table.Col('User')
#     key_hash = flask_table.Col('Key Hash')
#     error_message = flask_table.Col('Error Message')
#     timestamp = flask_table.DatetimeCol('Timestamp')

#     delete = CheckBoxCol('Delete')


# class SurgeryStatusTable(flask_table.Table):
#     classes = ['Relation']
#     animal_id = flask_table.Col('Animal ID')
#     username = flask_table.Col('Username')
#     date = flask_table.DateCol('Surgery Date')
#     mouse_room = flask_table.Col('Room')
#     timestamp = flask_table.DatetimeCol('Timestamp')
#     day_one = flask_table.BoolCol('Day 1 Check')
#     day_two = flask_table.BoolCol('Day 2 Check')
#     day_three = flask_table.BoolCol('Day 3 Check')
#     euthanized = flask_table.BoolCol('Euthanized')
#     checkup_notes = flask_table.Col('Notes')

#     kwargs = {'animal_id': 'animal_id', 'surgery_id': 'surgery_id'}
#     link = flask_table.LinkCol('Edit', 'main.surgery_update', url_kwargs=kwargs)



# class CheckmarkTable(flask_table.Table):
#     classes = ['table']
#     relation = flask_table.Col('Relation')
#     populated = CheckMarkCol('Populated')


# class InfoTable(flask_table.Table):
#     classes = ['table']
#     attribute = flask_table.Col('Attribute')
#     value = flask_table.Col('Value')

# class StatsTable(flask_table.Table):
#     classes = ['Relation']
#     field = flask_table.Col('Field')
#     somas = flask_table.Col('Number of cells')
#     depth = flask_table.Col('Depth from surface [um]')

# class CellTable(flask_table.Table):
#     classes = ['Relation']

#     session = flask_table.Col('Session')
#     scan_idx = flask_table.Col('Scan')
#     somas = flask_table.Col('Detected Somas')




# class SummaryTable(flask_table.Table):
#     classes = ['Relation']
#     animal_id = flask_table.Col('Animal Id')
#     session = flask_table.Col('Session')
#     scan_idx = flask_table.Col('Scan Idx')
#     field = flask_table.Col('Field')
#     pipe_version = flask_table.Col('Pipe Version')

#     kwargs = {'animal_id': 'animal_id', 'session': 'session', 'scan_idx': 'scan_idx',
#               'field': 'field', 'pipe_version': 'pipe_version'}
#     correlation = flask_table.LinkCol('Correlation Image', 'main.figure', url_kwargs=kwargs,
#                                       url_kwargs_extra={'which': 'correlation'})
#     average = flask_table.LinkCol('Average Image', 'main.figure', url_kwargs=kwargs,
#                                   url_kwargs_extra={'which': 'average'})
#     traces = flask_table.LinkCol('Spike Traces', 'main.traces', url_kwargs=kwargs,
#                                  url_kwargs_extra={'channel': 1, 'segmentation_method': 6,
#                                                    'spike_method': 5})

# def create_datajoint_table(rels, name='DataJoint Table', selection=None,
#                            check_funcs = None, **fetch_kwargs):

#     if not isinstance(rels, list):
#         rels = [rels]

#     table_class = flask_table.create_table(name)
#     if selection is None:
#         selection = set(rels[0].heading.attributes)
#         for rel in rels[1:]:
#             selection &= set(rel.heading.attributes)
#     for col in rels[0].heading.attributes:
#         if col in selection:
#             table_class.add_column(col, flask_table.Col(col))

#     if check_funcs is not None:
#         for col in check_funcs:
#             table_class.add_column(col, SimpleCheckMarkCol(col))

#     items = []
#     for rel in rels:
#         new_items = rel.proj(*rel.heading.non_blobs).fetch(as_dict=True, **fetch_kwargs)

#         for item in new_items:
#             for blob_col in rel.heading.blobs:
#                 item[blob_col] = '<BLOB>'
#         if selection is not None:
#             for i in range(len(new_items)):
#                 entry = {k:v for k,v in new_items[i].items() if k in selection}
#                 if check_funcs is not None:
#                     add = {}
#                     for col, f in check_funcs.items():
#                         add[col] = f(entry)
#                     entry.update(add)
#                 new_items[i] = entry

#         items.extend(new_items)

#     table_class.classes = ['Relation']
#     table = table_class(items)

#     return table


# def create_pandas_table(rels, name='Pandas Table', selection=None,
#                            check_funcs = None, **fetch_kwargs):

#     if not isinstance(rels, list):
#         rels = [rels]
#     table_class = flask_table.create_table(name)
#     if selection is None:
#         selection = set(rels[0].columns)
#         for rel in rels[1:]:
#             selection &= set(rel.columns)
#     for col in rels[0].columns:
#         if col in selection:
#             table_class.add_column(col, flask_table.Col(col))

#     if check_funcs is not None:
#         for col in check_funcs:
#             table_class.add_column(col, SimpleCheckMarkCol(col))

#     items = []
#     for new_items in rels:

#             for d in map(lambda x: x[1].to_dict(), new_items.iterrows()):
#                 if selection is not None:
#                     entry = {k:v for k,v in d.items() if k in selection}
#                 else:
#                     entry = d

#                 if check_funcs is not None:
#                     add = {}
#                     for col, f in check_funcs.items():
#                         add[col] = f(entry)
#                     entry.update(add)
#                 items.append(entry)

#     table_class.classes = ['Relation']
#     table = table_class(items)

#     return table

