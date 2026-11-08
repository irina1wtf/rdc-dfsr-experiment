"""Обработка results_v2.csv.

Для каждого уровня изменения: медиана и квартили Q1–Q3 объёма передачи с RDC,
коэффициент вариации, медиана без RDC, отношение медиан и его диапазон по всем
25 парам опытов (min/max), справочно точный критерий Манна–Уитни.
Затем линейная аппроксимация медиан с RDC (от 1 МиБ): коэффициенты, R² и
95 %-е доверительные интервалы.

Серии выполнены блоками, повторы шли подряд на одном файле без восстановления
исходного содержимого, поэтому наблюдения не независимы: p-значение и
доверительные интервалы формальные, результаты имеют описательный характер.
"""
import sys
import numpy as np, pandas as pd
from scipy import stats

path = sys.argv[1] if len(sys.argv) > 1 else '../data/results_v2.csv'
d = pd.read_csv(path)
d = d[d.Status == 'OK']
rows = []
for cb, g in d.groupby('ChangeBytes'):
    on = g[g.RDCConfigured == 'ON'].Delta.to_numpy(float)
    off = g[g.RDCConfigured == 'OFF'].Delta.to_numpy(float)
    q1, med, q3 = np.percentile(on, [25, 50, 75])
    p = stats.mannwhitneyu(off, on, alternative='two-sided', method='exact').pvalue
    rows.append(dict(ChangeBytes=cb, n_on=on.size, n_off=off.size,
                     ON_median=med, ON_Q1=q1, ON_Q3=q3,
                     cv_on=on.std(ddof=1) / on.mean() * 100,
                     OFF_median=np.median(off),
                     ratio=np.median(off) / med,
                     ratio_min=off.min() / on.max(), ratio_max=off.max() / on.min(),
                     p_MW=p))
t = pd.DataFrame(rows)
pd.set_option('display.width', 200)
print(t.round(3).to_string(index=False))

big = t[t.ChangeBytes >= 1048576]
r = stats.linregress(big.ChangeBytes, big.ON_median)
tq = stats.t.ppf(0.975, len(big) - 2)
a_lo, a_hi = r.intercept - tq * r.intercept_stderr, r.intercept + tq * r.intercept_stderr
b_lo, b_hi = r.slope - tq * r.stderr, r.slope + tq * r.stderr
s = np.polyfit(np.log10(big.ChangeBytes), np.log10(big.ON_median), 1)[0]
print(f'\nАппроксимация по {len(big)} медианам (от 1 МиБ до 75 %):')
print(f'ΔV ≈ {r.intercept:.0f} + {r.slope:.4f}·ΔB;  R² = {r.rvalue**2:.8f}')
print(f'95 % ДИ: свободный член {a_lo:.0f}–{a_hi:.0f} байт, наклон {b_lo:.6f}–{b_hi:.6f}')
print(f'наклон в lg-lg координатах = {s:.3f}')
print(f'равенство объёмов (экстраполяция) при ΔB ≈ '
      f'{(t.OFF_median.iloc[0] - r.intercept) / r.slope / 1073741824 * 100:.1f} % файла')
