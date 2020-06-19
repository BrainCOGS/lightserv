# remove all running and stopped containers from the docker-compose file and the worker,
# which is started with restart_test.sh. Never take down the testredis service!

docker rm -f $(docker ps -a | grep "lightserv_testflask\
\|lightserv_testworker\|cloudv_viewer:test\|nglancer_raw_viewer:test" | awk '{print $1}')

# # Make the image used for actually running the tests
docker build -f ./flaskcelery.Dockerfile -t flaskcelery:test .

# Build docker-compose services
docker-compose -f docker-compose-test.yml build 

## cleanup network to make sure a good fresh one exists

# docker network rm lightserv-test

docker network create --attachable lightserv-test

## build cloud volume test tag
cd ./cloudvolume

docker build -f ./cloudvolume.Dockerfile -t cloudv_viewer:test .
	
## build neuroglancer-raw test tag
cd ../neuroglancer-raw

docker build -f ./neuroglancer.Dockerfile -t nglancer_raw_viewer:test .

## build neuroglancer test tag
cd ../neuroglancer

docker build -f ./neuroglancer.Dockerfile -t nglancer_viewer:test .

## build neuroglancer-registration test tag
cd ../neuroglancer-registration

docker build -f ./neuroglancer.Dockerfile -t nglancer_registration_viewer:test .
