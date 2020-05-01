version: "3.4"

services:
  redis:
    image: redis
    expose:
      - 6379
    restart: always
  confproxy:
    env_file: .dockerenv
    image: jupyterhub/configurable-http-proxy:3.1.1
    # expose the proxy to the world
    ports:
      - "8002:8000"
      - "8003:8001"
    command: ['configurable-http-proxy',
              '--auto-rewrite',
              '--no-include-prefix',
              '--no-prepend-path',
              '--log-level', 'debug',
              '--api-ip', '0.0.0.0']
  flask:
    env_file: .dockerenv
    hostname: docker_lightserv
    image: flaskcelery:latest
    command: ["python", "run.py"]
    volumes:
      - .:/app # so changes made to the app are propagated to the container without having to rebuild
      - /jukebox/LightSheetData:/jukebox/LightSheetData
      - /jukebox/LightSheetTransfer:/jukebox/LightSheetTransfer
      - ./lib:/opt/libraries # for progproxy api
    ports:
      - '8080:5000'
    # restart: always
  viewer-launcher:
    env_file: .dockerenv
    build:
      context: ./viewer-launcher
      dockerfile: viewer-launcher.Dockerfile
    command: ["python", "run.py"]
    volumes:
      - ./viewer-launcher:/app
      - /jukebox/LightSheetData:/jukebox/LightSheetData
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - '5003:5005'
  worker:
    env_file: .dockerenv
    image: flaskcelery:latest
    command: ["celery",
              "worker",
              "-A",
              "celery_worker.cel",
              "--loglevel=info"]
    volumes:
      - .:/app
      - ./lib:/opt/libraries
      - /jukebox/LightSheetData:/jukebox/LightSheetData
      - /jukebox/LightSheetTransfer:/jukebox/LightSheetTransfer
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      - redis
    # restart: always
  scheduler:
    env_file: .dockerenv
    image: flaskcelery:latest
    command: ["celery",
              "beat",
              "-A",
              "celery_worker.cel",
              "--schedule=/tmp/celerybeat-schedule",
              "--loglevel=info",
              "--pidfile=/tmp/celerybeat.pid"]
    volumes:
      - .:/app
      - ./lib:/opt/libraries
    depends_on:
      - redis
      - worker
    # restart: always
networks:
  default:
    external:
      name: lightserv-dev