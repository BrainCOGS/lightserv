docker rm -f $(docker ps -aq)

# Make the common image that will be used by flask and celery and for testing
docker build -f ./flaskcelery.Dockerfile -t flaskcelery_test:latest .

# Build docker-compose services
docker-compose -f docker-compose-test.yml build 

## build cloud volume latest tag
cd ./cloudvolume

docker build -f ./cloudvolume.Dockerfile -t cloudv:latest .

## build neuroglancer latest tag
cd ../neuroglancer

docker build -f ./neuroglancer.Dockerfile -t nglancer:latest .

