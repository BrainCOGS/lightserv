# start testredis in background if it is not running already
docker-compose -f docker-compose-redistest.yml up -d

# start celery worker in background if not running already
docker-compose -f docker-compose-celerytest.yml up -d

# Now run the actual test(s) that is defined in docker-compose-test.yml 
docker-compose -f docker-compose-test.yml up --abort-on-container-exit --scale coverage=0