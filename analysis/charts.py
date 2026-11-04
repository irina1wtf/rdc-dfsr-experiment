import pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, NullFormatter
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.edgecolor':'#4b5563','axes.labelcolor':'#1f2937','xtick.color':'#374151','ytick.color':'#374151'})
DARK='#1b5e20'; MID='#2e7d32'; LIGHT='#81c784'; PALE='#c8e6c9'; GRID='#e8f0e8'; GREY='#6b7280'
d=pd.read_csv('../data/results_v2.csv'); d=d[d.Status=='OK']
lv=sorted(d.ChangeBytes.unique()); x=np.arange(len(lv))
lab=['1 Б','4 КиБ','64 КиБ','1 МиБ','10 МиБ','100 МиБ','25 %','50 %','75 %']
on=d[d.RDCConfigured=='ON']; off=d[d.RDCConfigured=='OFF']
med_on=on.groupby('ChangeBytes').Delta.median().reindex(lv)
med_off=off.groupby('ChangeBytes').Delta.median().reindex(lv)
sp=lambda v: f'{v:,.0f}'.replace(',',' ')
rng=np.random.default_rng(3)
def style(ax):
    for s in ['top','right']: ax.spines[s].set_visible(False)
    ax.grid(axis='y',color=GRID,lw=1); ax.set_axisbelow(True)
def bytes_fmt(v,_):
    for u,k in [('ГБ',1e9),('МБ',1e6),('КБ',1e3)]:
        if v>=k: return f'{v/k:g} {u}'
    return f'{v:g} Б'

# ---- Рис. 8: объём передачи
fig,ax=plt.subplots(figsize=(6.6,5.6),dpi=220)
xo=np.array([lv.index(c) for c in off.ChangeBytes]); xn=np.array([lv.index(c) for c in on.ChangeBytes])
ax.scatter(xo+rng.uniform(-.12,.12,len(xo)), off.Delta, s=22, marker='s', color=PALE, edgecolor=DARK, lw=.6, zorder=3, label='RDC отключён (отдельные опыты, ≈ размер файла)')
ax.plot(x, med_on.values, color=MID, lw=2, zorder=2, label='RDC включён, медиана')
ax.scatter(xn+rng.uniform(-.12,.12,len(xn)), on.Delta, s=22, color=DARK, alpha=.75, zorder=4, label='RDC включён (отдельные опыты)')
ax.set_yscale('log'); ax.set_ylim(5e3,4e9)
ax.yaxis.set_major_formatter(FuncFormatter(bytes_fmt)); ax.yaxis.set_minor_formatter(NullFormatter())
ax.set_xticks(x,lab,rotation=35,ha='right'); ax.set_xlim(-.5,len(lv)-.5)
ax.set_ylabel('Передано за цикл репликации'); ax.set_xlabel('Объём изменённых данных')
ax.annotate('11,9 КБ против 1,075 ГБ\n(в ≈ 90 000 раз меньше)', xy=(0,med_on.values[0]), xytext=(0.25,2.5e6),
            fontsize=9.5, color=DARK, arrowprops=dict(arrowstyle='-',color=DARK,lw=.8))
style(ax)
ax.legend(loc='upper center', bbox_to_anchor=(0.5,-0.30), ncol=1, frameon=False, fontsize=9.5)
fig.tight_layout(); fig.savefig('../figures/fig2_transfer.png', bbox_inches='tight', pad_inches=0.08); plt.close()

# ---- Рис. 9: выигрыш
ratio=(med_off/med_on).values
def fmt(v):
    if v>=10000: return sp(float(f'{v:.3g}'))
    if v>=100: return sp(v)
    if v>=10: return f'{v:.1f}'.replace('.',',')
    return f'{v:.2f}'.replace('.',',')
fig,ax=plt.subplots(figsize=(6.6,5.2),dpi=220)
cols=[DARK if r>=10 else LIGHT for r in ratio]
ax.bar(x,ratio,color=cols,width=.62,zorder=3)
ax.axhline(10,color=GREY,ls='--',lw=1,zorder=2)
ax.set_yscale('log'); ax.set_ylim(.8,4e5)
for xi,v in zip(x,ratio): ax.text(xi,v*1.3,fmt(v),ha='center',va='bottom',fontsize=9,color='#1f2937')
ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_: sp(v))); ax.yaxis.set_minor_formatter(NullFormatter())
ax.set_xticks(x,lab,rotation=35,ha='right'); ax.set_ylabel('Выигрыш, раз'); ax.set_xlabel('Объём изменённых данных')
style(ax)
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
ax.legend(handles=[Patch(color=DARK,label='выигрыш ≥ 10 раз (Н1 выполняется)'),Patch(color=LIGHT,label='выигрыш < 10 раз'),
          Line2D([],[],color=GREY,ls='--',label='порог Н1: 10 раз')],
          loc='upper center',bbox_to_anchor=(0.5,-0.32),ncol=1,frameon=False,fontsize=9.5)
fig.tight_layout(); fig.savefig('../figures/fig4_gain.png', bbox_inches='tight', pad_inches=0.08); plt.close()

# ---- Рис. 10: накладные расходы (две панели вместо второй оси)
o=on.copy(); o['ov']=o.Delta-o.ChangeBytes
med_ov=o.groupby('ChangeBytes').ov.median().reindex(lv)/1024
pct=(o.groupby('ChangeBytes').ov.median()/o.groupby('ChangeBytes').ChangeBytes.first()*100).reindex(lv)
fig,(a1,a2)=plt.subplots(1,2,figsize=(7.6,3.9),dpi=220,gridspec_kw=dict(width_ratios=[1.6,1]))
xm=np.array([lv.index(c) for c in o.ChangeBytes])
a1.plot(x,med_ov.values,color=MID,lw=2,zorder=2,label='медиана')
a1.scatter(xm+rng.uniform(-.12,.12,len(xm)),o.ov/1024,s=20,color=DARK,alpha=.7,zorder=3,label='отдельные опыты')
a1.set_yscale('log'); a1.set_ylim(5,2e4)
a1.yaxis.set_major_formatter(FuncFormatter(lambda v,_: sp(v))); a1.yaxis.set_minor_formatter(NullFormatter())
a1.set_xticks(x,lab,rotation=35,ha='right'); a1.set_ylabel('Сверх объёма изменения, КиБ')
a1.set_title('а) абсолютная величина',fontsize=10.5,color='#1f2937',loc='left')
style(a1); a1.legend(loc='upper left',frameon=False,fontsize=9)
k=list(range(3,len(lv)))
a2.bar(np.arange(len(k)),pct.values[3:],color=[DARK]+[MID]*5,width=.6,zorder=3)
for i,v in enumerate(pct.values[3:]): a2.text(i,v+.05,f'{v:.2f}'.replace('.',','),ha='center',va='bottom',fontsize=9)
a2.set_xticks(np.arange(len(k)),[lab[i] for i in k],rotation=35,ha='right'); a2.set_ylim(0,2.8)
a2.yaxis.set_major_formatter(FuncFormatter(lambda v,_: f'{v:.1f}'.replace('.',',')))
a2.set_ylabel('Доля от объёма изменения, %')
a2.set_title('б) относительная величина',fontsize=10.5,color='#1f2937',loc='left')
style(a2)
fig.tight_layout(rect=(0,0.05,1,1))
fig.text(0.5,0.03,'Объём изменённых данных',ha='center',fontsize=11,color='#1f2937'); fig.savefig('../figures/fig3_overhead.png', bbox_inches='tight', pad_inches=0.08); plt.close()
print('ok')
