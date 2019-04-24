# author : S. Mandalia
#          s.p.mandalia@qmul.ac.uk
#
# date   : March 19, 2018

"""
Plotting functions for the BSM flavour ratio analysis
"""

from __future__ import absolute_import, division

import os
import socket
from copy import deepcopy

import numpy as np
import numpy.ma as ma
from scipy.interpolate import splev, splprep
from scipy.ndimage.filters import gaussian_filter

import matplotlib as mpl
import matplotlib.patches as patches
import matplotlib.gridspec as gridspec
mpl.use('Agg')

from matplotlib import rc
from matplotlib import pyplot as plt
from matplotlib.offsetbox import AnchoredText
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.patches import Arrow

from getdist import plots, mcsamples

import ternary
from ternary.heatmapping import polygon_generator

import shapely.geometry as geometry

from utils.enums import DataType, str_enum
from utils.enums import Likelihood, ParamTag, StatCateg, Texture
from utils.misc import get_units, make_dir, solve_ratio, interval
from utils.fr import angles_to_u, angles_to_fr, SCALE_BOUNDARIES


BAYES_K = 1.   # Substantial degree of belief.
# BAYES_K = 3/2. # Strong degree of belief.
# BAYES_K = 2.   # Very strong degree of belief
# BAYES_K = 5/2. # Decisive degree of belief


LV_ATMO_90PC_LIMITS = {
    3: (2E-24, 1E-1),
    4: (2.7E-28, 3.16E-25),
    5: (1.5E-32, 1.12E-27),
    6: (9.1E-37, 2.82E-30),
    7: (3.6E-41, 1.77E-32),
    8: (1.4E-45, 1.00E-34)
}


PS = 8.203E-20 # GeV^{-1}
PLANCK_SCALE = {
    5: PS,
    6: PS**2,
    7: PS**3,
    8: PS**4
}


if os.path.isfile('./plot_llh/paper.mplstyle'):
    plt.style.use('./plot_llh/paper.mplstyle')
elif os.environ.get('GOLEMSOURCEPATH') is not None:
    plt.style.use(os.environ['GOLEMSOURCEPATH']+'/GolemFit/scripts/paper/paper.mplstyle')
if 'submitter' in socket.gethostname():
    rc('text', usetex=False)


def gen_figtext(args):
    """Generate the figure text."""
    t = r'$'
    t += r'{\rm Source\:flavour\:ratio}'+r'\:=\:({0})'.format(
        solve_ratio(args.source_ratio).replace('_', ':')
    )
    if args.data in [DataType.ASIMOV, DataType.REALISATION]:
        t += '\n' + r'\rm{Injected\:flavour\:ratio}'+r'\:=\:({0})'.format(
            solve_ratio(args.injected_ratio).replace('_', ':')
        )
    t += '$\n' + r'${\rm Dimension}'+r' = {0}$'.format(args.dimension)
    return t


def texture_label(x):
    if x == Texture.OEU:
        return r'$\mathcal{O}_{e\mu}$'
    elif x == Texture.OET:
        return r'$\mathcal{O}_{e\tau}$'
    elif x == Texture.OUT:
        return r'$\mathcal{O}_{\mu\tau}$'
    else:
        raise AssertionError


def cmap_discretize(cmap, N):
    colors_i = np.concatenate((np.linspace(0, 1., N), (0.,0.,0.,0.)))
    colors_rgba = cmap(colors_i)
    indices = np.linspace(0, 1., N+1)
    cdict = {}
    for ki,key in enumerate(('red','green','blue')):
        cdict[key] = [ (indices[i], colors_rgba[i-1,ki], colors_rgba[i,ki]) for i in xrange(N+1) ]
    # Return colormap object.
    return mpl.colors.LinearSegmentedColormap(cmap.name + "_%d"%N, cdict, 1024)


