from __future__ import unicode_literals

from flask import session,current_app
from flask_table import Col,LinkCol,NestedTableCol
# from datetime import strftime
from functools import partial

from flask import Markup


channel_str_dict = {'regch':'registration','injch':'injection/probe detection',
                    'cellch':'cell detection','gench':'generic imaging'}

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

class ProcessingRequestLinkCol(LinkCol):
    """Subclass of LinkCol to show the processing request number 
    as a link to the table overview of that processing request,
    but keep the text displayed as the actual processing request number.
    This is hard (or impossible) to do with the regular LinkCol
    """

    def text(self, item, attr_list):
        return item['processing_request_number']

