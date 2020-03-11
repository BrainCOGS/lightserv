#! /bin/env python

from cloudvolume import CloudVolume
import types
import logging
import os
import numpy as np
import types
from time import sleep
# import progproxy as pp


def start_server():

    ## add some error checking
    if not os.path.isfile('/mnt/data/info'):
        logging.info('no valid volume found, using test data')
        arr = np.random.random_integers(0, high=255, size=(128,128, 128))
        arr = np.asarray(arr, dtype=np.uint8)
        vol = CloudVolume.from_numpy(arr, max_mip=1)
    else:
        logging.info('using mounted dataset')
        vol = CloudVolume('file:///mnt/data',parallel=2,cache=True)

    logging.info('volume created: {}'.format(vol[1,1,1]))

    logging.info('patching viewer to allow connections on all IPs')
    funcType = types.MethodType
    vol.viewer = funcType(localviewer, vol)

    logging.info('starting cloudvolume service')

    vol.viewer(port=1337)


## replacement version of the 'view' function for the object `CloudVolumePrecomputed`
def localviewer(self, port=1337):
    import cloudvolume.server
    logging.info('using replacement viewer function')
    logging.info('cloudpath: {}'.format(self.cloudpath))
    cloudvolume.server.view(self.cloudpath,hostname="0.0.0.0", port=port)


if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG)
    # logging.info(os.listdir('/mnt/data/'))
    # logging.info(pp)
    # proxy_h = pp.progproxy(target_hname="confproxy")
    # proxy_h.getroutes()
    # register_cloudvol_confproxy()
    # logging.info("made it here")
    start_server()