def get_limit(scales, statistic, args, mask_initial=False):
    max_st = np.max(statistic)
    print 'scales, stat', zip(scales, statistic)
    if args.stat_method is StatCateg.BAYESIAN:
        if (statistic[0] - max_st) > np.log(10**(BAYES_K)):
            raise AssertionError('Discovered LV!')

    try:
        tck, u = splprep([scales, statistic], s=0)
    except:
        print 'Failed to spline'
        # return None
        raise
    sc, st = splev(np.linspace(0, 1, 1000), tck)

    if mask_initial:
        scales_rm = sc[sc >= scales[1]]
        statistic_rm = st[sc >= scales[1]]
    else:
        scales_rm = sc
        statistic_rm = st

    min_idx = np.argmin(scales)
    null = statistic[min_idx]
    if args.stat_method is StatCateg.BAYESIAN:
        reduced_ev = -(statistic_rm - null)
        print '[reduced_ev > np.log(10**(BAYES_K))]', np.sum([reduced_ev > np.log(10**(BAYES_K))])
        al = scales_rm[reduced_ev > np.log(10**(BAYES_K))]
    else:
        assert 0
    if len(al) == 0:
        print 'No points for DIM {0} [{1}, {2}, {3}]!'.format(
            args.dimension, *args.source_ratio
        )
        return None
    if reduced_ev[-1] < np.log(10**(BAYES_K)) - 0.1:
        print 'Warning, peaked contour does not exclude large scales! For ' \
            'DIM {0} [{1}, {2}, {3}]!'.format(
                args.dimension, *args.source_ratio
            )
        # return None
    lim = al[0]
    print 'limit = {0}'.format(lim)
    return lim


def heatmap(data, scale, vmin=None, vmax=None, style='triangular'):
    for k, v in data.items():
        data[k] = np.array(v)
    style = style.lower()[0]
    if style not in ["t", "h", 'd']:
        raise ValueError("Heatmap style must be 'triangular', 'dual-triangular', or 'hexagonal'")

    vertices_values = polygon_generator(data, scale, style)

    vertices = []
    for v, value in vertices_values:
        vertices.append(v)
    return vertices


def get_tax(ax, scale, ax_labels):
    ax.set_aspect('equal')

    # Boundary and Gridlines
    fig, tax = ternary.figure(ax=ax, scale=scale)

    # Draw Boundary and Gridlines
    tax.boundary(linewidth=2.0)
    tax.gridlines(color='grey', multiple=scale/5., linewidth=1.0, alpha=0.4, ls='--')
    tax.gridlines(color='grey', multiple=scale/10., linewidth=0.5, alpha=0.4, ls=':')

    # Set Axis labels and Title
    fontsize = 23
    tax.bottom_axis_label(ax_labels[0], fontsize=fontsize+8, position=(0.55, -0.20/2, 0.5), rotation=0)
    tax.right_axis_label(ax_labels[1], fontsize=fontsize+8, offset=0.2, rotation=0)
    tax.left_axis_label(ax_labels[2], fontsize=fontsize+8, offset=0.2, rotation=0)

    # Remove default Matplotlib axis
    tax.get_axes().axis('off')
    tax.clear_matplotlib_ticks()

    # Set ticks
    ticks = np.linspace(0, 1, 6)
    tax.ticks(ticks=ticks, locations=ticks*scale, axis='blr', linewidth=1,
              offset=0.03, fontsize=fontsize, tick_formats='%.1f')
    # tax.ticks()

    tax._redraw_labels()

    return tax


