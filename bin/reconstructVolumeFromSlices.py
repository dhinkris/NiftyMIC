#!/usr/bin/python

##
# \file reconstructVolume.py
# \brief      Script to reconstruct an isotropic, high-resolution volume from
#             multiple stacks of low-resolution 2D slices including
#             motion-correction.
#
# \author     Michael Ebner (michael.ebner.14@ucl.ac.uk)
# \date       March 2016
#

# Import libraries
import SimpleITK as sitk
import argparse
import numpy as np
import sys
import os

import pythonhelper.PythonHelper as ph
import pythonhelper.SimpleITKHelper as sitkh

# Import modules
import volumetricreconstruction.base.DataReader as dr
import volumetricreconstruction.base.Stack as st
import volumetricreconstruction.reconstruction.solver.TikhonovSolver as tk
import volumetricreconstruction.reconstruction.solver.ADMMSolver as admm
import volumetricreconstruction.reconstruction.solver.PrimalDualSolver as pd
from volumetricreconstruction.utilities.InputArparser import InputArgparser


if __name__ == '__main__':

    time_start = ph.start_timing()

    # Set print options for numpy
    np.set_printoptions(precision=3)

    # Read input
    input_parser = InputArgparser(
        description="Volumetric MRI reconstruction framework to reconstruct "
        "an isotropic, high-resolution 3D volume from multiple stacks of "
        "motion corrected slices obtained by 'reconstructVolume.py'.",
        prog="python " + os.path.basename(__file__),
    )
    input_parser.add_dir_input()
    input_parser.add_filenames()
    input_parser.add_image_selection()
    input_parser.add_dir_output(default="results/")
    input_parser.add_suffix_mask(default="_mask")
    input_parser.add_target_stack_index(default=0)
    input_parser.add_extra_frame_target(default=10)
    input_parser.add_isotropic_resolution(default=None)
    input_parser.add_reconstruction_space(default=None)
    input_parser.add_minimizer(default="lsmr")
    input_parser.add_iter_max(default=10)
    input_parser.add_reg_type(default="TK1")
    input_parser.add_data_loss(default="linear")
    input_parser.add_data_loss_scale(default=1)
    input_parser.add_alpha(default=0.02)
    input_parser.add_rho(default=0.5)
    input_parser.add_tv_solver(default="PD")
    input_parser.add_pd_alg_type(default="ALG2")
    input_parser.add_iterations(default=10)
    input_parser.add_provide_comparison(default=1)
    input_parser.add_log_script_execution(default=1)
    input_parser.add_verbose(default=1)
    args = input_parser.parse_args()
    input_parser.print_arguments(args)

    # Write script execution call
    if args.log_script_execution:
        input_parser.write_performed_script_execution(
            os.path.abspath(__file__))

    # --------------------------------Read Data--------------------------------
    ph.print_title("Read Data")

    # Neither '--dir-input' nor '--filenames' was specified
    if args.filenames is not None and args.dir_input is not None:
        raise Exceptions.IOError(
            "Provide input by either '--dir-input' or '--filenames' "
            "but not both together")

    # '--dir-input' specified
    elif args.dir_input is not None:
        data_reader = dr.ImageSlicesDirectoryReader(
            path_to_directory=args.dir_input,
            suffix_mask=args.suffix_mask,
            image_selection=args.image_selection)

    # '--filenames' specified
    elif args.filenames is not None:
        data_reader = dr.MultipleImagesReader(
            args.filenames, suffix_mask=args.suffix_mask)

    else:
        raise Exceptions.IOError(
            "Provide input by either '--dir-input' or '--filenames'")

    data_reader.read_data()
    stacks = data_reader.get_stacks()

    # if args.verbose:
    #     sitkh.show_stacks(stacks, segmentation=stacks[0])

    if args.reconstruction_space is None:
        recon0 = stacks[args.target_stack_index
                        ].get_isotropically_resampled_stack(
            spacing_new_scalar=args.isotropic_resolution,
            extra_frame=args.extra_frame_target)
    else:
        recon0 = st.Stack.from_filename(args.reconstruction_space,
                                        extract_slices=False)
        recon0 = \
            stacks[args.target_stack_index].get_resampled_stack(recon0.sitk)

    SRR0 = tk.TikhonovSolver(
        stacks=stacks,
        reconstruction=recon0,
        alpha=args.alpha,
        iter_max=args.iter_max,
        reg_type="TK1",
        minimizer=args.minimizer,
        data_loss=args.data_loss,
        data_loss_scale=args.data_loss_scale,
        verbose=args.verbose,
    )
    SRR0.run_reconstruction()
    SRR0.compute_statistics()
    SRR0.print_statistics()

    recon = SRR0.get_reconstruction()
    recon.set_filename(SRR0.get_setting_specific_filename())
    recon.write(args.dir_output)

    # List to store SRRs
    recons = []
    for i in range(0, len(stacks)):
        recons.append(stacks[i])
    recons.insert(0, recon)

    if args.reg_type == "TV" and args.tv_solver == "ADMM":
        SRR = admm.ADMMSolver(
            stacks=stacks,
            reconstruction=st.Stack.from_stack(SRR0.get_reconstruction()),
            minimizer=args.minimizer,
            alpha=args.alpha,
            iter_max=args.iter_max,
            rho=args.rho,
            data_loss=args.data_loss,
            iterations=args.iterations,
            verbose=args.verbose,
        )
        SRR.run_reconstruction()
        SRR.print_statistics()
        recon = SRR.get_reconstruction()
        recon.set_filename(SRR.get_setting_specific_filename())
        recons.insert(0, recon)

        recon.write(args.dir_output)

    elif args.reg_type in ["TV", "huber"] and args.tv_solver == "PD":

        SRR = pd.PrimalDualSolver(
            stacks=stacks,
            reconstruction=st.Stack.from_stack(SRR0.get_reconstruction()),
            minimizer=args.minimizer,
            alpha=args.alpha,
            iter_max=args.iter_max,
            iterations=args.iterations,
            alg_type=args.pd_alg_type,
            reg_type=args.reg_type,
            data_loss=args.data_loss,
            verbose=args.verbose,
        )
        SRR.run_reconstruction()
        SRR.print_statistics()
        recon = SRR.get_reconstruction()
        recon.set_filename(SRR.get_setting_specific_filename())
        recons.insert(0, recon)

        recon.write(args.dir_output)

    if args.verbose and not args.provide_comparison:
        sitkh.show_stacks(recons)

    # Show SRR together with linearly resampled input data.
    # Additionally, a script is generated to open files
    if args.provide_comparison:
        sitkh.show_stacks(recons,
                          show_comparison_file=args.provide_comparison,
                          dir_output=os.path.join(
                              args.dir_output, "comparison"),
                          )

    ph.print_line_separator()
