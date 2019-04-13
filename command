python contour.py --data real --debug true --nsteps 100 --burnin 10 --nwalkers 20 --outfile ./test_ --seed 26 --stat-method bayesian --threads max
python sens.py --debug True --data real --datadir ./test --dimension 6 --eval-segment 1 --mn-live-points 100 --mn-output ./test --mn-tolerance 0.3 --seed 26 --segments 10 --source-ratio 1 2 0 --stat-method bayesian --threads 4 --texture oeu

python plot_sens.py --data real --datadir /data/user/smandalia/flavour_ratio/data/sensitivity/ --dimensions 6 --plot-x True --segments 10 --x-segments 20 --split-jobs True --stat-method bayesian --texture none
