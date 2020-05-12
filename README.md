# lightserv

lightserv is a flask application that enables users to submit requests to acquire light sheet microscopy images (and derivative data products) of their biological samples at the Princeton Neuroscience Institute U19 Brain Registration and Histology Core Facility. Users can view the status of their current and past requests and view their acquired data in Neuroglancer at each step in the image processing pipeline. 

The application uses [datajoint](https://github.com/datajoint/datajoint-python) to connect to a MariaDB database for storing metadata about the requests during the various steps in the pipeline. 

For visualization links, the application uses the BRAIN CoGS fork of the Neuroglancer client: [Neuroglancer](https://github.com/BrainCOGS/neuroglancer), which has added some light sheet specific features compared to its parent forks. 

The entire application is containerized using Docker and Docker-compose.

The service is hosted at [https://braincogs00.pni.princeton.edu](https://braincogs00.pni.princeton.edu). 

## Explanation of folder contents

- cloudvolume: docker container for spawning cloudvolumes -- these are used for hosting light sheet data so that it can be viewed in Neuroglancer

- lib: homemade python libraries  

- lightserv: the main flask application

- neuroglancer-registration: docker container for spawning neuroglancer viewer links, specifically for viewing data registered to a brain atlas

- neuroglancer: docker container for spawning neuroglancer viewer links, for viewing all data besides data registered to a brain atlas

- schemas: the database and table structure

- viewer-launcher: a flask app serving as an API for the main flask app to spawn docker containers. The main flask app cannot do this itself because the conatiner user needs to be root in order to spawn docker containers via the docker socket, and the main flask app needs to be a non-root user in order to write to the Princeton file system. The viewer-launcher container is run as root so it can spawn the containers via the docker socket. 