def flavour_contour(frs, ax, nbins, coverage, fill=False, **kwargs):
    """Plot the flavour contour for a specified coverage."""
    # Histogram in flavour space
    H, b = np.histogramdd(
        (frs[:,0], frs[:,1], frs[:,2]),
        bins=(nbins+1, nbins+1, nbins+1), range=((0, 1), (0, 1), (0, 1))
    )
    H = H / np.sum(H)

    # 3D smoothing
    smoothing = 0.05
    H_s = gaussian_filter(H, sigma=smoothing)

    # Finding coverage
    H_r = np.ravel(H_s)
    H_rs = np.argsort(H_r)[::-1]
    H_crs = np.cumsum(H_r[H_rs])
    thres = np.searchsorted(H_crs, coverage/100.)
    mask_r = np.zeros(H_r.shape)
    mask_r[H_rs[:thres]] = 1
    mask = mask_r.reshape(H_s.shape)

    # Get vertices inside covered region
    binx = np.linspace(0, 1, nbins+1)
    interp_dict = {}
    for i in xrange(len(binx)):
        for j in xrange(len(binx)):
            for k in xrange(len(binx)):
                if mask[i][j][k] == 1:
                    interp_dict[(i, j, k)] = H_s[i, j, k]
    vertices = np.array(heatmap(interp_dict, nbins))
    points = vertices.reshape((len(vertices)*3, 2))

    # Convex full to find points forming exterior bound
    pc = geometry.MultiPoint(points)
    polygon = pc.convex_hull
    ex_cor = np.array(list(polygon.exterior.coords))

    # Join points with a spline
    tck, u = splprep([ex_cor.T[0], ex_cor.T[1]], s=0., per=1, k=1)
    xi, yi = map(np.array, splev(np.linspace(0, 1, 300), tck))

    # Spline again to smooth
    tck, u = splprep([xi, yi], s=0.4, per=1, k=3)
    xi, yi = map(np.array, splev(np.linspace(0, 1, 300), tck))
    ev_polygon = np.dstack((xi, yi))[0]

    def project_toflavour(p):
        """Convert from cartesian to flavour space."""
        x, y = p
        b = y / (np.sqrt(3)/2.)
        a = x - b/2.
        return [a, b, nbins-a-b]

    # Remove points interpolated outside flavour triangle
    f_ev_polygon = np.array(map(project_toflavour, ev_polygon))
    xf, yf, zf = f_ev_polygon.T
    mask = np.array((xf < 0) | (yf < 0) | (zf < 0) | (xf > nbins) |
                    (yf > nbins) | (zf > nbins))
    ev_polygon = np.dstack((xi[~mask], yi[~mask]))[0]

    # Plot
    if fill:
        ax.fill(
            ev_polygon.T[0], ev_polygon.T[1], label=r'{0}\%'.format(int(coverage)),
            **kwargs
        )
    else:
        ax.plot(
            ev_polygon.T[0], ev_polygon.T[1], label=r'{0}\%'.format(int(coverage)),
            **kwargs
        )
    # ax.scatter(points.T[0], points.T[1], marker='o', s=2, alpha=1, zorder=3,
    #           **kwargs)


def plot_Tchain(Tchain, axes_labels, ranges):
    """Plot the Tchain using getdist."""
    Tsample = mcsamples.MCSamples(
        samples=Tchain, labels=axes_labels, ranges=ranges
    )

    Tsample.updateSettings({'contours': [0.90, 0.99]})
    Tsample.num_bins_2D=500
    Tsample.fine_bins_2D=500
    Tsample.smooth_scale_2D=0.03

    g = plots.getSubplotPlotter()
    g.settings.num_plot_contours = 2
    g.settings.axes_fontsize = 10
    g.settings.figure_legend_frame = False
    g.triangle_plot(
        [Tsample], filled=True,
    )
    return g


