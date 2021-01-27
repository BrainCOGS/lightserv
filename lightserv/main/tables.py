from __future__ import unicode_literals

from flask import session,current_app
from flask_table import Col,LinkCol,NestedTableCol, Table
# from datetime import strftime
from functools import partial
from flask import Markup
from lightserv import db_lightsheet

channel_str_dict = {'regch':'registration','injch':'injection/probe detection',
                    'cellch':'cell detection','gench':'generic imaging'}

""" Functions and classes that I use in all of my blueprints.
They are collected here just for organizational purposes """

def element(element, attrs=None, content='',
            escape_attrs=True, escape_content=True):
    return '<{element}{formatted_attrs}>{content}</{element}>'.format(
        element=element,
        formatted_attrs=_format_attrs(attrs or {}, escape_attrs),
        content=_format_content(content, escape_content),
    )

def _format_attrs(attrs, escape_attrs=True):
    out = []
    for name, value in sorted(attrs.items()):
        if escape_attrs:
            name = Markup.escape(name)
            value = Markup.escape(value)
        out.append(' {name}="{value}"'.format(name=name, value=value))
    return ''.join(out)

def _format_content(content, escape_content=True):
    if isinstance(content, (list, tuple)):
        content = ''.join(content)
    if escape_content:
        return Markup.escape(content)
    return content

class DateTimeCol(Col):
    """ Subclassing Col to show datetimes in a more
    human readable format  """

    def td_format(self, content):
        return content.strftime('%m/%d/%Y %-I:%M %p')

class DesignatedRoleCol(Col):
    """ Conditional bold fonting """
    def td_format(self, content):
        if content == None or content == '':
            return 'N/A'
        else:
            return content

class ChannelPurposeCol(Col):
    """ Column for showing the purpose
    of imaging/processing channels in human readable text  """
    def td_format(self, content):
        return channel_str_dict[content]

class BooltoStringCol(Col):
    """ Subclassing Col to show 'yes' if Boolean
    entry is True, 'no' if False """  
    def td_format(self, content):
        if content == True:
            return "yes"
        else:
            return "no"
class DorsalOrVentralCol(Col):
    """ Subclassing Col to show 'yes' if Boolean
    entry is True, 'no' if False """  
    def td_format(self, content):
        if content == 1:
            return "Ventral"
        else:
            return "Dorsal"

class NotAssignedCol(Col):
    """ Subclassing Col to show 'Not assigned' if 
    entry is None, otherwise show the original content """  
    def td_format(self, content):
        if not content or content == None or content == "None":
            return "Not assigned"
        else:
            return content
  
class NACol(Col):
    """ Subclassing Col to show 'N/A' if 
    entry is None, otherwise show the original content """  
    def td_format(self, content):
        if not content or content == None or content == "None":
            return "N/A"
        else:
            return content
  

class ProgressCol(Col):
    """ Conditional bold fonting """
    def __init__(self, name, attr=None, attr_list=None,
                 allow_sort=True, show=True,
                 th_html_attrs=None, td_html_attrs=None,
                 column_html_attrs=None,**kwargs):
        super(ProgressCol, self).__init__(
            name,
            attr=attr,
            attr_list=attr_list,
            **kwargs)
        self.name = name
        self.allow_sort = allow_sort
        self._counter_val = Col._counter
        self.attr_list = attr_list
        column_html_attrs = column_html_attrs or {}
        self.td_html_attrs = column_html_attrs.copy()

    def td(self, item, attr):
        content = self.td_contents(item, self.get_attr_list(attr))

        if content != 'complete':
            attrs = self.td_html_attrs.copy()
            attrs['bgcolor'] = "#F9F607"
            return element(
                'td',
                content=content,
                escape_content=False,
                attrs=attrs)
        else:
            return element(
                'td',
                content=content,
                escape_content=False,
                attrs=self.td_html_attrs)
    
class HeaderButtonLinkCol(Col):
    """ Conditional bold fonting """
    def __init__(self, name, attr=None, attr_list=None,
                 allow_sort=True, show=True,
                 th_html_attrs=None, td_html_attrs=None,
                 column_html_attrs=None,**kwargs):
        super(ProgressCol, self).__init__(
            name,
            attr=attr,
            attr_list=attr_list,
            **kwargs)
        self.name = name
        self.allow_sort = allow_sort
        self._counter_val = Col._counter
        self.attr_list = attr_list
        column_html_attrs = column_html_attrs or {}
        self.td_html_attrs = column_html_attrs.copy()

    def td(self, item, attr):
        content = self.td_contents(item, self.get_attr_list(attr))

        if content != 'complete':
            attrs = self.td_html_attrs.copy()
            attrs['bgcolor'] = "#F9F607"
            return element(
                'td',
                content=content,
                escape_content=False,
                attrs=attrs)
        else:
            return element(
                'td',
                content=content,
                escape_content=False,
                attrs=self.td_html_attrs)

class ImagingRequestLinkCol(LinkCol):
    """Subclass of LinkCol to show the imaging request number 
    as a link to the table overview of that imaging request,
    but keep the text displayed as the actual imaging request number.
    This is hard (or impossible) to do with the regular LinkCol
    """

    def text(self, item, attr_list):
        return item['imaging_request_number']

    def td_contents(self, item,attr_list):
        if self.text(item,attr_list) == 'N/A':
            return "N/A"
        if item['is_archival']:
            return self.text(item,attr_list)
        else:
            attrs = dict(href=self.url(item))
            attrs.update(self.anchor_attrs)
            text = self.td_format(self.text(item, attr_list))
            return element('a', attrs=attrs, content=text, escape_content=False)

