"""Статистическая обработка results_v2.csv: медианы, IQR, бутстреп-интервалы
отношения медиан, точный критерий Манна-Уитни, линейная аппроксимация."""
import sys, itertools
import numpy as np, pandas as pd
from scipy.stats import mannwhitneyu

path = sys.argv[1] if len(sys.argv) > 1 else '../data/results_v2.csv'
d = pd.read_csv(path)
d = d[d.Status == 'OK']
rng = np.random.default_rng(20261102)
rows = []
for cb, g in d.groupby('ChangeBytes'):
    on = g[g.RDCConfigured == 'ON'].Delta.to_numpy(float)
    off = g[g.RDCConfigured == 'OFF'].Delta.to_numpy(float)
    q1, med, q3 = np.percentile(on, [25, 50, 75])
    boot = [np.median(rng.choice(off, off.size)) / np.median(rng.choice(on, on.size))
            for _ in range(20000)]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    p = mannwhitneyu(off, on, alternative='two-sided', method='exact').pvalue
    rows.append(dict(ChangeBytes=cb, n_on=on.size, n_off=off.size,
                     ON_median=med, ON_Q1=q1, ON_Q3=q3, OFF_median=np.median(off),
                     ratio=np.median(off) / med, ci_lo=lo, ci_hi=hi, p_MW=p))
t = pd.DataFrame(rows)
pd.set_option('display.width', 200)
print(t.round(3).to_string(index=False))
big = t[t.ChangeBytes >= 1048576]
k, b = np.polyfit(big.ChangeBytes, big.ON_median, 1)
s = np.polyfit(np.log10(big.ChangeBytes), np.log10(big.ON_median), 1)[0]
print(f'\nΔV ≈ {b:.0f} + {k:.4f}·ΔB;  наклон lg-lg (≥1 МиБ) = {s:.3f}')
print(f'равенство объёмов при ΔB ≈ {(t.OFF_median.iloc[0]-b)/k/1073741824*100:.1f} % файла')
