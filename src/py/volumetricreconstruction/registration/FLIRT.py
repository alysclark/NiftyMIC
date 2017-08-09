# \file FLIRT.py
# \brief      Class to use registration method FLIRT
#
# \author     Michael Ebner (michael.ebner.14@ucl.ac.uk)
# \date       Aug 2017


# Import libraries
import os
import numpy as np
import SimpleITK as sitk

import pythonhelper.PythonHelper as ph
import registrationtools.FLIRT

import volumetricreconstruction.base.Stack as st
from volumetricreconstruction.registration.RegistrationMethod \
    import AffineRegistrationMethod


##
# Class to use registration method FLIRT
# \date       2017-08-09 11:22:33+0100
#
class FLIRT(AffineRegistrationMethod):

    def __init__(self,
                 fixed=None,
                 moving=None,
                 use_fixed_mask=False,
                 use_moving_mask=False,
                 use_verbose=False,
                 registration_type="Rigid",
                 options="",
                 ):

        AffineRegistrationMethod.__init__(self,
                                          fixed=fixed,
                                          moving=moving,
                                          use_fixed_mask=use_fixed_mask,
                                          use_moving_mask=use_moving_mask,
                                          use_verbose=use_verbose,
                                          registration_type=registration_type,
                                          )

        self._options = options

    ##
    # Sets the registration type.
    # \date       2017-02-02 16:42:13+0000
    #
    # \param      self               The object
    # \param      registration_type  The registration type
    #
    def set_registration_type(self, registration_type):
        if registration_type not in ["Rigid", "Affine"]:
            raise ValueError("Error: Registration type not possible")
        self._registration_type = registration_type

    ##
    # Gets the registration type.
    # \date       2017-08-08 19:58:30+0100
    #
    # \param      self  The object
    #
    # \return     The registration type as string.
    #
    def get_registration_type(self):
        return self._registration_type

    ##
    # Sets the options used for FLIRT
    # \date       2017-08-08 19:57:47+0100
    #
    # \param      self     The object
    # \param      options  The options as string
    #
    def set_options(self, options):
        self._options = options

    ##
    # Gets the options.
    # \date       2017-08-08 19:58:14+0100
    #
    # \param      self  The object
    #
    # \return     The options as string.
    #
    def get_options(self):
        return self._options

    def _run_registration(self):

        if self._use_fixed_mask:
            fixed_sitk_mask = self._fixed.sitk_mask
        else:
            fixed_sitk_mask = None

        if self._use_moving_mask:
            moving_sitk_mask = self._moving.sitk_mask
        else:
            moving_sitk_mask = None

        options = self._options
        if self._registration_type == "Rigid":
            options += " -dof 6"

        elif self._registration_type == "Affine":
            options += " -dof 12"

        if self._use_verbose:
            options += " -verbose 1"

        self._registration_method = registrationtools.FLIRT.FLIRT(
            fixed_sitk=self._fixed.sitk,
            moving_sitk=self._moving.sitk,
            fixed_sitk_mask=fixed_sitk_mask,
            moving_sitk_mask=moving_sitk_mask,
            options=options
        )
        self._registration_method.run()

        self._registration_transform_sitk = \
            self._registration_method.get_registration_transform_sitk()
