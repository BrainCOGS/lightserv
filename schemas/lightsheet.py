import datajoint as dj
import socket


dj.config['database.host'] = '127.0.0.1'
dj.config['database.port'] = 3306

dj.config['database.user'] = 'ahoag'
if socket.gethostname() == 'braincogs00.pni.princeton.edu':
	dj.config['database.password'] = 'gaoha'
else:
	dj.config['database.password'] = 'p@sswd'

schema = dj.schema('ahoag_lightsheet_demo')
schema.drop()
schema = dj.schema('ahoag_lightsheet_demo')

@schema
class User(dj.Lookup):
	definition = """
	# Users of the light sheet microscope
	username : varchar(20)      # user in the lab
	---
	princeton_email       : varchar(50)
	"""
	
@schema
class Experiment(dj.Manual):
	definition = """ # Experiments performed using the light sheet microscope
	-> User  
	experiment_name                        :   varchar(64)
	----
	date_submitted               :   date     # The date it was submitted as a request
	time_submitted               :   time     # The time it was submitted as a request
	labname                      :   varchar(50)
	correspondence_email = ''    :   varchar(100)
	description                  :   varchar(250)
	species                      :   varchar(50)
	number_of_samples            :   tinyint
	sample_prefix                :   varchar(32)
	"""  

