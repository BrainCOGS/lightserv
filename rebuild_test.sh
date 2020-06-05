# remove all running and stopped containers from this docker-compose file
# docker rm -f $(docker ps -a | grep "lightserv\|cloudv_viewer\|nglancer_viewer\|nglancer_registration_viewer" | awk '{print $1}')
docker rm -f $(docker ps -a | grep "lightserv_testredis\|lightserv_testflask" | awk '{print $1}')

# Make the image used for actually running the tests
docker build -f ./flaskcelery.Dockerfile -t flaskcelery-test:test .
# Make the image used for getting test coverage
docker build -f ./flaskcelery-coverage.Dockerfile -t flaskcelery-coverage:test .

# Build docker-compose services
docker-compose -f docker-compose-test.yml build 

## cleanup network to make sure a good fresh one exists

# docker network rm lightserv-test

docker network create --attachable lightserv-test
