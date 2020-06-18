# start testredis in background if it is not running already
docker-compose -f docker-compose-redistest.yml up -d

# start celery worker in background if not running already
worker_containers=$(docker ps | grep "lightserv_testworker" | awk '{print $1}')
if [ -z "$worker_containers" ] # checks if null
then
	echo "Celery test worker container not already started. Starting container."
	docker-compose -f docker-compose-celerytest.yml up -d
	echo "Sleeping to give time for worker to start up before running tests"
	sleep 4
else
	echo "Celery test worker container already started"
fi

# # Now run the actual test(s) that is defined in docker-compose-test.yml 
docker-compose -f docker-compose-test.yml up --abort-on-container-exit --scale testflask=0 coverage