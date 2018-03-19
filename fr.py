#! /usr/bin/env python
# author : S. Mandalia
#          s.p.mandalia@qmul.ac.uk
#
# date   : March 17, 2018

"""
HESE BSM flavour ratio analysis script
"""

from __future__ import absolute_import, division

import argparse
from functools import partial

import numpy as np

from utils import mcmc as mcmc_utils
from utils import misc as misc_utils
from utils.fr import MASS_EIGENVALUES, normalise_fr
from utils.gf import gf_argparse
from utils.misc import Param, ParamSet

import chainer_plot


def define_nuisance():
    """Define the nuisance parameters to scan over with default values,
    ranges and sigma.
    """
    nuisance = ParamSet(
        Param(name='convNorm'       , value=1. , ranges=[0., 5.], std=0.3),
        Param(name='promptNorm'     , value=0. , ranges=[0., 5.], std=0.05),
        Param(name='muonNorm'       , value=1. , ranges=[0., 5.], std=0.1),
        Param(name='astroNorm'      , value=1. , ranges=[0., 5.], std=0.1),
        Param(name='astroDeltaGamma', value=2. , ranges=[0., 5.], std=0.1)
    )
    return nuisance


def nuisance_argparse(parser):
    nuisance_paramset = define_nuisance()
    for parm in nuisance_paramset:
        parser.add_argument(
            '--'+parm.name, type=float, default=parm.value,
            help=parm.name+' to inject'
        )


def get_paramsets(args):
    """Make the paramsets for generating the Asmimov MC sample and also running
    the MCMC.
    """
    nuisance_paramset = define_nuisance()
    for parm in nuisance_paramset:
        parm.value = args.__getattribute__(parm.name)
    asimov_paramset = ParamSet(
        nuisance_paramset.params +
        [Param(name='astroENorm'     , value=args.measured_ratio[0], ranges=[0., 1.], std=0.2),
         Param(name='astroMuNorm'    , value=args.measured_ratio[1], ranges=[0., 1.], std=0.2),
         Param(name='astroTauNorm'   , value=args.measured_ratio[2], ranges=[0., 1.], std=0.2)]
    )

    mcmc_paramset = []
    if not args.fix_mixing:
        mcmc_paramset.extend([
            Param(name='s_12^2', value=0.5, ranges=[0., 1.], std=0.2, tex=r'\tilde{s}_{12}^2'),
            Param(name='c_13^4', value=0.5, ranges=[0., 1.], std=0.2, tex=r'\tilde{c}_{13}^4'),
            Param(name='s_23^2', value=0.5, ranges=[0., 1.], std=0.2, tex=r'\tilde{s}_{23}^4'),
            Param(name='dcp', value=np.pi, ranges=[0., 2*np.pi], std=0.2, tex=r'\tilde{\delta_{CP}}')
        ])
    if not args.fix_scale:
        logLam, scale_region = np.log10(args.scale), np.log10(args.scale_region)
        lL_range = (logLam-scale_region, logLam+scale_region)
        mcmc_paramset.append(
            Param(name='logLam', value=logLam, ranges=lL_range, std=3, tex=r'{\rm log}_{10}\Lambda')
        )
    if not args.fix_source_ratio:
        mcmc_paramset.extend([
            Param(name='s_phi4', value=0.5, ranges=[0., 1.], std=0.2, tex=r'sin^4(\phi)'),
            Param(name='c_2psi', value=0.5, ranges=[0., 1.], std=0.2, tex=r'cos(2\psi)')
        ])
    mcmc_paramset = ParamSet(nuisance_paramset.params + mcmc_paramset)
    return nuisance_paramset, mcmc_paramset


