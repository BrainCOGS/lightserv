from lightserv import db_admin

# class UserActionLog(dj.Manual):
#     definition = """    # event logging table 
#     event_number  : int auto_increment
#     ---
#     timestamp = CURRENT_TIMESTAMP : timestamp 
#     browser_name    : varchar(255)
#     browser_version : varchar(255)
#     platform        : varchar(255)
#     event=""  : varchar(255)  # custom message
#     """

class UserActionLog(db_admin.Model):
    event_number = db_admin.Column(db_admin.Integer, primary_key=True)
    # timestamp = db_admin.Column(db_admin.Timestamp, unique=True, nullable=False)
    browser_name = db_admin.Column(db_admin.String(255), nullable=False)
    # browser_version = db_admin.Column(db_admin.String(255), nullable=False, )
    # platform = db_admin.Column(db_admin.String(255), nullable=False)
    event = db_admin.Column(db_admin.String(255), nullable=False)