# author : S. Mandalia
#          s.p.mandalia@qmul.ac.uk
#
# date   : April 04, 2018

"""
Likelihood functions for the BSM flavour ratio analysis
"""

from __future__ import absolute_import, division

from functools import partial

import numpy as np
from scipy.stats import multivariate_normal, rv_continuous

from utils import fr as fr_utils
from utils import gf as gf_utils
from utils.enums import EnergyDependance, Likelihood, ParamTag, PriorsCateg
from utils.misc import enum_parse, gen_identifier, parse_bool


class Gaussian(rv_continuous):
    """Gaussian for one dimension."""
    def _pdf(self, x, mu, sig):
        return (1./np.sqrt(2*np.pi*sig**2))*np.exp(-((x-mu)**2)/(2*sig**2))


def multi_gaussian(fr, fr_bf, sigma, offset=-320):
    """Multivariate gaussian likelihood."""
    cov_fr = np.identity(3) * sigma
    return np.log(multivariate_normal.pdf(fr, mean=fr_bf, cov=cov_fr)) + offset


def likelihood_argparse(parser):
    parser.add_argument(
        '--likelihood', default='gaussian', type=partial(enum_parse, c=Likelihood),
        choices=Likelihood, help='likelihood contour'
    )
    parser.add_argument(
        '--sigma-ratio', type=float, default=0.01,
        help='Set the 1 sigma for the measured flavour ratio for a gaussian LLH'
    )
    parser.add_argument(
        '--save-measured-fr', type=parse_bool, default='False',
        help='Output the measured flavour ratios'
    )
    parser.add_argument(
        '--output-measured-fr', type=str, default='./frs',
        help='Output of the measured flavour ratios'
    )


def lnprior(theta, paramset):
    """Priors on theta."""
    if len(theta) != len(paramset):
        raise AssertionError(
            'Length of MCMC scan is not the same as the input '
            'params\ntheta={0}\nparamset={1}'.format(theta, paramset)
        )
    for idx, param in enumerate(paramset):
        param.value = theta[idx]
    ranges = paramset.ranges
    for value, range in zip(theta, ranges):
        if range[0] <= value <= range[1]:
            pass
        else: return -np.inf

    prior = 0
    for param in paramset:
        if param.prior is PriorsCateg.GAUSSIAN:
            prior += Gaussian().logpdf(
                param.nominal_value, param.value, param.std
            )
        elif param.prior is PriorsCateg.HALFGAUSS:
            prior += Gaussian().logpdf(
                param.nominal_value, param.value, param.std
            ) + Gaussian().logcdf(1, param.value, param.std)
    return prior


