
def test_tables_exist(test_client,test_schema):
	user_contents = test_schema.User()
	exp_contents = test_schema.Experiment()

	assert len(user_contents) == 12
	assert len(exp_contents) == 33

def test_User_table_ingested_correctly(test_client,test_schema):
	user_contents = test_schema.User()
	usernames,emails = user_contents.fetch('username','princeton_email')
	assert 'jverpeut' in usernames and 'tomohito' in usernames
	assert 'jverpeut@princeton.edu' in emails and 'zhihaoz@princeton.edu' in emails