@schema
class Sample(dj.Manual):
	definition = """ # Samples from a particular experiment
	-> Experiment
	sample_name                               :   varchar(64)                
	----
	perfusion_date = NULL        :   date
	expected_handoff_date = NULL :   date
	clearer = "not yet assigned" :   varchar(20) # netid of person doing the clearing
	clearing_protocol            :   enum("iDISCO+_immuno","iDISCO abbreviated clearing","iDISCO abbreviated clearing (rat)","uDISCO","iDISCO_EdU")
	clearing_progress            :   enum("incomplete","in progress","complete")
	antibody1 = ''               :   varchar(100)
	antibody2 = ''               :   varchar(100)
	notes_for_clearer = ""                    :   varchar(1024)
	imager = "not yet assigned"  :   varchar(20) # netid of person doing the imaging
    imaging_progress             :   enum("incomplete","in progress","complete")
    notes_for_imager = ""                     :   varchar(1024)
    imaging_date = NULL                       :   date
    processor = "not yet assigned"            :   varchar(20) # netid of person doing the processing
    processing_progress                       :   enum("incomplete","in progress","complete")
    stitching_method                          :   enum("blending","terastitcher")
	blend_type                                :   enum("sigmoidal","flat")
	atlas_name                                :   enum("allen_2017","allen_2011","princeton_mouse_atlas")
	intensity_correction = 1                  :   boolean
	"""  

	class ImagingChannel(dj.Part):
		definition = """ # Samples from a particular experiment
		-> Sample
		channel_name                              :   varchar(64)                
		----
		registration = 0                          :   boolean
		injection_detection = 0                   :   boolean
		probe_detection = 0                       :   boolean
		cell_detection = 0                        :   boolean
		image_resolution_requested = NULL         :   enum("1.3x","4x","1.1x","2x")
		image_resolution_used = NULL              :   enum("1.3x","4x","1.1x","2x")
		tiling_scheme = '1x1'                     :   char(3)
		tiling_overlap = 0.0                      :   float
		"""

	class IdiscoPlusClearing(dj.Part): # 
		definition = """ # iDISCO+ clearing table
		-> Sample           
		----
		exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during experiment that could affect clearing
		time_dehydr_pbs_wash1 = NULL                             :   datetime
		dehydr_pbs_wash1_notes = ""                              :   varchar(250)
		time_dehydr_pbs_wash2 = NULL                             :   datetime
		dehydr_pbs_wash2_notes = ""                              :   varchar(250)
		time_dehydr_pbs_wash3 = NULL                             :   datetime
		dehydr_pbs_wash3_notes = ""                              :   varchar(250)
		time_dehydr_methanol_20percent_wash1 = NULL                 :   datetime
		dehydr_methanol_20percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_40percent_wash1 = NULL                 :   datetime
		dehydr_methanol_40percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_60percent_wash1 = NULL                 :   datetime
		dehydr_methanol_60percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_80percent_wash1 = NULL                 :   datetime
		dehydr_methanol_80percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_100percent_wash1 = NULL                :   datetime
		dehydr_methanol_100percent_wash1_notes = ""                 :   varchar(250)
		time_dehydr_methanol_100percent_wash2 = NULL                :   datetime
		dehydr_methanol_100percent_wash2_notes = ""                 :   varchar(250)
		time_dehydr_h202_wash1 = NULL                            :   datetime
		dehydr_h202_wash1_notes = ""                             :   varchar(250)
		time_rehydr_methanol_100percent_wash1 = NULL                :   datetime
		rehydr_methanol_100percent_wash1_notes = ""                 :   varchar(250)
		time_rehydr_methanol_80percent_wash1 = NULL                 :   datetime
		rehydr_methanol_80percent_wash1_notes = ""                  :   varchar(250)
		time_rehydr_methanol_60percent_wash1 = NULL                 :   datetime
		rehydr_methanol_60percent_wash1_notes = ""                  :   varchar(250)
		time_rehydr_methanol_40percent_wash1 = NULL                 :   datetime
		rehydr_methanol_40percent_wash1_notes = ""                  :   varchar(250)
		time_rehydr_methanol_20percent_wash1 = NULL                 :   datetime
		rehydr_methanol_20percent_wash1_notes = ""                  :   varchar(250)
		time_rehydr_pbs_wash1 = NULL                             :   datetime
		rehydr_pbs_wash1_notes = ""                              :   varchar(250)
		time_rehydr_sodium_azide_wash1 = NULL                    :   datetime
		rehydr_sodium_azide_wash1_notes = ""                     :   varchar(250)
		time_rehydr_sodium_azide_wash2 = NULL                    :   datetime
		rehydr_sodium_azide_wash2_notes = ""                     :   varchar(250)
		time_rehydr_glycine_wash1 = NULL                         :   datetime
		rehydr_glycine_wash1_notes = ""                          :   varchar(250)
		time_blocking_start_roomtemp = NULL                      :   datetime
		blocking_start_roomtemp_notes = ""                       :   varchar(250)
		time_blocking_donkey_serum = NULL                        :   datetime
		blocking_donkey_serum_notes = ""                         :   varchar(250)
		time_antibody1_start_roomtemp = NULL                     :   datetime
		antibody1_start_roomtemp_notes = ""                      :   varchar(250)
		time_antibody1_ptwh_wash1 = NULL                         :   datetime
		antibody1_ptwh_wash1_notes = ""                          :   varchar(250)
		time_antibody1_ptwh_wash2 = NULL                         :   datetime
		antibody1_ptwh_wash2_notes = ""                          :   varchar(250)
		time_antibody1_added = NULL                              :   datetime
		antibody1_added_notes = ""                               :   varchar(250)
		time_wash1_start_roomtemp = NULL                         :   datetime
		wash1_start_roomtemp_notes = ""                          :   varchar(250)
		time_wash1_ptwh_wash1 = NULL                             :   datetime
		wash1_ptwh_wash1_notes = ""                              :   varchar(250)
		time_wash1_ptwh_wash2 = NULL                             :   datetime
		wash1_ptwh_wash2_notes = ""                              :   varchar(250)
		time_wash1_ptwh_wash3 = NULL                             :   datetime
		wash1_ptwh_wash3_notes = ""                              :   varchar(250)
		time_wash1_ptwh_wash4 = NULL                             :   datetime
		wash1_ptwh_wash4_notes = ""                              :   varchar(250)
		time_wash1_ptwh_wash5 = NULL                             :   datetime
		wash1_ptwh_wash5_notes = ""                              :   varchar(250)
		time_antibody2_added = NULL                              :   datetime
		antibody2_added_notes = ""                               :   varchar(250)
		time_wash2_start_roomtemp = NULL                         :   datetime
		wash2_start_roomtemp_notes = ""                          :   varchar(250)
		time_wash2_ptwh_wash1 = NULL                             :   datetime
		wash2_ptwh_wash1_notes = ""                              :   varchar(250)
		time_wash2_ptwh_wash2 = NULL                             :   datetime
		wash2_ptwh_wash2_notes = ""                              :   varchar(250)
		time_wash2_ptwh_wash3 = NULL                             :   datetime
		wash2_ptwh_wash3_notes = ""                              :   varchar(250)
		time_wash2_ptwh_wash4 = NULL                             :   datetime
		wash2_ptwh_wash4_notes = ""                              :   varchar(250)
		time_wash2_ptwh_wash5 = NULL                             :   datetime
		wash2_ptwh_wash5_notes = ""                              :   varchar(250)
		time_clearing_methanol_20percent_wash1 = NULL               :   datetime
		clearing_methanol_20percent_wash1_notes = ""                :   varchar(250)
		time_clearing_methanol_40percent_wash1 = NULL               :   datetime
		clearing_methanol_40percent_wash1_notes = ""                :   varchar(250)
		time_clearing_methanol_60percent_wash1 = NULL               :   datetime
		clearing_methanol_60percent_wash1_notes = ""                :   varchar(250)
		time_clearing_methanol_80percent_wash1 = NULL               :   datetime
		clearing_methanol_80percent_wash1_notes = ""                :   varchar(250)
		time_clearing_methanol_100percent_wash1 = NULL              :   datetime
		clearing_methanol_100percent_wash1_notes = ""               :   varchar(250)
		time_clearing_methanol_100percent_wash2 = NULL              :   datetime
		clearing_methanol_100percent_wash2_notes = ""               :   varchar(250)
		time_clearing_dcm_66percent_methanol_33percent = NULL       :   datetime
		clearing_dcm_66percent_methanol_33percent_notes = ""        :   varchar(250)
		time_clearing_dcm_wash1 = NULL                           :   datetime
		clearing_dcm_wash1_notes = ""                            :   varchar(250)
		time_clearing_dcm_wash2 = NULL                           :   datetime
		clearing_dcm_wash2_notes = ""                            :   varchar(250)
		time_clearing_dbe = NULL                                 :   datetime
		clearing_dbe_notes = ""                                  :   varchar(250)
		time_clearing_new_tubes = NULL                           :   datetime
		clearing_new_tubes_notes = ""                            :   varchar(250)
		clearing_notes = ""                                      :   varchar(500)
		"""

	class IdiscoAbbreviatedClearing(dj.Part): 
		definition = """ # iDISCO abbreviated clearing table
		-> Sample           
		----
		exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during experiment that could affect clearing
		time_pbs_wash1 = NULL                                    :   datetime
		pbs_wash1_notes = ""                                     :   varchar(250)
		time_pbs_wash2 = NULL                                    :   datetime
		pbs_wash2_notes = ""                                     :   varchar(250)
		time_pbs_wash3 = NULL                                    :   datetime
		pbs_wash3_notes = ""                                     :   varchar(250)
		time_dehydr_methanol_20percent_wash1 = NULL                 :   datetime
		dehydr_methanol_20percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_40percent_wash1 = NULL                 :   datetime
		dehydr_methanol_40percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_60percent_wash1 = NULL                 :   datetime
		dehydr_methanol_60percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_80percent_wash1 = NULL                 :   datetime
		dehydr_methanol_80percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_100percent_wash1 = NULL                :   datetime
		dehydr_methanol_100percent_wash1_notes = ""                 :   varchar(250)
		time_dehydr_methanol_100percent_wash2 = NULL                :   datetime
		dehydr_methanol_100percent_wash2_notes = ""                 :   varchar(250)
		time_dehydr_dcm_66percent_methanol_33percent = NULL         :   datetime
		dehydr_dcm_66percent_methanol_33percent_notes = ""          :   varchar(250)
		time_dehydr_dcm_wash1 = NULL                             :   datetime
		dehydr_dcm_wash1_notes = ""                              :   varchar(250)
		time_dehydr_dcm_wash2 = NULL                             :   datetime
		dehydr_dcm_wash2_notes = ""                              :   varchar(250)
		time_dehydr_dbe_wash1 = NULL                             :   datetime
		dehydr_dbe_wash1_notes = ""                              :   varchar(250)
		time_dehydr_dbe_wash2 = NULL                             :   datetime
		dehydr_dbe_wash2_notes = ""                              :   varchar(250)
		clearing_notes = ""                                      :   varchar(500)
		"""

	class IdiscoAbbreviatedRatClearing(dj.Part): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
		definition = """ # iDISCO Abbreviated Rat clearing table
		-> Sample              
		----
		exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during experiment that could affect clearing
		time_pbs_wash1 = NULL                                    :   datetime
		pbs_wash1_notes = ""                                     :   varchar(250)
		time_pbs_wash2 = NULL                                    :   datetime
		pbs_wash2_notes = ""                                     :   varchar(250)
		time_pbs_wash3 = NULL                                    :   datetime
		pbs_wash3_notes = ""                                     :   varchar(250)
		time_dehydr_methanol_20percent_wash1 = NULL                 :   datetime
		dehydr_methanol_20percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_20percent_wash2 = NULL                 :   datetime
		dehydr_methanol_20percent_wash2_notes = ""                  :   varchar(250)
		time_dehydr_methanol_40percent_wash1 = NULL                 :   datetime
		dehydr_methanol_40percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_40percent_wash2 = NULL                 :   datetime
		dehydr_methanol_40percent_wash2_notes = ""                  :   varchar(250)
		time_dehydr_methanol_60percent_wash1 = NULL                 :   datetime
		dehydr_methanol_60percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_80percent_wash1 = NULL                 :   datetime
		dehydr_methanol_80percent_wash1_notes = ""                  :   varchar(250)
		time_dehydr_methanol_80percent_wash2 = NULL                 :   datetime
		dehydr_methanol_80percent_wash2_notes = ""                  :   varchar(250)
		time_dehydr_methanol_100percent_wash1 = NULL                :   datetime
		dehydr_methanol_100percent_wash1_notes = ""                 :   varchar(250)
		time_dehydr_methanol_100percent_wash2 = NULL                :   datetime
		dehydr_methanol_100percent_wash2_notes = ""                 :   varchar(250)
		time_dehydr_h202_wash1 = NULL                            :   datetime
		dehydr_h202_wash1_notes = ""                             :   varchar(250)
		time_dehydr_methanol_100percent_wash3 = NULL                :   datetime
		dehydr_methanol_100percent_wash3_notes = ""                 :   varchar(250)
		time_dehydr_methanol_100percent_wash4 = NULL                :   datetime
		dehydr_methanol_100percent_wash4_notes = ""                 :   varchar(250)
		time_dehydr_methanol_100percent_wash5 = NULL                :   datetime
		dehydr_methanol_100percent_wash5_notes = ""                 :   varchar(250)
		time_dehydr_dcm_66percent_methanol_33percent = NULL         :   datetime
		dehydr_dcm_66percent_methanol_33percent_notes = ""          :   varchar(250)
		time_dehydr_dcm_wash1 = NULL                             :   datetime
		dehydr_dcm_wash1_notes = ""                              :   varchar(250)
		time_dehydr_dcm_wash2 = NULL                             :   datetime
		dehydr_dcm_wash2_notes = ""                              :   varchar(250)
		time_dehydr_dbe_wash1 = NULL                             :   datetime
		dehydr_dbe_wash1_notes = ""                              :   varchar(250)
		time_dehydr_dbe_wash2 = NULL                             :   datetime
		dehydr_dbe_wash2_notes = ""                              :   varchar(250)
		clearing_notes = ""                                      : varchar(500)
		"""

	class UdiscoClearing(dj.Part): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
		definition = """ # uDISCO clearing table
		-> Sample              
		----
		exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during experiment that could affect clearing
		time_dehydr_pbs_wash1 = NULL                             :   datetime
		dehydr_pbs_wash1_notes = ""                              :   varchar(250)
		time_dehydr_butanol_30percent = NULL                     :   datetime
		dehydr_butanol_30percent_notes = ""                      :   varchar(250)
		time_dehydr_butanol_50percent = NULL                     :   datetime
		dehydr_butanol_50percent_notes = ""                      :   varchar(250)
		time_dehydr_butanol_70percent = NULL                     :   datetime
		dehydr_butanol_70percent_notes = ""                      :   varchar(250)
		time_dehydr_butanol_80percent = NULL                     :   datetime
		dehydr_butanol_80percent_notes = ""                      :   varchar(250)
		time_dehydr_butanol_90percent = NULL                     :   datetime
		dehydr_butanol_90percent_notes = ""                      :   varchar(250)
		time_dehydr_butanol_96percent = NULL                     :   datetime
		dehydr_butanol_96percent_notes = ""                      :   varchar(250)
		time_dehydr_butanol_100percent = NULL                    :   datetime
		dehydr_butanol_100percent_notes = ""                     :   varchar(250)
		time_clearing_dcm_wash1 = NULL                           :   datetime
		clearing_dcm_wash1_notes = ""                            :   varchar(250)
		time_clearing_babb_wash1 = NULL                          :   datetime
		clearing_babb_wash1_notes = ""                           :   varchar(250)
		clearing_notes = ""                                      : varchar(500)
		"""

	class IdiscoEdUClearing(dj.Part): # dj.Manual is one of the 4 datajoint table types - Manual corresponds to externally inputted data
		definition = """ # uDISCO clearing table
		-> Sample              
		----
		exp_notes = ""                                           :   varchar(500)  # Note anything unusual that happened during experiment that could affect clearing
		time_dehydr_pbs_wash1 = NULL                             :   datetime
		dehydr_pbs_wash1_notes = ""                              :   varchar(250)
		time_dehydr_pbs_wash2 = NULL                             :   datetime
		dehydr_pbs_wash2_notes = ""                              :   varchar(250)
		time_dehydr_pbs_wash3 = NULL                             :   datetime
		dehydr_pbs_wash3_notes = ""                              :   varchar(250)

		time_dehydr_methanol_20percent_wash1 = NULL              :   datetime
		dehydr_methanol_20percent_wash1_notes = ""               :   varchar(250)
		time_dehydr_methanol_40percent_wash1 = NULL              :   datetime
		dehydr_methanol_40percent_wash1_notes = ""               :   varchar(250)
		time_dehydr_methanol_60percent_wash1 = NULL              :   datetime
		dehydr_methanol_60percent_wash1_notes = ""               :   varchar(250)
		time_dehydr_methanol_80percent_wash1 = NULL              :   datetime
		dehydr_methanol_80percent_wash1_notes = ""               :   varchar(250)
		time_dehydr_methanol_100percent_wash1 = NULL             :   datetime
		dehydr_methanol_100percent_wash1_notes = ""              :   varchar(250)
		time_dehydr_methanol_100percent_wash2 = NULL             :   datetime
		dehydr_methanol_100percent_wash2_notes = ""              :   varchar(250)
		
		time_dehydr_h202_wash1 = NULL                            :   datetime
		dehydr_h202_wash1_notes = ""                             :   varchar(250)
		time_rehydr_methanol_100percent_wash1 = NULL             :   datetime
		rehydr_methanol_100percent_wash1_notes = ""              :   varchar(250)
		time_rehydr_methanol_80percent_wash1 = NULL              :   datetime
		rehydr_methanol_80percent_wash1_notes = ""               :   varchar(250)
		time_rehydr_methanol_60percent_wash1 = NULL              :   datetime
		rehydr_methanol_60percent_wash1_notes = ""               :   varchar(250)
		time_rehydr_methanol_40percent_wash1 = NULL              :   datetime
		rehydr_methanol_40percent_wash1_notes = ""               :   varchar(250)
		time_rehydr_methanol_20percent_wash1 = NULL              :   datetime
		rehydr_methanol_20percent_wash1_notes = ""               :   varchar(250)
		
		time_rehydr_pbs_wash1 = NULL                             :   datetime
		rehydr_pbs_wash1_notes = ""                              :   varchar(250)
		time_rehydr_sodium_azide_wash1 = NULL                    :   datetime
		rehydr_sodium_azide_wash1_notes = ""                     :   varchar(250)
		time_rehydr_sodium_azide_wash2 = NULL                    :   datetime
		rehydr_sodium_azide_wash2_notes = ""                     :   varchar(250)
		time_rehydr_glycine_wash1 = NULL                         :   datetime
		rehydr_glycine_wash1_notes = ""                          :   varchar(250)
		
		time_wash1_start_roomtemp = NULL                         :   datetime
		wash1_start_roomtemp_notes = ""                          :   varchar(250)
		time_wash1_ptwh_wash1 = NULL                             :   datetime
		wash1_ptwh_wash1_notes = ""                              :   varchar(250)
		time_wash1_ptwh_wash2 = NULL                             :   datetime
		wash1_ptwh_wash2_notes = ""                              :   varchar(250)
		time_wash1_ptwh_wash3 = NULL                             :   datetime
		wash1_ptwh_wash3_notes = ""                              :   varchar(250)
		time_wash1_ptwh_wash4 = NULL                             :   datetime
		wash1_ptwh_wash4_notes = ""                              :   varchar(250)
		time_wash1_ptwh_wash5 = NULL                             :   datetime
		wash1_ptwh_wash5_notes = ""                              :   varchar(250)

		time_edu_click_chemistry = NULL                          :   datetime
		edu_click_chemistry_notes = ""                           :   varchar(250)

		time_wash2_ptwh_wash1 = NULL                             :   datetime
		wash2_ptwh_wash1_notes = ""                              :   varchar(250)
		time_wash2_ptwh_wash2 = NULL                             :   datetime
		wash2_ptwh_wash2_notes = ""                              :   varchar(250)
		time_wash2_ptwh_wash3 = NULL                             :   datetime
		wash2_ptwh_wash3_notes = ""                              :   varchar(250)
		time_wash2_ptwh_wash4 = NULL                             :   datetime
		wash2_ptwh_wash4_notes = ""                              :   varchar(250)
		time_wash2_ptwh_wash5 = NULL                             :   datetime
		wash2_ptwh_wash5_notes = ""                              :   varchar(250)
		
		time_clearing_methanol_20percent_wash1 = NULL            :   datetime
		clearing_methanol_20percent_wash1_notes = ""             :   varchar(250)
		time_clearing_methanol_40percent_wash1 = NULL            :   datetime
		clearing_methanol_40percent_wash1_notes = ""             :   varchar(250)
		time_clearing_methanol_60percent_wash1 = NULL            :   datetime
		clearing_methanol_60percent_wash1_notes = ""             :   varchar(250)
		time_clearing_methanol_80percent_wash1 = NULL            :   datetime
		clearing_methanol_80percent_wash1_notes = ""             :   varchar(250)
		time_clearing_methanol_100percent_wash1 = NULL           :   datetime
		clearing_methanol_100percent_wash1_notes = ""            :   varchar(250)
		time_clearing_methanol_100percent_wash2 = NULL           :   datetime
		clearing_methanol_100percent_wash2_notes = ""            :   varchar(250)
		time_clearing_dcm_66percent_methanol_33percent = NULL    :   datetime
		clearing_dcm_66percent_methanol_33percent_notes = ""     :   varchar(250)
		time_clearing_dcm_wash1 = NULL                           :   datetime
		clearing_dcm_wash1_notes = ""                            :   varchar(250)
		time_clearing_dcm_wash2 = NULL                           :   datetime
		clearing_dcm_wash2_notes = ""                            :   varchar(250)
		time_clearing_dbe = NULL                                 :   datetime
		clearing_dbe_notes = ""                                  :   varchar(250)
		time_clearing_new_tubes = NULL                           :   datetime
		clearing_new_tubes_notes = ""                            :   varchar(250)
		clearing_notes = ""                                      : varchar(500)
		"""


