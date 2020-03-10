docker rm -f $(docker ps -aq)

# Make the common image that will be used by flask and celery
docker build -f ./flaskcelery.Dockerfile -t flaskcelery_test:latest .

# Build docker-compose services
docker-compose build 

## cleanup network to make sure a good fresh one exists
docker network rm lightserv

docker network create --attachable lightserv