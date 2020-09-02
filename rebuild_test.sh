# remove all running and stopped containers from the docker-compose file and the worker,
# except redis and the neuroglancer client

docker rm -f $(docker ps -a -f network=lightserv-test | grep -v "redis\|nglancerstatic" | awk '{print $1}')

# # Make the image used for actually running the tests
docker build -f ./flaskcelery.Dockerfile -t flaskcelery:test .

# Build docker-compose services
docker-compose -f docker-compose-test.yml build 

## cleanup network to make sure a good fresh one exists

# docker network rm lightserv-test

docker network create --attachable lightserv-test

## viewer-launcher test tag
cd viewer-launcher

docker build -f ./viewer-launcher.Dockerfile -t viewer-launcher:test .

## build cloud volume test tag
cd ../cloudvolume

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