def process_args(args):
    """Process the input args."""
    if args.fix_mixing and args.fix_source_ratio:
        raise NotImplementedError('Fixed mixing and sfr not implemented')
    if args.fix_mixing and args.fix_scale:
        raise NotImplementedError('Fixed mixing and scale not implemented')

    args.measured_ratio = normalise_fr(args.measured_ratio)
    if args.fix_source_ratio:
        args.source_ratio = normalise_fr(args.source_ratio)

    if not args.fix_scale:
        args.scale = np.power(
            10, np.round(np.log10(MASS_EIGENVALUES[1]/args.energy)) - \
            np.log10(args.energy**(args.dimension-3))
        )
        """Estimate the scale of when to expect the BSM term to contribute."""


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="BSM flavour ratio analysis")
    parser.add_argument(
        '--measured-ratio', type=int, nargs=3, default=[1, 1, 1],
        help='Set the central value for the measured flavour ratio at IceCube'
    )
    parser.add_argument(
        '--sigma-ratio', type=float, default=0.01,
        help='Set the 1 sigma for the measured flavour ratio for a gaussian LLH'
    )
    parser.add_argument(
        '--fix-source-ratio', type=misc_utils.parse_bool, default='False',
        help='Fix the source flavour ratio'
    )
    parser.add_argument(
        '--source-ratio', type=int, nargs=3, default=[2, 1, 0],
        help='Set the source flavour ratio for the case when you want to fix it'
    )
    parser.add_argument(
        '--no-bsm', type=misc_utils.parse_bool, default='False',
        help='Turn off BSM terms'
    )
    parser.add_argument(
        '--fix-mixing', type=misc_utils.parse_bool, default='False',
        help='Fix all mixing parameters except one'
    )
    parser.add_argument(
        '--fix-scale', type=misc_utils.parse_bool, default='False',
        help='Fix the new physics scale'
    )
    parser.add_argument(
        '--scale', type=float, default=1e-30,
        help='Set the new physics scale'
    )
    parser.add_argument(
        '--scale-region', type=float, default=1e10,
        help='Set the size of the box to scan for the scale'
    )
    parser.add_argument(
        '--dimension', type=int, default=3,
        help='Set the new physics dimension to consider'
    )
    parser.add_argument(
        '--energy', type=float, default=1000,
        help='Set the energy scale'
    )
    parser.add_argument(
        '--seed', type=int, default=99,
        help='Set the random seed value'
    )
    parser.add_argument(
        '--threads', type=misc_utils.thread_type, default='1',
        help='Set the number of threads to use (int or "max")'
    )
    parser.add_argument(
        '--outfile', type=str, default='./untitled',
        help='Path to output chains'
    )
    nuisance_argparse(parser)
    gf_argparse(parser)
    mcmc_utils.mcmc_argparse(parser)
    return parser.parse_args()


def main():
    args = parse_args()
    process_args(args)
    misc_utils.print_args(args)

    np.random.seed(args.seed)

    asmimov_paramset, mcmc_paramset = get_paramsets(args)
    outfile = misc_utils.gen_outfile_name(args)
    print '== {0:<25} = {1}'.format('outfile', outfile)

    if args.run_mcmc:
        triangle_llh = partial(
            mcmc_utils.triangle_llh, args=args
        )
        lnprior = partial(
            mcmc_utils.lnprior, paramset=mcmc_paramset
        )

        ndim = len(mcmc_paramset)
        ntemps=1
        p0 = mcmc_utils.gaussian_seed(
            mcmc_paramset, ntemps=ntemps, nwalkers=args.nwalkers
        )

        samples = mcmc_utils.mcmc(
            p0           = p0,
            triangle_llh = triangle_llh,
            lnprior      = lnprior,
            ndim         = ndim,
            nwalkers     = args.nwalkers,
            burnin       = args.burnin,
            nsteps       = args.nsteps,
            ntemps       = ntemps,
            threads      = args.threads
        )
        mcmc_utils.save_chains(samples, outfile)

    scale_bounds = (args.scale/args.scale_region, args.scale*args.scale_region)
    print "Making triangle plots"
    chainer_plot.plot(
        infile         = outfile+'.npy',
        angles         = True,
        outfile        = outfile[:5]+outfile[5:].replace('data', 'plots')+'_angles.pdf',
        measured_ratio = args.measured_ratio,
        sigma_ratio    = args.sigma_ratio,
        fix_sfr        = args.fix_source_ratio,
        fix_mixing     = args.fix_mixing,
        fix_scale      = args.fix_scale,
        source_ratio   = args.source_ratio,
        scale          = args.scale,
	dimension      = args.dimension,
	energy         = args.energy,
	scale_bounds   = scale_bounds,
    )
    # chainer_plot.plot(
    #     infile=outfile+'.npy',
    #     angles=False,
    #     outfile=outfile[:5]+outfile[5:].replace('data', 'plots')+'.pdf',
    #     measured_ratio=args.measured_ratio,
    #     sigma_ratio=args.sigma_ratio,
    #     fix_sfr=args.fix_source_ratio,
    #     fix_mixing=args.fix_mixing,
    #     fix_scale=FIX_SCALE,
    #     source_ratio=args.source_ratio,
    #     scale=args.scale,
    #     dimension=args.dimension,
    #     energy=args.energy,
    #     scale_bounds=scale_bounds,
    # )
    print "DONE!"


main.__doc__ = __doc__


if __name__ == '__main__':
    main()

