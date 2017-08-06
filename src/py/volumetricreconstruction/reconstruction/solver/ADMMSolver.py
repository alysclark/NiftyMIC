#!/usr/bin/python

# \file ADMMSolver.py
#  \brief Implementation to get an approximate solution of the inverse problem
#  \f$ y_k = A_k x \f$ for each slice \f$ y_k,\,k=1,\dots,K \f$
#  by using TV-L2-regularization.
#  Solution via Alternating Direction Method of Multipliers (ADMM) method.
#
#  \author Michael Ebner (michael.ebner.14@ucl.ac.uk)
#  \date July 2016

# Import libraries
import os
import sys
import itk
import SimpleITK as sitk
import numpy as np
import time

import numericalsolver.ADMMLinearSolver as admm
import numericalsolver.LinearOperators as linop
import pythonhelper.SimpleITKHelper as sitkh
import pythonhelper.PythonHelper as ph

# Import modules
from volumetricreconstruction.reconstruction.solver.Solver import Solver


# This class implements the framework to iteratively solve
#  \f$ \vec{y}_k = A_k \vec{x} \f$ for every slice \f$ \vec{y}_k,\,k=1,\dots,K \f$
#  via TV-L2-regularization via an augmented least-square approach
#  TODO
class ADMMSolver(Solver):

    ##
    # Constructor
    # \date          2016-08-01 22:57:21+0100
    #
    # \param         self                   The object
    # \param[in]     stacks                 list of Stack objects containing
    #                                       all stacks used for the
    #                                       reconstruction
    # \param[in,out] reconstruction         Stack object containing the current
    #                                       estimate of the reconstruction
    #                                       volume (used as initial value +
    #                                       space definition)
    # \param[in]     alpha_cut              Cut-off distance for Gaussian
    #                                       blurring filter
    # \param[in]     alpha                  regularization parameter, scalar
    # \param[in]     iter_max               number of maximum iterations,
    #                                       scalar
    # \param         minimizer              The minimizer
    # \param         deconvolution_mode     The deconvolution mode
    # \param         predefined_covariance  The predefined covariance
    # \param[in]     rho                    regularization parameter of
    #                                       augmented Lagrangian term, scalar
    # \param[in]     iterations             number of ADMM iterations, scalar
    # \param         verbose                The verbose
    #
    def __init__(self,
                 stacks,
                 reconstruction,
                 alpha_cut=3,
                 alpha=0.03,
                 iter_max=10,
                 minimizer="lsmr",
                 deconvolution_mode="full_3D",
                 predefined_covariance=None,
                 rho=0.5,
                 iterations=10,
                 verbose=0,
                 ):

        # Run constructor of superclass
        Solver.__init__(self,
                        stacks=stacks,
                        reconstruction=reconstruction,
                        alpha_cut=alpha_cut,
                        alpha=alpha,
                        iter_max=iter_max,
                        minimizer=minimizer,
                        deconvolution_mode=deconvolution_mode,
                        predefined_covariance=predefined_covariance,
                        verbose=verbose,
                        )

        # Settings for optimizer
        self._rho = rho
        self._iterations = iterations

    # Set regularization parameter used for augmented Lagrangian in TV-L2 regularization
    #  \[$
    #   \sum_{k=1}^K \frac{1}{2} \Vert y_k - A_k x \Vert_{\ell^2}^2 + \alpha\,\Psi(x)
    #   + \mu \cdot (\nabla x - v) + \frac{\rho}{2} \Vert \nabla x - v \Vert_{\ell^2}^2
    #  \]$
    #  \param[in] rho regularization parameter of augmented Lagrangian term, scalar
    def set_rho(self, rho):
        self._rho = rho

    # Get regularization parameter used for augmented Lagrangian in TV-L2 regularization
    #  \return regularization parameter of augmented Lagrangian term, scalar
    def get_rho(self):
        return self._rho

    # Set ADMM iterations to solve TV-L2 reconstruction problem
    #  \[$
    #   \sum_{k=1}^K \frac{1}{2} \Vert y_k - A_k x \Vert_{\ell^2}^2 + \alpha\,\Psi(x)
    #   + \mu \cdot (\nabla x - v) + \frac{\rho}{2} \Vert \nabla x - v \Vert_{\ell^2}^2
    #  \]$
    #  \param[in] iterations number of ADMM iterations, scalar
    def set_iterations(self, iterations):
        self._iterations = iterations

    # Get chosen value of ADMM iterations to solve TV-L2 reconstruction problem
    #  \return number of ADMM iterations, scalar
    def get_iterations(self):
        return self._iterations

    # Compute statistics associated to performed reconstruction
    def compute_statistics(self):
        reconstruction_nda_vec = sitk.GetArrayFromImage(
            self._reconstruction.sitk).flatten()

        self._residual_ell2 = self._get_residual_ell2(reconstruction_nda_vec)
        # self._residual_prior = self._get_residual_prior(reconstruction_nda_vec)

    ##
    #       Gets the setting specific filename indicating the information
    #             used for the reconstruction step
    # \date       2016-11-17 15:41:58+0000
    #
    # \param      self    The object
    # \param      prefix  The prefix as string
    #
    # \return     The setting specific filename as string.
    #
    def get_setting_specific_filename(self, prefix="SRR_"):

        # Build filename
        filename = prefix
        filename += "stacks" + str(len(self._stacks))
        if self._alpha > 0:
            filename += "_ADMM"
            filename += "_TV"
        filename += "_" + self._minimizer
        filename += "_alpha" + str(self._alpha)
        filename += "_itermax" + str(self._iter_max)
        filename += "_rho" + str(self._rho)
        filename += "_ADMMiterations" + str(self._iterations)

        # Replace dots by 'p'
        filename = filename.replace(".", "p")

        return filename

    ##
    #       Reconstruct volume using TV-L2 regularization via Alternating
    #             Direction Method of Multipliers (ADMM) method.
    # \post       self._reconstruction is updated with new volume and can be fetched
    #             via \p get_recon
    # \date       2016-08-01 23:22:50+0100
    #
    # \param      self                    The object
    # \param      estimate_initial_value  Estimate initial value by running one
    #                                     first-order Tikhonov reconstruction
    #                                     step prior the ADMM algorithm
    #
    def _run_reconstruction(self):

        self._print_info_text()

        # Get operators
        A = self.get_A()
        A_adj = self.get_A_adj()
        b = self.get_b()
        x0 = self.get_x0()
        x_scale = x0.max()

        spacing = np.array(self._reconstruction.sitk.GetSpacing())
        linear_operators = linop.LinearOperators3D(spacing=spacing)
        grad, grad_adj = linear_operators.get_gradient_operators()

        X_shape = self._reconstruction_shape
        Z_shape = grad(x0.reshape(*X_shape)).shape

        B = lambda x: grad(x.reshape(*X_shape)).flatten()
        B_adj = lambda x: grad_adj(x.reshape(*Z_shape)).flatten()

        # Run reconstruction
        solver = admm.ADMMLinearSolver(
            dimension=3,
            A=A, A_adj=A_adj,
            B=B, B_adj=B_adj,
            b=b,
            x0=x0,
            x_scale=x_scale,
            alpha=self._alpha,
            data_loss="linear",
            minimizer="lsmr",
            iter_max=self._iter_max,
            rho=self._rho,
            iterations=self._iterations,
            verbose=self._verbose,
        )
        solver.run()

        # Get computational time
        self._computational_time = solver.get_computational_time()

        # Update volume
        self._reconstruction.itk = self._get_itk_image_from_array_vec(
            solver.get_x(), self._reconstruction.itk)
        self._reconstruction.sitk = sitkh.get_sitk_from_itk_image(
            self._reconstruction.itk)

    def _print_info_text(self):
        ph.print_title("ADMM Solver:")
        ph.print_info("Chosen regularization type: TV")
        ph.print_info("Regularization parameter alpha: " + str(self._alpha))
        ph.print_info(
            "Regularization parameter of augmented Lagrangian term rho: " + str(self._rho))
        ph.print_info("Number of ADMM iterations: " + str(self._iterations))
        ph.print_info(
            "Maximum number of TK1 solver iterations: " + str(self._iter_max))
        # ph.print_info("Tolerance: %.0e" %(self._tolerance))