def chainer_plot(infile, outfile, outformat, args, llh_paramset, fig_text=None):
    """Make the triangle plot."""
    if hasattr(args, 'plot_elements'):
        if not args.plot_angles and not args.plot_elements:
            return
    elif not args.plot_angles:
        return

    if not isinstance(infile, np.ndarray):
        raw = np.load(infile)
    else:
        raw = infile
    print 'raw.shape', raw.shape
    print 'raw', raw

    make_dir(outfile), make_dir
    if fig_text is None:
        fig_text = gen_figtext(args)

    axes_labels = llh_paramset.labels
    ranges = llh_paramset.ranges

    if args.plot_angles:
        print "Making triangle plots"
        Tchain = raw
        g = plot_Tchain(Tchain, axes_labels, ranges)

        mpl.pyplot.figtext(0.5, 0.7, fig_text, fontsize=15)

        for i_ax_1, ax_1 in enumerate(g.subplots):
            for i_ax_2, ax_2 in enumerate(ax_1):
                if i_ax_1 == i_ax_2:
                    itv = interval(Tchain[:,i_ax_1], percentile=90.)
                    for l in itv:
                        ax_2.axvline(l, color='gray', ls='--')
                        ax_2.set_title(r'${0:.2f}_{{{1:.2f}}}^{{+{2:.2f}}}$'.format(
                            itv[1], itv[0]-itv[1], itv[2]-itv[1]
                        ), fontsize=10)

        # if not args.fix_mixing:
        #     sc_index = llh_paramset.from_tag(ParamTag.SCALE, index=True)
        #     itv = interval(Tchain[:,sc_index], percentile=90.)
        #     mpl.pyplot.figtext(
        #         0.5, 0.3, 'Scale 90% Interval = [1E{0}, 1E{1}], Center = '
        #         '1E{2}'.format(itv[0], itv[2], itv[1])
        #     )

        if args.data is DataType.REAL:
            plt.text(0.8, 0.9, 'IceCube Preliminary', color='red', fontsize=15,
                     ha='center', va='center')
        elif args.data in [DataType.ASIMOV, DataType.REALISATION]:
            plt.text(0.8, 0.9, 'IceCube Simulation', color='red', fontsize=15,
                     ha='center', va='center')

        for of in outformat:
            print 'Saving', outfile+'_angles.'+of
            g.export(outfile+'_angles.'+of)

    if not hasattr(args, 'plot_elements'):
        return

    if args.plot_elements:
        print "Making triangle plots"
        if args.fix_mixing_almost:
            raise NotImplementedError
        nu_index = llh_paramset.from_tag(ParamTag.NUISANCE, index=True)
        fr_index = llh_paramset.from_tag(ParamTag.MMANGLES, index=True)
        sc_index = llh_paramset.from_tag(ParamTag.SCALE, index=True)
        if not args.fix_source_ratio:
            sr_index = llh_paramset.from_tag(ParamTag.SRCANGLES, index=True)

        nu_elements = raw[:,nu_index]
        fr_elements = np.array(map(flat_angles_to_u, raw[:,fr_index]))
        sc_elements = raw[:,sc_index]
        if not args.fix_source_ratio:
            sr_elements = np.array(map(angles_to_fr, raw[:,sr_index]))
        if args.fix_source_ratio:
            Tchain = np.column_stack(
                [nu_elements, fr_elements, sc_elements]
            )
        else:
            Tchain = np.column_stack(
                [nu_elements, fr_elements, sc_elements, sr_elements]
            )

        trns_ranges = np.array(ranges)[nu_index,].tolist()
        trns_axes_labels = np.array(axes_labels)[nu_index,].tolist()
        if args.fix_mixing is not MixingScenario.NONE:
            trns_axes_labels += \
                [r'\mid \tilde{U}_{e1} \mid'    , r'\mid \tilde{U}_{e2} \mid'    , r'\mid \tilde{U}_{e3} \mid'     , \
                 r'\mid \tilde{U}_{\mu1} \mid'  , r'\mid \tilde{U}_{\mu2} \mid'  , r'\mid \tilde{U}_{\mu3} \mid'   , \
                 r'\mid \tilde{U}_{\tau1} \mid' , r'\mid \tilde{U}_{\tau2} \mid' , r'\mid \tilde{U}_{\tau3} \mid']
            trns_ranges += [(0, 1)] * 9
        if not args.fix_scale:
            trns_axes_labels += [np.array(axes_labels)[sc_index].tolist()]
            trns_ranges += [np.array(ranges)[sc_index].tolist()]
        if not args.fix_source_ratio:
            trns_axes_labels += [r'\phi_e', r'\phi_\mu', r'\phi_\tau']
            trns_ranges += [(0, 1)] * 3

        g = plot_Tchain(Tchain, trns_axes_labels, trns_ranges)

        if args.data is DataType.REAL:
            plt.text(0.8, 0.7, 'IceCube Preliminary', color='red', fontsize=15,
                     ha='center', va='center')
        elif args.data in [DataType.ASIMOV, DataType.REALISATION]:
            plt.text(0.8, 0.7, 'IceCube Simulation', color='red', fontsize=15,
                     ha='center', va='center')

        mpl.pyplot.figtext(0.5, 0.7, fig_text, fontsize=15)
        for of in outformat:
            print 'Saving', outfile+'_elements'+of
            g.export(outfile+'_elements.'+of)


