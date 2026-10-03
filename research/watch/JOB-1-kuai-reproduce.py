# Reproduces the "computed by me" numbers in JOB-1-watch-through.txt. Needs numpy only.
# Not included here: KuaiRec video-level rank correlations, category-tag R2 and within-tag correlations, and the viewer/video two-way fit (findings 4 and 7, KuaiRec part); these were computed with ad hoc scripts in the session scratchpad.
# Data: KuaiRec  https://zenodo.org/records/18164998/files/KuaiRec.zip   (small_matrix.csv, big_matrix.csv, item_categories.csv)
#       KuaiRand https://zenodo.org/records/10439422/files/KuaiRand-Pure.tar.gz (log_random_4_22_to_5_08_pure.csv)
# Usage: python3 JOB-1-kuai-reproduce.py "KuaiRec 2.0/data" KuaiRand-Pure/data
import sys, numpy as np
kr, kp = sys.argv[1], sys.argv[2]

def load_rec(fn):  # user_id, video_id, play_duration, video_duration, watch_ratio
    return np.loadtxt(fn, delimiter=',', skiprows=1, usecols=(0, 1, 2, 3, 7))

for name in ('small_matrix.csv', 'big_matrix.csv'):
    u, v, pd_, vd, wr = load_rec(f'{kr}/{name}').T
    ps, ds = pd_ / 1000, vd / 1000
    print(name, 'views', len(u), 'median len s', np.median(ds).round(1))
    print(' P(play>=t s):', {t: round(float((ps >= t).mean()), 3) for t in (1, 2, 3, 5, 8, 10, 15, 30)})
    print(' share ended before 1,2,3,5 s:', [round(float((ps < t).mean()), 3) for t in (1, 2, 3, 5)])
    print(' share wr>=1, >=2:', round(float((wr >= 1).mean()), 3), round(float((wr >= 2).mean()), 3))
    nc = wr < 1
    print(' among non-completers, share ended before 2 s:', round(float((ps[nc] < 2).mean()), 3))
    for lo, hi in [(5, 7), (9, 11), (13, 15), (20, 30), (30, 60), (60, 1e9)]:
        m = (ds >= lo) & (ds < hi)
        print(f' len {lo}-{hi}s: mean wr {wr[m].mean():.3f}, share wr>=1 {(wr[m] >= 1).mean():.3f}, mean play s {ps[m].mean():.2f}')
    m = ds >= 30
    print(' hazard per 1 s bin, videos>=30 s:', [round(float(((ps[m] >= t) & (ps[m] < t + 1)).sum() / (ps[m] >= t).sum()), 3) for t in range(12)])

# KuaiRand random-exposure log: user, video, click, like, follow, comment, forward, hate, play_ms, dur_ms
a = np.loadtxt(f'{kp}/log_random_4_22_to_5_08_pure.csv', delimiter=',', skiprows=1, usecols=(0, 1, 5, 6, 7, 8, 9, 10, 12, 13))
a = a[a[:, 9] > 0]
u, v, click, like, fol, com, fwd, hate, play, dur = a.T
ps, wr = play / 1000, play / dur
print('KuaiRand random log views', len(a), 'median play s', np.median(ps).round(2), 'P(<2s)', round(float((ps < 2).mean()), 3))
def adjr2(y, g):
    _, inv = np.unique(g, return_inverse=True); k = inv.max() + 1; n = len(y)
    m = np.bincount(inv, y) / np.bincount(inv)
    return 1 - (((y - m[inv]) ** 2).sum() / (n - k)) / (((y - y.mean()) ** 2).sum() / (n - 1))
q = np.digitize(dur, np.quantile(dur, np.linspace(0, 1, 41)[1:-1]))
for nm, y in (('log play s', np.log(ps + 0.1)), ('completion (capped 1)', np.minimum(wr, 1.0))):
    print(nm, 'adj R2: user', round(adjr2(y, u), 3), 'video', round(adjr2(y, v), 3), 'length bins', round(adjr2(y, q), 3))
for lo, hi in [(0, .25), (.25, .5), (.5, 1), (1, 2), (2, 1e9)]:
    m = (wr >= lo) & (wr < hi)
    print(f' wr {lo}-{hi}: n {m.sum()} like {like[m].mean():.4f} follow {fol[m].mean():.5f} comment {com[m].mean():.5f} forward {fwd[m].mean():.5f}')
