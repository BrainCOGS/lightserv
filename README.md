# lightserv

lightserv is a flask application that enables users to submit requests to acquire light sheet microscopy images (and derivative data products) of their biological samples at the Princeton Neuroscience Institute U19 Brain Registration and Histology Core Facility. Users can view the status of their current and past requests and view their acquired data in Neuroglancer at each step in the image processing pipeline. 

The application uses [datajoint](https://github.com/datajoint/datajoint-python) to connect to a MariaDB database for storing metadata about the requests during the various steps in the pipeline. 

For visualization links, the application uses the BRAIN CoGS fork of the Neuroglancer client: [Neuroglancer](https://github.com/BrainCOGS/neuroglancer), which has added some light sheet specific features compared to its parent forks. 

The entire application is containerized using Docker and Docker-compose.

The service is hosted at [https://braincogs00.pni.princeton.edu](https://braincogs00.pni.princeton.edu). 