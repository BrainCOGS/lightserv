# remove all running and stopped containers from this docker-compose file
docker rm -f $(docker ps -a | grep "lightserv_viewer-launcher\|lightserv_confproxy\|\
lightserv_flask\|nglancer_viewer:latest\|nglancer_registration_viewer:latest\|\
cloudv_viewer:latest\|nglancer_custom_viewer:latest" | awk '{print $1}'	)

# Make the common image that will be used by flask and celery
docker build -f ./flaskcelery.Dockerfile -t flaskcelery:latest .

# Build docker-compose services
docker-compose -f docker-compose-dev.yml build 

## cleanup network to make sure a good fresh one exists

docker network rm lightserv-dev

docker network create --attachable lightserv-dev

## build cloud volume latest tag
cd ./cloudvolume

docker build -f ./cloudvolume.Dockerfile -t cloudv_viewer:latest .
	
## build neuroglancer-raw latest tag
cd ../neuroglancer-raw

docker build -f ./neuroglancer.Dockerfile -t nglancer_raw_viewer:latest .

## build neuroglancer latest tag
cd ../neuroglancer

docker build -f ./neuroglancer.Dockerfile -t nglancer_viewer:latest .

## build neuroglancer-registration latest tag
cd ../neuroglancer-registration

docker build -f ./neuroglancer.Dockerfile -t nglancer_registration_viewer:latest .

## build neuroglancer-custom latest tag
cd ../neuroglancer-custom

docker build -f ./neuroglancer.Dockerfile -t nglancer_custom_viewer:latest .