def triangle_llh(theta, args, asimov_paramset, llh_paramset, fitter):
    """Log likelihood function for a given theta."""
    if len(theta) != len(llh_paramset):
        raise AssertionError(
            'Length of MCMC scan is not the same as the input '
            'params\ntheta={0}\nparamset]{1}'.format(theta, llh_paramset)
        )
    for idx, param in enumerate(llh_paramset):
        param.value = theta[idx]
    hypo_paramset = asimov_paramset
    for param in llh_paramset.from_tag(ParamTag.NUISANCE):
        hypo_paramset[param.name].value = param.value

    if args.energy_dependance is EnergyDependance.SPECTRAL:
        bin_centers = np.sqrt(args.binning[:-1]*args.binning[1:])
        bin_width = np.abs(np.diff(args.binning))
        if args.likelihood in [Likelihood.GOLEMFIT, Likelihood.GF_FREQ] \
           and args.fold_index:
            args.spectral_index = -hypo_paramset['astroDeltaGamma'].value

    if args.fix_source_ratio:
        if args.energy_dependance is EnergyDependance.MONO:
            source_flux = args.source_ratio
        elif args.energy_dependance is EnergyDependance.SPECTRAL:
            source_flux = np.array(
                [fr * np.power(bin_centers, args.spectral_index)
                 for fr in args.source_ratio]
            ).T
    else:
        if args.energy_dependance is EnergyDependance.MONO:
            source_flux = fr_utils.angles_to_fr(
                llh_paramset.from_tag(ParamTag.SRCANGLES, values=True)
            )
        elif args.energy_dependance is EnergyDependance.SPECTRAL:
            source_flux = np.array(
                [fr * np.power(bin_centers, args.spectral_index)
                 for fr in fr_utils.angles_to_fr(theta[-2:])]
            ).T

    bsm_angles = llh_paramset.from_tag(
        [ParamTag.SCALE, ParamTag.MMANGLES], values=True
    )

    m_eig_names = ['m21_2', 'm3x_2']
    ma_names = ['s_12_2', 'c_13_4', 's_23_2', 'dcp']

    if set(m_eig_names+ma_names).issubset(set(llh_paramset.names)):
        mass_eigenvalues = [x.value for x in llh_paramset if x.name in m_eig_names]
        sm_u = fr_utils.angles_to_u(
            [x.value for x in llh_paramset if x.name in ma_names]
        )
    else:
        mass_eigenvalues = fr_utils.MASS_EIGENVALUES
        sm_u = fr_utils.NUFIT_U

    if args.no_bsm:
        fr = fr_utils.u_to_fr(source_flux, np.array(sm_u, dtype=np.complex256))
    elif args.energy_dependance is EnergyDependance.MONO:
        u = fr_utils.params_to_BSMu(
            theta             = bsm_angles,
            dim               = args.dimension,
            energy            = args.energy,
            mass_eigenvalues  = mass_eigenvalues,
            sm_u              = sm_u,
            no_bsm            = args.no_bsm,
            fix_mixing        = args.fix_mixing,
            fix_mixing_almost = args.fix_mixing_almost,
            fix_scale         = args.fix_scale,
            scale             = args.scale
        )
        fr = fr_utils.u_to_fr(source_flux, u)
    elif args.energy_dependance is EnergyDependance.SPECTRAL:
        mf_perbin = []
        for i_sf, sf_perbin in enumerate(source_flux):
            u = fr_utils.params_to_BSMu(
                theta             = bsm_angles,
                dim               = args.dimension,
                energy            = bin_centers[i_sf],
                mass_eigenvalues  = mass_eigenvalues,
                sm_u              = sm_u,
                no_bsm            = args.no_bsm,
                fix_mixing        = args.fix_mixing,
                fix_mixing_almost = args.fix_mixing_almost,
                fix_scale         = args.fix_scale,
                scale             = args.scale
            )
            fr = fr_utils.u_to_fr(sf_perbin, u)
            mf_perbin.append(fr)
        measured_flux = np.array(mf_perbin).T
        intergrated_measured_flux = np.sum(measured_flux * bin_width, axis=1)
        averaged_measured_flux = (1./(args.binning[-1] - args.binning[0])) * \
            intergrated_measured_flux
        fr = averaged_measured_flux / np.sum(averaged_measured_flux)

    flavour_angles = fr_utils.fr_to_angles(fr)
    # print 'flavour_angles', map(float, flavour_angles)
    for idx, param in enumerate(hypo_paramset.from_tag(ParamTag.BESTFIT)):
        param.value = flavour_angles[idx]

    if args.likelihood is Likelihood.FLAT:
        llh = 1.
    elif args.likelihood is Likelihood.GAUSSIAN:
        fr_bf = args.measured_ratio
        llh = multi_gaussian(fr, fr_bf, args.sigma_ratio)
    elif args.likelihood is Likelihood.GOLEMFIT:
        llh = gf_utils.get_llh(fitter, hypo_paramset)
    elif args.likelihood is Likelihood.GF_FREQ:
        llh = gf_utils.get_llh_freq(fitter, hypo_paramset)

    if args.save_measured_fr and args.burnin is False:
        n = gen_identifier(args) + '.txt'
        with open(args.output_measured_fr + n, 'a') as f:
            f.write(r'{0:.3f} {1:.3f} {2:.3f}'.format(
                float(fr[0]), float(fr[1]), float(fr[2])
            ))
            for p in llh_paramset:
                f.write(r' {0:.3f}'.format(p.value))
            f.write('     LLH = {0:.3f}'.format(llh))
            f.write('\n')

    return llh


def ln_prob(theta, args, asimov_paramset, llh_paramset, fitter):
    lp = lnprior(theta, paramset=llh_paramset)
    if not np.isfinite(lp):
        return -np.inf
    return lp + triangle_llh(
        theta, args=args, asimov_paramset=asimov_paramset,
        llh_paramset=llh_paramset, fitter=fitter
    )