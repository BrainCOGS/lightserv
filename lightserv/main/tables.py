from flask_table import Col,LinkCol

class HeadingCol(LinkCol):
    """ A hack to show certain columns as visual dividers 
    for different sections in the table """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_sort = False
    def td_format(self, content):
        html = '<a>----------</a>'
        return html


class BoldTextCol(Col):
    """ Bold font whatever text was in the column """
    def td_format(self, content):
        if content != 'complete':
            html = '<b>{}</b>'.format(content)
            return html
        else:
            return content