class RawImageSet(dj.Manual):
	definition = """ # a set of raw images for a given experiment and channel
	-> Sample
	channel                      :   char(3)
	----
	-> User
	imager                       :   varchar(20) # netid of the person who did the imaging
	numerical_aperture           :   float
	exp_time                     :   smallint
	image_resolution             :   enum("1.3x","4x")
	foci                         :   varchar(50)
	tiled                        :   boolean # 1 for yes, 0 for no
	purpose                      :   varchar(255)
	notes = ""                   :   varchar(1000)
	"""  

class ImageProcessing(dj.Manual):
	definition = """ # Image Processing metadata for a run through the pipeline
	-> RawImageSet
	----
	-> User
	output_directory             :   varchar(255) # root of output directory path on bucket
	processor                    :   varchar(20) # netid of the person who started the image processing
	spatial_scale                :   float
	z_scale                      :   float
	stitchingmethod              :   enum("blending")
	blendtype                    :   enum("sigmoidal","flat")
	atlas_name                   :   enum("allen_2017","allen_2011","princeton_mouse_atlas")
	atlas_file                   :   varchar(255) # path on bucket
	annotation_file              :   varchar(255) # path on bucket
	tiling_overlap = 0.0         :   float
	intensity_correction         :   boolean
	rawdata_dir                  :   varchar(255) # path on bucket
	resizefactor                 :   tinyint
	slurmjobfactor               :   tinyint
	parameter_folder             :   varchar(255) # path on bucket to affine/spline parameters
	imspector_version            :   varchar(64)
	"""  


