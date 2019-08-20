import flask_table

class UserTable(flask_table.Table):
    border = True
    username = flask_table.Col('username')
    email = flask_table.Col('email')

class ExpTable(flask_table.Table):
    border = True
    no_items = "No Experiments Yet"
    # classes = ["table-wrapper-scroll-x"]
    # classes = ["table","table-striped","table-bordered","table-sm"]
    classes = ["table-striped"]
    html_attrs = {'width':'100%'}
    username = flask_table.Col('username')
    experiment_id = flask_table.Col('experiment_id')
    title = flask_table.Col('title')
    description = flask_table.Col('description')
    species = flask_table.Col('species')
    clearing_protocol = flask_table.Col('clearing_protocol')
    fluorophores = flask_table.Col('fluorophores')
    primary_antibody = flask_table.Col('primary_antibody')
    secondary_antibody = flask_table.Col('secondary_antibody')
    image_resolution = flask_table.Col('image_resolution')
    cell_detection = flask_table.Col('cell_detection')
    registration = flask_table.Col('registration')
    probe_detection = flask_table.Col('probe_detection')
    injection_detection = flask_table.Col('injection_detection')
    # kwargs = {'animal_id': 'animal_id', 'surgery_id': 'surgery_id'}
    kwargs = {'experiment_id':'experiment_id',}
    anchor_attrs = {'target':"_blank"}
    
    experiment_link = flask_table.LinkCol('View experiment', 'experiments.exp',url_kwargs=kwargs,anchor_attrs=anchor_attrs)
    delete_experiment_button = flask_table.ButtonCol('Delete experiment', 'experiments.exp',url_kwargs=kwargs,anchor_attrs=anchor_attrs)


class ExpTable_nolink(flask_table.Table):
    border = True
    username = flask_table.Col('username')
    experiment = flask_table.Col('experiment')
    species = flask_table.Col('species')
    clearing_protocol = flask_table.Col('clearing_protocol')
    fluorophores = flask_table.Col('fluorophores')
    primary_antibody = flask_table.Col('primary_antibody')
    secondary_antibody = flask_table.Col('secondary_antibody')
    image_resolution = flask_table.Col('image_resolution')

class SelectCol(flask_table.Col):
    def td_format(self, content):
        html = '<select name="{}">'.format(content['name'])
        html += '<option></option>'
        for option, value in zip(content['options'], content.get('values',
                                                                 content['options'])):
            html += '<option value="{}"{}>{}</option>'.format(value, ' selected' if
            option == content.get('default', None) else '', option)
        html += "</select>"
        return html


