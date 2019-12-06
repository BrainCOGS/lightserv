from flask import session,current_app
from flask_table import Col,LinkCol
# from datetime import strftime

class HeadingCol(LinkCol):
    """ A hack to show certain columns as visual dividers 
    for different sections in the table """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_sort = False
    def td_format(self, content):
        html = '<a>----------</a>'
        return html

class DateTimeCol(Col):
    """ Subclassing Col to show datetimes in a more
    human readable format  """

    def td_format(self, content):
        return content.strftime('%m/%d/%Y %-I:%m %p')

class BoldTextCol(Col):
    """ Conditional bold fonting """
    def td_format(self, content):
        if content != 'complete':
            html = '<b>{}</b>'.format(content)
            return html
        else:
            return content


class ConditionalLinkCol(LinkCol):
    """ Subclassing linkcol to only show the link
    if the person if the current user is an admin
    of the task shown in the link or is the person
    performing the task (i.e. 'clearer','imager','processor') """  
    def td_contents(self, item, attr_list):
        # print(attr_list)
        if 'clearing' in self.name.lower():
            admins = current_app.config['CLEARING_ADMINS']
            person_assigned_to_task = item['clearer']
        elif 'processing' in self.name.lower():
            admins = current_app.config['PROCESSING_ADMINS']
            person_assigned_to_task = item['processor']
        if session['user'] in admins or session['user'] == person_assigned_to_task:
            return '<a href="{url}">{text}</a>'.format(
                url=self.url(item),
                text=self.td_format(self.text(item, attr_list)))
        else:
            return ""

class BooltoStringCol(Col):
    """ Subclassing Col to show 'yes' if Boolean
    entry is True, 'no' if False """  
    def td_format(self, content):
        if content == True:
            return "yes"
        else:
            return "no"