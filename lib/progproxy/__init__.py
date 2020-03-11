## pull in required libraries for logging
import logging
import sys


FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
formatter = logging.Formatter(FORMAT)
shandler = logging.StreamHandler(sys.stdout)
shandler.setFormatter(formatter)
logging.getLogger("progproxy").addHandler(shandler)
logging.getLogger("progproxy").setLevel(logging.INFO)


# from . import progproxy
from .progproxy import progproxy