def plot_statistic(data, outfile, outformat, args, scale_param, label=None):
    """Make MultiNest factor or LLH value plot."""
    print 'Making Statistic plot'
    fig_text = gen_figtext(args)
    if label is not None: fig_text += '\n' + label

    print 'data', data
    print 'data.shape', data.shape
    scales, statistic = ma.compress_rows(data).T
    try:
        tck, u = splprep([scales, statistic], s=0)
    except:
        return
    sc, st = splev(np.linspace(0, 1, 10000), tck)
    scales_rm = sc[sc >= scales[1]]
    statistic_rm = st[sc >= scales[1]]

    min_idx = np.argmin(scales)
    null = statistic[min_idx]
    fig_text += '\nnull lnZ = {0:.2f}'.format(null)

    if args.stat_method is StatCateg.BAYESIAN:
        reduced_ev = -(statistic_rm - null)
    elif args.stat_method is StatCateg.FREQUENTIST:
        reduced_ev = -2*(statistic_rm - null)

    fig = plt.figure(figsize=(7, 5))
    ax = fig.add_subplot(111)

    xlims = SCALE_BOUNDARIES[args.dimension]
    ax.set_xlim(xlims)
    ax.set_xlabel(r'${\mathrm {log}}_{10} \left (\Lambda^{-1}' + \
                  get_units(args.dimension) +r'\right )$', fontsize=16)
    if args.stat_method is StatCateg.BAYESIAN:
        ax.set_ylabel(r'log(Bayes Factor)')
    elif args.stat_method is StatCateg.FREQUENTIST:
        ax.set_ylabel(r'$-2\Delta {\rm LLH}$')

    # ymin = np.round(np.min(reduced_ev) - 1.5)
    # ymax = np.round(np.max(reduced_ev) + 1.5)
    # ax.set_ylim((ymin, ymax))

    ax.plot(scales_rm, reduced_ev)

    ax.axhline(y=np.log(10**(BAYES_K)), color='red', alpha=1., linewidth=1.3)

    for ymaj in ax.yaxis.get_majorticklocs():
        ax.axhline(y=ymaj, ls=':', color='gray', alpha=0.3, linewidth=1)
    for xmaj in ax.xaxis.get_majorticklocs():
        ax.axvline(x=xmaj, ls=':', color='gray', alpha=0.3, linewidth=1)

    if args.data is DataType.REAL:
        fig.text(0.8, 0.14, 'IceCube Preliminary', color='red', fontsize=9,
                 ha='center', va='center')
    elif args.data in [DataType.ASIMOV, DataType.REALISATION]:
        fig.text(0.8, 0.14, 'IceCube Simulation', color='red', fontsize=9,
                 ha='center', va='center')

    at = AnchoredText(
        fig_text, prop=dict(size=10), frameon=True, loc=4
    )
    at.patch.set_boxstyle("round,pad=0.1,rounding_size=0.5")
    ax.add_artist(at)
    make_dir(outfile)
    for of in outformat:
        print 'Saving as {0}'.format(outfile+'.'+of)
        fig.savefig(outfile+'.'+of, bbox_inches='tight', dpi=150)


