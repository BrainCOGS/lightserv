from ..models import User

def test_user_table_contents(test_client,init_database):
	user = User.query.first()
	assert user.username == "admin"
	assert user.email == "ad@min.com"