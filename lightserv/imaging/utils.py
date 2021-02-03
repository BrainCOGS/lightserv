import os

def count_files(filepath):
    return len(os.listdir(filepath))

def translate_lavision_to_smartspim_channel(lavision_channel_name):
    translate_dict = {
    	'488':'488',
    	'555':'561',
    	'647':'642',
    	'790':'785'
    	}
    return translate_dict[lavision_channel_name]

def translate_smartspim_to_lavision_channel(smartspim_channel_name):
    translate_dict = {
    	'488':'488',
    	'561':'555',
    	'642':'647',
    	'785':'790'
    	}
    return translate_dict[smartspim_channel_name]