#! /bin/env python

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image
import tifffile

from cloudvolume import CloudVolume
from cloudvolume.lib import mkdir, touch

import logging
import argparse

# home_dir = '/home/ahoag/ngdemo'
# atlas_file = '/home/ahoag/mounts/LightSheetTransfer/atlas/annotation_sagittal_atlas_20um_iso.tif'

def make_info_file(volume_size,layer_name,commit=True):
    """ 
    ---PURPOSE---
    Make the cloudvolume info file.
    ---INPUT---
    volume_size     [Nx,Ny,Nz] in voxels, e.g. [2160,2560,1271]
    layer_name      The name of the layer you want to create
    commit          if True, will write the info/provenance file to disk. 
                    if False, just creates it in memory
    """
    info = CloudVolume.create_new_info(
        num_channels = 1,
        layer_type = 'image', # 'image' or 'segmentation'
        data_type = 'uint16', # 
        encoding = 'raw', # other options: 'jpeg', 'compressed_segmentation' (req. uint32 or uint64)
        resolution = [ 20000, 20000, 20000 ], # X,Y,Z values in nanometers, 20 microns in each dim. 
        voxel_offset = [ 0, 0, 0 ], # values X,Y,Z values in voxels
        chunk_size = [ 1024,1024,1 ], # rechunk of image X,Y,Z in voxels -- only used for downsampling task I think
        volume_size = volume_size, # X,Y,Z size in voxels
        )

    vol = CloudVolume(f'file:///mnt/viz/{layer_name}', info=info)
    vol.provenance.description = "Created during lightserv pipeline"
    vol.provenance.owners = ['ahoag@princeton.edu'] # list of contact email addresses
    if commit:
        vol.commit_info() # generates info json file
        vol.commit_provenance() # generates provenance json file
        print("Created CloudVolume info file: ",vol.info_cloudpath)
    return vol


# def make_downsample(vol,mip_start=0,num_mips=3):
#     """ 
#     ---PURPOSE---
#     Make downsamples of the precomputed data
#     ---INPUT---
#     vol             The cloudvolume.Cloudvolume() object
#     mip_start       The mip level to start at with the downsamples
#     num_mips        The number of mip levels to create, starting from mip_start
#     """
#     # cloudpath = 'file:///home/ahoag/ngdemo/demo_bucket/m61467_demons_20190702/190821_647'
#     cloudpath = vol.cloudpath
#     with LocalTaskQueue(parallel=8) as tq:
#         tasks = tc.create_downsampling_tasks(
#             cloudpath, 
#             mip=mip_start, # Start downsampling from this mip level (writes to next level up)
#             fill_missing=False, # Ignore missing chunks and fill them with black
#             axis='z', 
#             num_mips=num_mips, # number of downsamples to produce. Downloaded shape is chunk_size * 2^num_mip
#             chunk_size=[ 128, 128, 64 ], # manually set chunk size of next scales, overrides preserve_chunk_size
#             preserve_chunk_size=True, # use existing chunk size, don't halve to get more downsamples
#           )
#         tq.insert_all(tasks)
#     print("Done!")  
    
def process_slice(z):
    print('Processing slice z=',z)
    
    array = image[z].reshape((1,y_dim,x_dim)).T 
    print(array.shape)
    vol[:,:, z] = array
    print("success")
    touch(os.path.join(progress_dir, str(z)))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    """ First load the tifffile in its entirety """
    # image = np.array(tifffile.imread(atlas_file),dtype=np.uint16, order='F') # F stands for fortran order
    # z_dim,y_dim,x_dim = image.shape
    parser = argparse.ArgumentParser()
    parser.add_argument("--x_dim", type=int, help="Size of volume in x in pixels")
    parser.add_argument("--y_dim", type=int, help="Size of volume in y in pixels")
    parser.add_argument("--z_dim", type=int, help="Size of volume in z in pixels")
    parser.add_argument("--layer_name", help="The name to give the layer that will be displayed in neuroglancer")
    args = parser.parse_args()
    print(args.x_dim)
    print(args.y_dim)
    print(args.z_dim)
    print(args.layer_name)
    x_dim = args.x_dim
    y_dim = args.y_dim
    z_dim = args.z_dim
    layer_name = args.layer_name
    vol = make_info_file(volume_size=(x_dim,y_dim,z_dim),layer_name=layer_name)
    # logging.info("wrote info file: /mnt/data/testfile.txt")
    # progress_dir = mkdir('/mnt/data/progress_princetonmouse/') # unlike os.mkdir doesn't crash on prexisting 

    # done_files = set([ int(z) for z in os.listdir(progress_dir) ])
    # all_files = set(range(vol.bounds.minpt.z, vol.bounds.maxpt.z)) 

    # to_upload = [ int(z) for z in list(all_files.difference(done_files)) ]
    # to_upload.sort()
    # print("Remaining slices to upload are:",to_upload)

    # with ProcessPoolExecutor(max_workers=8) as executor:
    #     executor.map(process_slice, to_upload)
        
    # vol.cache.flush()
