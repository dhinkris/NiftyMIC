## \file N4BiasFieldCorrection.py
#  \brief N4 bias field correction according to the file
#  runN4BiasFieldCorrectionImageFilter.cpp in src/cpp/source
#
#  \author Michael Ebner (michael.ebner.14@ucl.ac.uk)
#  \date May 2017


## Import libraries
import os
import sys
import itk
import SimpleITK as sitk
import numpy as np

## Import modules
import base.Stack as st
import utilities.SimpleITKHelper as sitkh
import utilities.PythonHelper as ph

from definitions import dir_build_cpp
from definitions import dir_tmp

##
# Class implementing the segmentation propagation from one image to another
# \date       2017-05-10 23:48:08+0100
#
class N4BiasFieldCorrection(object):

    def __init__(self, stack=None, dir_tmp=os.path.join(dir_tmp, "N4BiasFieldCorrection"), use_mask=True, use_verbose=False):

        self._stack = stack
        self._use_mask = use_mask
        self._use_verbose = use_verbose

        self._stack_corrected = None

        ## Directory where temporary files are written
        self._dir_tmp = ph.create_directory(dir_tmp, delete_files=False)


    def set_stack(self, stack):
        self._stack = stack

    def get_bias_field_corrected_stack(self):
        return self._stack_corrected


    def run_bias_field_correction(self):

        ## Clean output directory first
        ph.clear_directory(self._dir_tmp)

        filename_out = self._stack.get_filename()

        sitk.WriteImage(self._stack.sitk, self._dir_tmp + filename_out + ".nii.gz")

        if self._use_mask:
            sitk.WriteImage(self._stack.sitk_mask, self._dir_tmp + filename_out + "_mask.nii.gz")


        cmd =  dir_build_cpp + "/bin/runN4BiasFieldCorrectionImageFilter "
        cmd += "--f " + self._dir_tmp + filename_out + " "
        if self._use_mask:
            cmd += "--fmask " + self._dir_tmp + filename_out + "_mask "
        cmd += "--tout " + self._dir_tmp + " "
        cmd += "--m " + filename_out

        ph.execute_command(cmd)

        stack_corrected_sitk = sitk.ReadImage(self._dir_tmp + filename_out + "_corrected.nii.gz", sitk.sitkFloat64)

        ## Reading of image might lead to slight differences 
        stack_corrected_sitk_mask = sitk.Resample(self._stack.sitk_mask, stack_corrected_sitk, sitk.Euler3DTransform(), sitk.sitkNearestNeighbor, 0, self._stack.sitk_mask.GetPixelIDValue())
        

        # stack_corrected = st.Stack.from_sitk_image(stack_corrected_sitk, self._stack.get_filename(), self._stack.sitk_mask)
        self._stack_corrected = st.Stack.from_sitk_image(stack_corrected_sitk, self._stack.get_filename(), stack_corrected_sitk_mask)

        ## Debug
        # sitkh.show_stacks([self._stack, self._stack_corrected], label=["orig", "corr"])