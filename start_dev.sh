# start neuroglnacer in background if it is not running already
docker-compose -f /home/ahoag/Git/nglancer-docker/docker-compose-dev.yml up -d

# start redis in background if it is not running already
docker-compose -f docker-compose-redisdev.yml up -d

# start celery worker in background if not running already
worker_containers=$(docker ps | grep "lightserv_worker" | awk '{print $1}') # prod will have lightservprod_worker so no collision will occur
if [ -z "$worker_containers" ] # checks if null
then
	echo "Celery test worker container not already started. Starting container."
	docker-compose -f docker-compose-celerydev.yml up -d
	echo "Sleeping to give time for worker to start up before main application starts"
	sleep 2
else
	echo "Celery test worker container already started"
fi

# Now run the rest of the dev services 
docker-compose -f docker-compose-dev.yml up 