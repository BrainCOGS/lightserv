# remove all running and stopped containers from this docker-compose file
docker rm -f $(docker ps -a | grep lightserv | awk '{print $1}')

# Make the common image that will be used by flask and celery
docker build -f ./flaskcelery.Dockerfile -t flaskcelery:latest .

# Build docker-compose services
docker-compose build 

## cleanup network to make sure a good fresh one exists
docker network rm lightserv

docker network create --attachable lightserv

## build cloud volume latest tag
cd ./cloudvolume

docker build -f ./cloudvolume.Dockerfile -t cloudv:latest .

## build neuroglancer latest tag
cd ../neuroglancer

docker build -f ./neuroglancer.Dockerfile -t nglancer:latest .



