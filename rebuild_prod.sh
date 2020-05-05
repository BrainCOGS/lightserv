# remove all running and stopped containers from this docker-compose file
# docker rm -f $(docker ps -a | grep "lightserv\|cloudv_viewer\|nglancer_viewer\|nglancer_registration_viewer" | awk '{print $1}')


# Make the common image that will be used by flask and celery
docker build -f ./flaskcelery.Dockerfile -t flaskcelery:latest .

# Build docker-compose services
docker-compose -f docker-compose-prod.yml build 

## cleanup network to make sure a good fresh one exists

docker network rm lightserv-prod

docker network create --attachable lightserv-prod

## build cloud volume latest tag
cd ./cloudvolume

docker build -f ./cloudvolume.Dockerfile -t cloudv_viewer:latest .
	
## build neuroglancer latest tag
cd ../neuroglancer

docker build -f ./neuroglancer.Dockerfile -t nglancer_viewer:latest .

## build neuroglancer-registration latest tag
cd ../neuroglancer-registration

docker build -f ./neuroglancer.Dockerfile -t nglancer_registration_viewer:latest .