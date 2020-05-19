# remove all running and stopped containers from this docker-compose file
# docker rm -f $(docker ps -a | grep "lightserv\|cloudv_viewer\|nglancer_viewer\|nglancer_registration_viewer" | awk '{print $1}')
docker rm -f $(docker ps -a | grep "lightserv_testredis\|lightserv_testflask" | awk '{print $1}')

# Make the common image that will be used by flask and celery
docker build -f ./flaskcelery.Dockerfile -t flaskcelery:test .

# Build docker-compose services
docker-compose -f docker-compose-dev.yml build 

## cleanup network to make sure a good fresh one exists

# docker network rm lightserv-test

docker network create --attachable lightserv-test