class NewImagingRequestLinkCol(LinkCol):
    """Subclass of LinkCol to conditionally show the 
    new imaging request link for non-archival requests"
    """
    def __init__(self,name,endpoint,**kwargs):
        super(NewImagingRequestLinkCol, self).__init__(name,endpoint,**kwargs)
    
    def td_contents(self, item,attr_list):
        if item['is_archival']:
            return "N/A"
        else:
            attrs = dict(href=self.url(item))
            attrs.update(self.anchor_attrs)
            text = self.td_format(self.text(item, attr_list))
            return element('a', attrs=attrs, content=text, escape_content=False)

class ProcessingRequestLinkCol(LinkCol):
    """Subclass of LinkCol to conditionally show the processing request number 
    as a link to the table overview of that processing request,
    but keep the text displayed as the actual processing request number.
    The condition to show the link is if processing requests are allowed for this sample.
    If they are, show the link, if not show "N/A'"
    """
    def __init__(self,name,endpoint,**kwargs):
        super(ProcessingRequestLinkCol, self).__init__(name,endpoint,**kwargs)
    
    def text(self, item, attr_list):
        return item['processing_request_number']

    def td_contents(self, item,attr_list):
        if item['processing_request_number'] == None or item['processing_request_number'] == 'N/A':
            return "N/A"
        if item['is_archival']:
            return self.text(item,attr_list)
        else:
            attrs = dict(href=self.url(item))
            attrs.update(self.anchor_attrs)
            text = self.td_format(self.text(item, attr_list))
            return element('a', attrs=attrs, content=text, escape_content=False)

class NewProcessingRequestLinkCol(LinkCol):
    """Subclass of LinkCol to conditionally show a link to the form 
    requesting additional processing. The condition
    to show the link is if processing requests are allowed for this sample.
    If they are, show the link, if not show "N/A'"
    """
    def __init__(self,name,endpoint,**kwargs):
        super(NewProcessingRequestLinkCol, self).__init__(name,endpoint,**kwargs)

    def td_contents(self, item,attr_list):
        if item['processing_requests'][0]['processing_request_number'] == None:
            return "N/A"
        elif item['is_archival']:
            return "N/A"
        else:
            attrs = dict(href=self.url(item))
            attrs.update(self.anchor_attrs)
            text = self.td_format(self.text(item, attr_list))
            return element('a', attrs=attrs, content=text, escape_content=False)

class AbbrevDescriptionCol(Col):
    """ Column for showing an abbreviated version 
    of the description (works for any string-formatted column actually)  """
    def td_format(self, content):
        if len(content) > 64:
            return content[0:64] + ' ...'
        else:
            return content

class ConditionalDeleteLinkCol(LinkCol):
    """Subclass of LinkCol to conditionally show the "Delete request?" link in the 
    delete request column. 
    The condition to show the link is if no clearing batches have been started
    for this request yet. 
    If they are, show the link, if not show "N/A'"
    """
    def __init__(self,name,endpoint,**kwargs):
        super(ConditionalDeleteLinkCol, self).__init__(name,endpoint,**kwargs)
    
    def text(self, item, attr_list):
        return "Delete request?"

    def td_contents(self, item, attr_list):
        username=item['username']
        request_name=item['request_name']
        current_user = session['user']
        if current_user != username:
            return "N/A"
        restrict_dict = dict(username=username,
            request_name=request_name)
        clearing_batch_contents = db_lightsheet.Request.ClearingBatch() & restrict_dict
        clearing_batches_started = [clearing_dict['clearing_progress']!='incomplete' for clearing_dict in clearing_batch_contents]
        if any(clearing_batches_started):
            return "N/A"
        else:
            attrs = dict(href=self.url(item))
            attrs.update(self.anchor_attrs)
            text = self.td_format(self.text(item, attr_list))
            return element('a', attrs=attrs, content=text, escape_content=False)

class ConditionalRequestNameLinkCol(LinkCol):
    """Subclass of LinkCol to conditionally show no link 
    or the link to a request overview if username and request_name
    are provided 
    If provided, show the link, if not show "N/A'"
    """
    def __init__(self,name,endpoint,**kwargs):
        super(ConditionalRequestNameLinkCol, self).__init__(name,endpoint,**kwargs)
    
    def text(self, item, attr_list):
        return "Link to request"

    def td_contents(self, item, attr_list):
        username=item['username']
        request_name=item['request_name']
        
        if (not username) or (not request_name): 
            return "N/A"
        else:
            attrs = dict(href=self.url(item))
            attrs.update(self.anchor_attrs)
            text = self.td_format(self.text(item, attr_list))
            return element('a', attrs=attrs, content=text, escape_content=False)


""" Tables I use in main.routes """

class RequestTable(Table):
    border = True
    no_items = "No Request"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    username = Col('username',column_html_attrs=column_html_attrs)
    request_name = Col('request name',column_html_attrs=column_html_attrs)
    description = Col('description',column_html_attrs=column_html_attrs)
    species = Col('species',column_html_attrs=column_html_attrs)
    number_of_samples = Col('number_of_samples',column_html_attrs=column_html_attrs)



class AdminTable(Table):
    """ Table showing user actions """
    border = True
    no_items = "No User Actions yet"
    html_attrs = {"style":'font-size:18px'} # gets assigned to table header
    column_html_attrs = {'style':'text-align: center; min-width:10px'} # gets assigned to both th and td
    timestamp = DateTimeCol('timestamp',column_html_attrs=column_html_attrs)
    classes = ["table-striped"] # gets assigned to table classes. Striped is alternating bright and dark ros for visual ease.
    platform = Col('platform',column_html_attrs=column_html_attrs)
    event = Col('event',column_html_attrs=column_html_attrs)
