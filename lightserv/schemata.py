import datajoint as dj

db = dj.create_virtual_module('lightsheet_demo','ahoag_lightsheet_demo',create_schema=True) # first argument is abbreviated title, second is the actual name of the schema
# meso = dj.create_virtual_module('meso','pipeline_meso',create_schema=True)
# stack = dj.create_virtual_module('stack','pipeline_stack',create_schema=True)
# shared = dj.create_virtual_module('shared','pipeline_shared',create_schema=True)
# experiment = dj.create_virtual_module('experiment','pipeline_experiment',create_schema=True)
# tune = dj.create_virtual_module('tune','pipeline_tune',create_schema=True)
# pupil = dj.create_virtual_module('pupil','pipeline_eye',create_schema=True)
# treadmill = dj.create_virtual_module('behavior','pipeline_treadmill',create_schema=True)
# stimulus = dj.create_virtual_module('stimulus','pipeline_stimulus',create_schema=True)
# xcorr = dj.create_virtual_module('xcorr','pipeline_xcorr',create_schema=True)
# mice = dj.create_virtual_module('mice ','common_mice',create_schema=True)
# stack = dj.create_virtual_module('stack ','pipeline_stack',create_schema=True)

# dj.config['external-analysis'] = dict(
#     protocol='file',
#     location='/mnt/scratch05/datajoint-store/analysis')

# dj.config['external-maps'] = dict(
#     protocol='s3',
#     endpoint="kobold.ad.bcm.edu:9000",
#     bucket='microns-pipelines',
#     location='maps',
#     access_key="21IYGREPV4RS3IUU9ZYX",
#     secret_key="yzGLiu7ndHzMSCrobTliCpRDpP9WGdRv7YmrieJ0")

# dj.config['cache'] = os.path.expanduser('/mnt/data/dj-cache')


test_schema = dj.schema('test_lightsheet','test_lightsheet')
