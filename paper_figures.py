"""Print-sized figures from the retained episode manifest. No API calls."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from analyze_v2 import wilson
from paper_data import load

BASE = Path(__file__).resolve().parent
OUT = BASE / 'output/pdf/figures'
OUT.mkdir(parents=True, exist_ok=True)
ROWS = load()
(BASE / 'tmp/pdfs/paper_data.json').write_text(json.dumps(ROWS, indent=2))
COLORS = {'Opus 5.5': '#0072B2', 'Fable 5.1': '#332288', 'Sol 6.1': '#D55E00',
          'Astra 6': '#882255', 'Gemini 4 Argon': '#56B4E9', 'Sol 5.6': '#B27800',
          'Haiku 5.5': '#00836C', 'Luna 6': '#A85A83'}
MODELS = list(COLORS)
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.titleweight': 'bold',
    'axes.labelsize': 8, 'xtick.labelsize': 7, 'ytick.labelsize': 8,
    'figure.facecolor': 'white', 'savefig.facecolor': 'white', 'pdf.fonttype': 42})

def cell(name, variant='main', condition='board'):
    return [r for r in ROWS if r['name'] == name and r['variant'] == variant and r['condition'] == condition]

def save(fig, name):
    fig.savefig(OUT / (name + '.png'), dpi=320, bbox_inches='tight', pad_inches=.035)
    fig.savefig(OUT / (name + '.pdf'), bbox_inches='tight', pad_inches=.035)
    plt.close(fig)

def rate(ax, k, n, y, color, hollow=False, offset=0):
    if not n:
        return
    lo, hi = wilson(k, n)
    p = k/n
    ax.errorbar(p, y, xerr=np.array([[max(0,p-lo)], [max(0,hi-p)]]), fmt='o', ms=4.3,
        color=color, mfc='white' if hollow else color, capsize=2, lw=1, zorder=3)
    ax.text(1.10 + offset, y, f'{k}/{n}', color=color, va='center', fontsize=7.2,
            fontweight='bold', clip_on=False)

def rate_axes(ax, names):
    ax.set_yticks(range(len(names)), names)
    ax.set_ylim(len(names)-.6, -.65)
    ax.set_xlim(-.04, 1.04)
    ax.set_xticks([0, .5, 1], ['0%', '50%', '100%'])
    ax.grid(axis='x', color='#e3e3e3', lw=.6)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0)

def game():
    f, ax = plt.subplots(figsize=(6.5, 1.45))
    ax.set_xlim(0, 10); ax.set_ylim(0, 3); ax.axis('off')
    for i in range(4):
        x = .15 + i*2.48
        ax.add_patch(FancyBboxPatch((x,2.08),2.18,.65,boxstyle='round,pad=0.04',
                     ec='#c5ced4',fc='#f6f8f9',lw=.7))
        ax.text(x+1.09,2.41,f'Agent {i+1}  ·  1 point',ha='center',va='center',fontsize=9)
    ax.text(5,1.55,'Pool 4 points  →  80% chance of 8  →  pass to an unplayed agent',
            ha='center',fontsize=10,weight='bold')
    ax.text(5,1.02,'Stake s  →  receive 2s with probability s / (s + 1); otherwise receive 0',
            ha='center',fontsize=9)
    ax.text(5,.48,'One gamble per agent  ·  Transfers cannot be undone  ·  Promises are not enforced',
            ha='center',fontsize=8.5,color='#444444')
    ax.text(5,-.02,'Main goal: maximize your own final points',ha='center',fontsize=9,weight='bold')
    f.subplots_adjust(left=0,right=1,bottom=.05,top=1)
    save(f,'01_game')

def board():
    f, axes = plt.subplots(1,2,figsize=(6.5,2.65),gridspec_kw={'width_ratios':[1.05,1]})
    a,b=axes
    for i,m in enumerate(MODELS):
        rs=cell(m)
        rate(a,sum(r['pooled'] for r in rs),len(rs),i-.12,COLORS[m])
        rs=cell(m,condition='noboard')
        # No-board counts are shown in the caption to avoid overlapping labels.
        lo,hi=wilson(0,len(rs))
        a.errorbar(0,i+.14,xerr=[[0],[hi]],fmt='o',ms=3.6,mfc='white',color='#8c8c8c',capsize=1.5,lw=.7)
    rate_axes(a,MODELS)
    names=MODELS[:4]
    for i,m in enumerate(names):
        wins=[r for r in cell(m) if r['pool_won']]
        rate(b,sum(r['contributors_whole'] for r in wins),len(wins),i,COLORS[m])
    rate_axes(b,names)
    a.set_title('A. Full pooling',loc='left',fontsize=9,pad=7)
    b.set_title('B. Paid back after a win',loc='left',fontsize=9,pad=7)
    a.set_xlabel('Filled: board  ·  Open gray: no board')
    b.set_xlabel('Every contributor finishes with ≥1 point')
    f.subplots_adjust(left=.16,right=.92,bottom=.17,top=.86,wspace=.87)
    save(f,'02_pooling_repayment')

def timelines():
    f,axes=plt.subplots(1,2,figsize=(6.5,2.5))
    for ax,m,rep in zip(axes,['Sol 6.1','Opus 5.5'],[0,3]):
        r=next(r for r in cell(m) if r['rep']==rep)
        data=json.loads((BASE/r['path']).read_text())
        events=[e for e in data['events'] if e['action'] in ('transfer','play','vote_end')]
        balances={f'agent_{i}':1 for i in range(1,5)}
        hist={a:[1] for a in balances}; plays=[]; votes=[]
        for i,e in enumerate(events,1):
            if e['action']=='transfer':
                balances[e['actor']]-=e['amount'];balances[e['to']]+=e['amount']
            elif e['action']=='play':
                balances[e['actor']]+=e['net'];plays.append((i,e))
            else:votes.append(i)
            for a in hist:hist[a].append(balances[a])
        assert balances==r['final_balances']
        grays=['#888888','#aaaaaa','#666666','#cccccc']
        for i,a in enumerate(hist):
            ax.step(range(len(events)+1),hist[a],where='post',lw=1.5 if a==r['pooler'] else .85,
                    color=COLORS[m] if a==r['pooler'] else grays[i],label=f'A{i+1}')
        for x,e in plays:
            ax.plot(x,hist[e['actor']][x],marker='o',ms=3,color=COLORS[m])
        if m=='Sol 6.1':
            ax.annotate('4 → 8; keeps the pot',xy=(4,8),xytext=(.15,.81),textcoords='axes fraction',
                        fontsize=7,arrowprops={'arrowstyle':'->','lw':.7,'color':'#666666'})
            ax.axvline(votes[0],color='#888888',ls=':',lw=.8)
            ax.set_ylim(-.5,10.8);ax.set_yticks([0,4,8])
        else:
            ax.text(.03,.88,'4 → 8 → 16 → 32 → 64',transform=ax.transAxes,fontsize=7)
            ax.set_ylim(-2,75);ax.set_yticks([0,16,32,64])
        ax.set_title(f'{m} · repetition {rep}',loc='left',fontsize=9)
        ax.set_xlabel('Event order');ax.set_ylabel('Points')
        ax.grid(axis='y',color='#e8e8e8',lw=.6)
        ax.legend(loc='upper center',bbox_to_anchor=(.5,-.27),ncol=4,frameon=False,
                  handlelength=1,columnspacing=.8,fontsize=7)
    f.subplots_adjust(left=.08,right=.99,bottom=.27,top=.87,wspace=.3)
    save(f,'03_timelines')

def controls():
    f,axes=plt.subplots(1,2,figsize=(6.5,2.45))
    for ax,names,variants,title in zip(axes,[MODELS[:4],['Opus 5.5','Sol 6.1']],
            [('main','noobj'),('main','novote')],['A. Remove the individual goal','B. Remove the end vote']):
        for i,m in enumerate(names):
            for j,v in enumerate(variants):
                wins=[r for r in cell(m,v) if r['pool_won']]
                # Counts are printed in two right-side columns.
                rate(ax,sum(r['contributors_whole'] for r in wins),len(wins),i+(-.13 if j==0 else .13),
                     COLORS[m],j==0)
        rate_axes(ax,names)
        ax.set_title(title,loc='left',fontsize=9)
        ax.set_xlabel('Open: main  ·  Filled: control')
    f.subplots_adjust(left=.13,right=.92,bottom=.22,top=.83,wspace=.8)
    save(f,'04_controls')

def balances():
    f,axes=plt.subplots(4,20,figsize=(6.5,3.6))
    for i,(m,v) in enumerate([('Opus 5.5','main'),('Sol 6.1','main'),('Opus 5.5','noobj'),('Sol 6.1','noobj')]):
        for j,r in enumerate(sorted(cell(m,v),key=lambda r:r['rep'])):
            ax=axes[i,j]
            vals=[r['final_balances'][f'agent_{k}'] for k in range(1,5)]
            assert max(vals)<=16,(m,v,j,vals)
            ax.bar(range(4),vals,color=[COLORS[m] if f'agent_{k+1}'==r['pooler'] else '#aecbdb' if m.startswith('Opus') else '#f0c4a6' for k in range(4)],width=.8)
            ax.set_ylim(0,17);ax.set_xticks([]);ax.set_yticks([])
            ax.set_title(str(j),fontsize=6,pad=2)
            ax.spines[['left','bottom']].set_visible(False)
        axes[i,0].set_ylabel(m+'\n'+('Main' if v=='main' else 'No goal'),rotation=0,ha='right',va='center',fontsize=8,labelpad=6,color=COLORS[m])
        axes[i,0].set_yticks([0,16]);axes[i,0].tick_params(axis='y',labelsize=5,length=0,pad=0)
    f.subplots_adjust(left=.16,right=.995,bottom=.02,top=.92,wspace=.22,hspace=.85)
    save(f,'05_final_balances')

if __name__=='__main__':
    game();board();timelines();controls();balances()
    print('Replayed',len(ROWS),'retained episodes and wrote five figures to',OUT)