def plot_table_sens(data, outfile, outformat, args):
    print 'Making TABLE sensitivity plot'
    argsc = deepcopy(args)

    dims = args.dimensions
    srcs = args.source_ratios
    if args.texture is Texture.NONE:
        textures = [Texture.OEU, Texture.OET, Texture.OUT]
    else:
        textures = [args.texture]

    if len(srcs) > 3:
        raise NotImplementedError

    xlims = (-60, -20)
    ylims = (0.5, 1.5)

    colour = {0:'red', 1:'blue', 2:'green'}
    rgb_co = {0:[1,0,0], 1:[0,0,1], 2:[0.0, 0.5019607843137255, 0.0]}

    fig = plt.figure(figsize=(8, 6))
    gs = gridspec.GridSpec(dims, 1)
    gs.update(hspace=0.15)

    first_ax = None
    legend_log = []
    legend_elements = []

    for idim, dim in enumerate(dimensions):
        print '|||| DIM = {0}'.format(dim)
        argsc.dimension = dim
        gs0 = gridspec.GridSpecFromSubplotSpec(
            len(textures), 1, subplot_spec=gs[idim], hspace=0
        )

        for itex, tex in enumerate(textures):
            argcs.texture = tex
            ylabel = texture_label(texture)
            # if angles == 2 and ian == 0: continue
            ax = fig.add_subplot(gs0[itex])

            if first_ax is None:
                first_ax = ax

            ax.set_xlim(xlims)
            ax.set_ylim(ylims)
            ax.set_yticks([1.])
            ax.set_yticklabels([ylabel], fontsize=13)
            ax.yaxis.tick_right()
            for xmaj in ax.xaxis.get_majorticklocs():
                ax.axvline(x=xmaj, ls=':', color='gray', alpha=0.2, linewidth=1)
            ax.get_xaxis().set_visible(False)
            # TODO(shivesh): check this
            if itex == len(tex) - 2:
                ax.spines['bottom'].set_alpha(0.6)
            elif itex == len(tex) - 1:
                ax.text(
                    -0.04, ylims[0], '$d = {0}$'.format(dim), fontsize=16,
                    rotation='90', verticalalignment='center',
                    transform=ax.transAxes
                )
                dim_label_flag = False
                ax.spines['top'].set_alpha(0.6)
                ax.spines['bottom'].set_alpha(0.6)

            for isrc, src in enumerate(srcs):
                print '== src', src
                argsc.source_ratio = src

                if dim in PLANCK_SCALE.iterkeys():
                    ps = np.log10(PLANCK_SCALE[dim])
                    if ps < xlims[0]:
                        ax.annotate(
                            s='', xy=(xlims[0], 1), xytext=(xlims[0]+1, 1),
                            arrowprops={'arrowstyle': '->, head_length=0.2',
                                        'lw': 1, 'color':'purple'}
                        )
                    elif ps > xlims[1]:
                        ax.annotate(
                            s='', xy=(xlims[1]-1, 1), xytext=(xlims[1], 1),
                            arrowprops={'arrowstyle': '<-, head_length=0.2',
                                        'lw': 1, 'color':'purple'}
                        )
                    else:
                        ax.axvline(x=ps, color='purple', alpha=1., linewidth=1.5)

                scales, statistic = ma.compress_rows(data[idim][isrc][itex]).T
                lim = get_limit(scales, statistic, argsc, mask_initial=True)
                if lim is None: continue

                ax.axvline(x=lim, color=colour[isrc], alpha=1., linewidth=1.5)
                ax.add_patch(patches.Rectangle(
                    (lim, ylims[0]), 100, np.diff(ylims), fill=True,
                    facecolor=colour[isrc], alpha=0.3, linewidth=0
                ))

                if isrc not in legend_log:
                    legend_log.append(isrc)
                    label = '{0} at source'.format(solve_ratio(src))
                    legend_elements.append(
                        Patch(facecolor=rgb_co[isrc]+[0.3],
                              edgecolor=rgb_co[isrc]+[1], label=label)
                    )

            if itex == 2:
                LV_lim = np.log10(LV_ATMO_90PC_LIMITS[dim])
                ax.add_patch(patches.Rectangle(
                    (LV_lim[1], ylim[0]), LV_lim[0]-LV_lim[1], np.diff(ylim),
                    fill=False, hatch='\\\\'
                ))

    ax.get_xaxis().set_visible(True)
    ax.set_xlabel(r'${\rm New\:Physics\:Scale}\:[\:{\rm log}_{10} (\Lambda^{-1}\:/\:{\rm GeV}^{-d+4})\: ]$',
                 fontsize=19)
    ax.tick_params(axis='x', labelsize=16)

    purple = [0.5019607843137255, 0.0, 0.5019607843137255]
    legend_elements.append(
        Patch(facecolor=purple+[0.7], edgecolor=purple+[1], label='Planck Scale Expectation')
    )
    legend_elements.append(
        Patch(facecolor='none', hatch='\\\\', edgecolor='k', label='IceCube, Nature.Phy.14,961(2018)')
    )
    legend = first_ax.legend(
        handles=legend_elements, prop=dict(size=11), loc='upper left',
        title='Excluded regions', framealpha=1., edgecolor='black',
        frameon=True
    )
    first_ax.set_zorder(10)
    plt.setp(legend.get_title(), fontsize='11')
    legend.get_frame().set_linestyle('-')

    ybound = 0.595
    if args.data is DataType.REAL:
        # fig.text(0.295, 0.684, 'IceCube Preliminary', color='red', fontsize=13,
        fig.text(0.278, ybound, r'\bf IceCube Preliminary', color='red', fontsize=13,
                 ha='center', va='center', zorder=11)
    elif args.data is DataType.REALISATION:
        fig.text(0.278, ybound-0.05, r'\bf IceCube Simulation', color='red', fontsize=13,
                 ha='center', va='center', zorder=11)
    else:
        fig.text(0.278, ybound, r'\bf IceCube Simulation', color='red', fontsize=13,
                 ha='center', va='center', zorder=11)

    make_dir(outfile)
    for of in outformat:
        print 'Saving plot as {0}'.format(outfile+'.'+of)
        fig.savefig(outfile+'.'+of, bbox_inches='tight', dpi=150)


