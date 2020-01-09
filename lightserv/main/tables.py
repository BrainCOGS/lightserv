from flask import session,current_app
from flask_table import Col,LinkCol
# from datetime import strftime

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

class BooltoStringCol(Col):
    """ Subclassing Col to show 'yes' if Boolean
    entry is True, 'no' if False """  
    def td_format(self, content):
        if content == True:
            return "yes"
        else:
            return "no"