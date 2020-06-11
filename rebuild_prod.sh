# remove all running and stopped containers from this docker-compose file,
# including any neuroglancer or cloudvolume containers that were spawned
# by the app
docker rm -f $(docker ps -a | grep "lightservprod\|nglancer_viewer:prod\|nglancer_registration_viewer:prod\|cloudv_viewer:prod" | awk '{print $1}')

# Make the common image that will be used by flask and celery
docker build -f ./flaskcelery.Dockerfile -t flaskcelery:prod .

# Build docker-compose services
docker-compose -f docker-compose-prod.yml build 

## cleanup network to make sure a good fresh one exists

docker network rm lightserv-prod

docker network create --attachable lightserv-prod

## build cloud volume latest tag
cd ./cloudvolume

docker build -f ./cloudvolume.Dockerfile -t cloudv_viewer:prod .
	
## build neuroglancer-raw prod tag
cd ../neuroglancer-raw

docker build -f ./neuroglancer.Dockerfile -t nglancer_raw_viewer:prod .

## build neuroglancer latest tag
cd ../neuroglancer

docker build -f ./neuroglancer.Dockerfile -t nglancer_viewer:prod .

## build neuroglancer-registration latest tag
cd ../neuroglancer-registration

docker build -f ./neuroglancer.Dockerfile -t nglancer_registration_viewer:prod .

## build neuroglancer-custom prod tag
cd ../neuroglancer-custom

docker build -f ./neuroglancer.Dockerfile -t nglancer_custom_viewer:prod .