def plot_x(data, outfile, outformat, args, normalise=False):
    """Limit plot as a function of the source flavour ratio for each operator
    texture."""
    print 'Making X sensitivity plot'
    dim = args.dimension
    srcs = args.source_ratios
    x_arr = np.array([i[0] for i in srcs])
    if args.texture is Texture.NONE:
        textures = [Texture.OEU, Texture.OET, Texture.OUT]
    else:
        textures = [args.texture]

    # Rearrange data structure
    r_data = np.full((
        data.shape[1], data.shape[0], data.shape[2], data.shape[3]
    ), np.nan)

    for isrc in xrange(data.shape[0]):
        for itex in xrange(data.shape[1]):
            r_data[itex][isrc] = data[isrc][itex]
    r_data = ma.masked_invalid(r_data)
    print r_data.shape, 'r_data.shape'

    if normalise:
        fig = plt.figure(figsize=(7, 6))
    else:
        fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    if normalise:
        ylims = (-10, 8)
    else:
        ylims = (-60, -20)
    xlims = (0, 1)

    colour = {0:'red', 1:'green', 2:'blue'}
    rgb_co = {0:[1,0,0], 1:[0.0, 0.5019607843137255, 0.0], 2:[0,0,1]}

    legend_log = []
    legend_elements = []
    labelsize = 13
    largesize = 17

    ax.set_xlim(xlims)
    ax.set_ylim(ylims)
    xticks = [0, 1/3., 0.5, 2/3., 1]
    # xlabels = [r'$0$', r'$\frac{1}{3}$', r'$\frac{1}{2}$', r'$\frac{2}{3}$', r'$1$']
    xlabels = [r'$0$', r'$1 / 3$', r'$1/2$', r'$2/3$', r'$1$']
    ax.set_xticks([], minor=True)
    ax.set_xticks(xticks, minor=False)
    ax.set_xticklabels(xlabels, fontsize=largesize)
    for ymaj in ax.yaxis.get_majorticklocs():
        ax.axhline(y=ymaj, ls=':', color='gray', alpha=0.2, linewidth=1)
    for xmaj in xticks:
        if xmaj == 1/3.:
            ax.axvline(x=xmaj, ls='-', color='gray', alpha=0.5, linewidth=1)
        else:
            ax.axvline(x=xmaj, ls=':', color='gray', alpha=0.2, linewidth=1)

    ax.text(
        (1/3.)+0.01, 0.01,  r'$f_{\alpha}^S=(1:2:0)$', fontsize=labelsize,
        transform=ax.transAxes, rotation='vertical', va='bottom'
    )
    ax.text(
        0.96, 0.01, r'$f_{\alpha}^S=(1:0:0)$', fontsize=labelsize,
        transform=ax.transAxes, rotation='vertical', va='bottom', ha='left'
    )
    ax.text(
        0.01, 0.01, r'$f_{\alpha}^S=(0:1:0)$', fontsize=labelsize,
        transform=ax.transAxes, rotation='vertical', va='bottom'
    )
    ax.text(
        0.07, 0.46, r'${\rm \bf Excluded}$', fontsize=largesize,
        transform=ax.transAxes, color = 'g', rotation='vertical', zorder=10
    )
    ax.text(
        0.95, 0.46, r'${\rm \bf Excluded}$', fontsize=largesize,
        transform=ax.transAxes, color = 'b', rotation='vertical', zorder=10
    )

    for itex, tex in enumerate(textures):
        print '|||| TEX = {0}'.format(tex)
        lims = np.full(len(srcs), np.nan)

        for isrc, src in enumerate(srcs):
            x = src[0]
            print '|||| X = {0}'.format(x)
            args.source_ratio = src
            d = r_data[itex][isrc]
            if np.sum(d.mask) > 0:
                continue
            scales, statistic = ma.compress_rows(d).T
            lim = get_limit(scales, statistic, args, mask_initial=True)
            if lim is None: continue
            if normalise:
                lim -= np.log10(PLANCK_SCALE[dim])
            lims[isrc] = lim

        lims = ma.masked_invalid(lims)
        size = np.sum(~lims.mask)
        if size == 0: continue

        print 'x_arr, lims', zip(x_arr, lims)
        if normalise:
            zeropoint = 100
        else:
            zeropoint = 0
        lims[lims.mask] = zeropoint
        tck, u = splprep([x_arr, lims], s=0, k=1)
        x, y = splev(np.linspace(0, 1, 1000), tck)
        y = gaussian_filter(y, sigma=4)
        ax.fill_between(x, y, zeropoint, color=colour[itex], alpha=0.3)
        # ax.scatter(x, y, color='black', s=1)
        # ax.scatter(x_arr, lims, color=colour[itex], s=8)

        if itex not in legend_log:
            legend_log.append(itex)
            label = texture_label(tex)[:-1] + r'\:{\rm\:texture}$'
            legend_elements.append(
                Patch(facecolor=rgb_co[itex]+[0.3],
                      edgecolor=rgb_co[itex]+[1], label=label)
            )

    LV_lim = np.log10(LV_ATMO_90PC_LIMITS[dim])
    if normalise:
        LV_lim -= np.log10(PLANCK_SCALE[dim])
    ax.add_patch(patches.Rectangle(
        (xlims[0], LV_lim[1]), np.diff(xlims), LV_lim[0]-LV_lim[1],
        fill=False, hatch='\\\\'
    ))

    if dim in PLANCK_SCALE:
        ps = np.log10(PLANCK_SCALE[dim])
        if normalise:
            ps -= np.log10(PLANCK_SCALE[dim])
            ax.add_patch(Arrow(
                0.27, -0.009, 0, -5, width=0.12, capstyle='butt',
                facecolor='purple', fill=True, alpha=0.8,
                edgecolor='darkmagenta'
            ))
            ax.add_patch(Arrow(
                0.82, -0.009, 0, -5, width=0.12, capstyle='butt',
                facecolor='purple', fill=True, alpha=0.8,
                edgecolor='darkmagenta'
            ))

            ax.text(
                0.3, 0.4, r'${\rm \bf Quantum\:Gravity\:Frontier}$',
                fontsize=largesize-2, transform=ax.transAxes, va='top',
                ha='left', color='purple'
            )
        ax.axhline(y=ps, color='purple', alpha=1., linewidth=1.5)

    if normalise:
        fig.text(
            0.02, 0.5,
            r'${\rm New\:Physics\:Scale}\:[\:{\rm log}_{10} \left (\Lambda_{' +
            r'\:d={0}'.format(args.dimension)+r'}\:/\:{\rm M}_{\:\rm Planck}^{\:'+
            r'{0}'.format(args.dimension-4)+ r'}\right )\: ]$', ha='left',
            va='center', rotation='vertical', fontsize=largesize
        )
    else:
        fig.text(
            0.02, 0.5,
            r'${\rm New\:Physics\:Scale}\:[\:{\rm log}_{10} \left (\Lambda_{' +
            r'\:d={0}'.format(args.dimension)+r'}^{-1}\:' + get_units(args.dimension) +
            r'\right )\: ]$', ha='left',
            va='center', rotation='vertical', fontsize=largesize
        )

    ax.set_xlabel(
        r'${\rm Source\:Flavour\:Ratio}\:[\:f_{\alpha}^S=\left (\:x:1-x:0\:\right )\:]$',
        fontsize=largesize
    )
    ax.tick_params(axis='x', labelsize=largesize-1)

    purple = [0.5019607843137255, 0.0, 0.5019607843137255]
    legend_elements.append(
        Patch(facecolor=purple+[0.7], edgecolor=purple+[1], label='Planck Scale Expectation')
    )
    legend_elements.append(
        Patch(facecolor='none', hatch='\\\\', edgecolor='k', label='IceCube, Nature.Phy.14,961(2018)')
    )
    legend = ax.legend(
        handles=legend_elements, prop=dict(size=labelsize-2),
        loc='upper center', title='Excluded regions', framealpha=1.,
        edgecolor='black', frameon=True, bbox_to_anchor=(0.55, 1)
    )
    plt.setp(legend.get_title(), fontsize=labelsize)
    legend.get_frame().set_linestyle('-')

    # ybound = 0.61
    # if args.data is DataType.REAL:
    #     fig.text(0.278, ybound, r'\bf IceCube Preliminary', color='red', fontsize=13,
    #              ha='center', va='center', zorder=11)
    # elif args.data is DataType.REALISATION:
    #     fig.text(0.278, ybound-0.05, r'\bf IceCube Simulation', color='red', fontsize=13,
    #              ha='center', va='center', zorder=11)
    # else:
    #     fig.text(0.278, ybound, r'\bf IceCube Simulation', color='red', fontsize=13,
    #              ha='center', va='center', zorder=11)

    make_dir(outfile)
    for of in outformat:
        print 'Saving plot as {0}'.format(outfile + '.' + of)
        fig.savefig(outfile + '.' + of, bbox_inches='tight', dpi=150)
