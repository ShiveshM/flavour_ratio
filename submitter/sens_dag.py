#! /usr/bin/env python

from __future__ import absolute_import, division, print_function

import os
import numpy as np

x_segments = 100
scenarios = [
    [(0.00, 0.30), 'OET'],
    [(0.70, 1.00), 'OUT']
]

dims = [
    3, 6
]

for i, (xlims, tex) in enumerate(scenarios):
    x_array = np.linspace(0, 1, x_segments)
    sources = []
    for x in x_array:
        if x >= xlims[0] and x <= xlims[1]:
            sources.append([x, 1-x, 0])
    scenarios[i][0] = tuple(sources)

datadir = '/data/user/smandalia/flavour_ratio/data/sensitivity'

# prefix = ''
prefix = '_d36'
# prefix = '_kfarrag'

golemfitsourcepath = os.environ['GOLEMSOURCEPATH'] + '/GolemFit'
condor_script = golemfitsourcepath + '/scripts/flavour_ratio/submitter/sens_submit.sub'

GLOBAL_PARAMS = {}

# Bayes Factor
GLOBAL_PARAMS.update(dict(
    stat_method = 'bayesian',
    segments    = 10,
    seed        = 26,
    overwrite   = 'False'
))

# MultiNest
GLOBAL_PARAMS.update(dict(
    # mn_live_points = 1000,
    mn_live_points = 600,
    # mn_live_points = 200,
    mn_tolerance   = 0.3,
    mn_efficiency  = 0.3,
    mn_output      = './mnrun',
    run_mn         = 'True'
))

# FR
GLOBAL_PARAMS.update(dict(
    threads = 1,
    binning = '6e4 1e7 20',
    no_bsm  = 'False'
))

# GolemFit
GLOBAL_PARAMS.update(dict(
    ast  = 'p2_0',
    data = 'real'
))

dagfile = 'dagman_SENS_{0}_{1}'.format(
    GLOBAL_PARAMS['stat_method'], GLOBAL_PARAMS['data']
)
dagfile += prefix + '.submit'

with open(dagfile, 'w') as f:
    job_number = 1
    for dim in dims:
        print('dims', dim)
        of_d = datadir + '/DIM{0}/{1}'.format(dim, prefix)
        for sources, tex in scenarios:
            print('texture', tex)
            for src in sources:
                print('source flavor', src)
                for r in range(GLOBAL_PARAMS['segments']):
                    print('run', r)
                    f.write('JOB\tjob{0}\t{1}\n'.format(job_number, condor_script))
                    f.write('VARS\tjob{0}\tdimension="{1}"\n'.format(job_number, dim))
                    f.write('VARS\tjob{0}\tsr0="{1}"\n'.format(job_number, src[0]))
                    f.write('VARS\tjob{0}\tsr1="{1}"\n'.format(job_number, src[1]))
                    f.write('VARS\tjob{0}\tsr2="{1}"\n'.format(job_number, src[2]))
                    f.write('VARS\tjob{0}\ttexture="{1}"\n'.format(job_number, tex))
                    f.write('VARS\tjob{0}\teval_segment="{1}"\n'.format(job_number, r))
                    for key in GLOBAL_PARAMS.iterkeys():
                        f.write('VARS\tjob{0}\t{1}="{2}"\n'.format(job_number, key, GLOBAL_PARAMS[key]))
                    f.write('VARS\tjob{0}\tdatadir="{1}"\n'.format(job_number, of_d))
                    job_number += 1

print('total jobs = {0}'.format(job_number - 1))
print('dag file = {0}'.format(dagfile))
