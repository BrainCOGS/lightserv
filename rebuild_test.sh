# docker rm -f $(docker ps -aq)

# Make the common image that will be used by flask and celery and for testing
docker build -f ./flaskcelery.Dockerfile -t flaskcelery_test:latest .

# Build docker-compose services
docker-compose -f docker-compose_test.yml build 