# start redis in background if it is not running already
docker-compose -f docker-compose-redisprod.yml up -d

# start celery worker and scheduler in background if not running already
worker_containers=$(docker ps | grep "lightservprod_worker" | awk '{print $1}') 
if [ -z "$worker_containers" ] # checks if null
then
	echo "Celery worker container not already started. Starting container."
	docker-compose -f docker-compose-celeryprod.yml up -d
	echo "Sleeping to give time for worker to start up before main application starts"
	sleep 2
else
	echo "Celery worker container already started"
fi

# Now run the rest of the dev services 
docker-compose -f docker-compose-prod.yml up -d