class CheckBoxCol(flask_table.Col):
    def __init__(self, *args, checked=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.checked = checked

    def td_format(self, content):
        html = '<input type="checkbox" name="{}" value="{}"{}>'.format(content['name'],
                                                                       content['value'],
                                                                       ' checked' if self.checked else '')
        return html


class CheckMarkCol(flask_table.Col):
    def td_format(self, content):
        return '<span class ="glyphicon {}" ></span>'.format('glyphicon-ok' if content
                                                              else 'glyphicon-remove')


class SimpleCheckMarkCol(flask_table.Col):
    def td_format(self, content):
        return '{}'.format('yes' if content else '')

class KeyColumn(flask_table.Col):
    def td_format(self, content):
        key = {name: content[name][0] for name in content.dtype.names}  # recarray to dict
        return '<code>{}</code>'.format(key)


class CorrectionTable(flask_table.Table):
    classes = ['Relation']
    animal_id = flask_table.Col('Animal Id')
    session = flask_table.Col('Session')
    scan_idx = flask_table.Col('Scan Idx')
    pipe_version = flask_table.Col('Pipe Version')
    field = flask_table.Col('Field')

    channel = SelectCol('Channel')


class StackCorrectionTable(flask_table.Table):
    classes = ['Relation']
    animal_id = flask_table.Col('Animal Id')
    session = flask_table.Col('Session')
    stack_idx = flask_table.Col('Stack Idx')

    channel = SelectCol('Channel')


class SegmentationTable(flask_table.Table):
    classes = ['Relation']
    animal_id = flask_table.Col('Animal Id')
    session = flask_table.Col('Session')
    scan_idx = flask_table.Col('Scan')
    pipe_version = flask_table.Col('Pipe Version')
    field = flask_table.Col('Field')
    channel = flask_table.Col('Channel')

    compartment = SelectCol('Compartment')
    ignore = CheckBoxCol('Ignore')


class ProgressTable(flask_table.Table):
    classes = ['Relation']
    table = flask_table.Col('Table')
    processed = flask_table.Col('Processed')
    percentage = flask_table.Col('Percentage')


class JobTable(flask_table.Table):
    classes = ['Relation']
    table_name = flask_table.Col('Table Name')
    status = flask_table.Col('Status')
    key = KeyColumn('Key')
    user = flask_table.Col('User')
    key_hash = flask_table.Col('Key Hash')
    error_message = flask_table.Col('Error Message')
    timestamp = flask_table.DatetimeCol('Timestamp')

    delete = CheckBoxCol('Delete')


class SurgeryStatusTable(flask_table.Table):
    classes = ['Relation']
    animal_id = flask_table.Col('Animal ID')
    username = flask_table.Col('Username')
    date = flask_table.DateCol('Surgery Date')
    mouse_room = flask_table.Col('Room')
    timestamp = flask_table.DatetimeCol('Timestamp')
    day_one = flask_table.BoolCol('Day 1 Check')
    day_two = flask_table.BoolCol('Day 2 Check')
    day_three = flask_table.BoolCol('Day 3 Check')
    euthanized = flask_table.BoolCol('Euthanized')
    checkup_notes = flask_table.Col('Notes')

    kwargs = {'animal_id': 'animal_id', 'surgery_id': 'surgery_id'}
    link = flask_table.LinkCol('Edit', 'main.surgery_update', url_kwargs=kwargs)



class CheckmarkTable(flask_table.Table):
    classes = ['table']
    relation = flask_table.Col('Relation')
    populated = CheckMarkCol('Populated')


class InfoTable(flask_table.Table):
    classes = ['table']
    attribute = flask_table.Col('Attribute')
    value = flask_table.Col('Value')

class StatsTable(flask_table.Table):
    classes = ['Relation']
    field = flask_table.Col('Field')
    somas = flask_table.Col('Number of cells')
    depth = flask_table.Col('Depth from surface [um]')

class CellTable(flask_table.Table):
    classes = ['Relation']

    session = flask_table.Col('Session')
    scan_idx = flask_table.Col('Scan')
    somas = flask_table.Col('Detected Somas')




class SummaryTable(flask_table.Table):
    classes = ['Relation']
    animal_id = flask_table.Col('Animal Id')
    session = flask_table.Col('Session')
    scan_idx = flask_table.Col('Scan Idx')
    field = flask_table.Col('Field')
    pipe_version = flask_table.Col('Pipe Version')

    kwargs = {'animal_id': 'animal_id', 'session': 'session', 'scan_idx': 'scan_idx',
              'field': 'field', 'pipe_version': 'pipe_version'}
    correlation = flask_table.LinkCol('Correlation Image', 'main.figure', url_kwargs=kwargs,
                                      url_kwargs_extra={'which': 'correlation'})
    average = flask_table.LinkCol('Average Image', 'main.figure', url_kwargs=kwargs,
                                  url_kwargs_extra={'which': 'average'})
    traces = flask_table.LinkCol('Spike Traces', 'main.traces', url_kwargs=kwargs,
                                 url_kwargs_extra={'channel': 1, 'segmentation_method': 6,
                                                   'spike_method': 5})

def create_datajoint_table(rels, name='DataJoint Table', selection=None,
                           check_funcs = None, **fetch_kwargs):

    if not isinstance(rels, list):
        rels = [rels]

    table_class = flask_table.create_table(name)
    if selection is None:
        selection = set(rels[0].heading.attributes)
        for rel in rels[1:]:
            selection &= set(rel.heading.attributes)
    for col in rels[0].heading.attributes:
        if col in selection:
            table_class.add_column(col, flask_table.Col(col))

    if check_funcs is not None:
        for col in check_funcs:
            table_class.add_column(col, SimpleCheckMarkCol(col))

    items = []
    for rel in rels:
        new_items = rel.proj(*rel.heading.non_blobs).fetch(as_dict=True, **fetch_kwargs)

        for item in new_items:
            for blob_col in rel.heading.blobs:
                item[blob_col] = '<BLOB>'
        if selection is not None:
            for i in range(len(new_items)):
                entry = {k:v for k,v in new_items[i].items() if k in selection}
                if check_funcs is not None:
                    add = {}
                    for col, f in check_funcs.items():
                        add[col] = f(entry)
                    entry.update(add)
                new_items[i] = entry

        items.extend(new_items)

    table_class.classes = ['Relation']
    table = table_class(items)

    return table


def create_pandas_table(rels, name='Pandas Table', selection=None,
                           check_funcs = None, **fetch_kwargs):

    if not isinstance(rels, list):
        rels = [rels]
    table_class = flask_table.create_table(name)
    if selection is None:
        selection = set(rels[0].columns)
        for rel in rels[1:]:
            selection &= set(rel.columns)
    for col in rels[0].columns:
        if col in selection:
            table_class.add_column(col, flask_table.Col(col))

    if check_funcs is not None:
        for col in check_funcs:
            table_class.add_column(col, SimpleCheckMarkCol(col))

    items = []
    for new_items in rels:

            for d in map(lambda x: x[1].to_dict(), new_items.iterrows()):
                if selection is not None:
                    entry = {k:v for k,v in d.items() if k in selection}
                else:
                    entry = d

                if check_funcs is not None:
                    add = {}
                    for col, f in check_funcs.items():
                        add[col] = f(entry)
                    entry.update(add)
                items.append(entry)

    table_class.classes = ['Relation']
    table = table_class(items)

    return table

