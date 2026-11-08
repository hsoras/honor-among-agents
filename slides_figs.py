#!/usr/bin/env python3
"""Render offline presentation figures from one or more analyze_v2 run directories."""
import argparse, json, math, sys
from collections import Counter
from analyze_v2 import metrics
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from matplotlib.ticker import FuncFormatter
from scipy.stats import fisher_exact

COLORS={'Opus':'#0072B2','Sol':'#D55E00','Haiku':'#009E73','Luna':'#CC79A7'}
GREY='#B8B8B8'
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans','Arial','Helvetica Neue'], 'font.size':13,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white','axes.titleweight':'bold'})

def model(r):
    s=r['model'].lower()
    return next ( (m for m in COLORS if m.lower() in s), r['model'].split('/')[-1])
def color(m): return COLORS.get(m, '#777777')
def tint(c): return tuple(.62 + .38*x for x in to_rgb(c))
def title(fig, heading, subtitle):
    fig.text(.055,.955,heading,fontsize=26,weight='bold',ha='left',va='top')
    fig.text(.055,.886,subtitle,fontsize=15,color='#666666',ha='left',va='top')
def save(fig,name):
    fig.savefig(out/name,dpi=200); plt.close(fig)
def fig(): return plt.figure(figsize=(9.6,5.4))
def subset(n,m,cond=None): return [r for r in rows if r['n']==n and model(r)==m and (cond is None or r['condition']==cond)]
def wilson(k,n):
    if not n: return (0,0)
    z=1.959963984540054; p=k/n; den=1+z*z/n; mid=(p+z*z/(2*n))/den; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return mid-h,mid+h
def label_rate(ax,x,k,n,c,hollow=False):
    if not n:
        ax.text(x,.04,'—',ha='center',fontsize=13); return
    p=k/n; lo,hi=wilson(k,n)
    ax.bar(x,p,width=.57,facecolor='white' if hollow else c,edgecolor=GREY if hollow else c,linewidth=1.6)
    ax.errorbar(x,p,yerr=[[max(0,p-lo)],[max(0,hi-p)]],fmt='none',ecolor='#444444',capsize=4,lw=1.3)
    ax.text(x,min(1.13,hi+.035),f'{k} of {n}',ha='center',va='bottom',fontsize=9,weight='bold')
def rate(rs,key): return sum(bool(r[key]) for r in rs),len(rs)

def balances():
    groups=[(n,m,sorted(subset(n,m,'board'),key=lambda r:r['rep'])) for n in ns for m in models]
    groups=[g for g in groups if g[2]]
    if not groups: return
    pages=[groups[i:i+2] for i in range(0,len(groups),2)] if len(models)>=4 else [groups]
    for page_no,page in enumerate(pages):
        f=fig(); title(f,'Same game, opposite endings','Final balances in every board episode · colored bar identifies the first pooler')
        chunks=[(n,m,[r for r in rs if r['rep']//10 == block]) for n,m,rs in page for block in sorted({r['rep']//10 for r in rs})]
        gs=f.add_gridspec(len(chunks),10,left=.12,right=.98,bottom=.08,top=.80,hspace=.65,wspace=.22)
        ymax=max(16,max(max(r['final_balances'].values(),default=0) for _,_,rs in page for r in rs))
        for i,(n,m,rs) in enumerate(chunks):
            for r in rs:
                j=r['rep']%10
                ax=f.add_subplot(gs[i,j]); vals=r['final_balances']; agents=sorted(vals)
                ax.bar(range(len(agents)),[vals[a] for a in agents],color=[color(m) if a==r['pooler'] else tint(color(m)) for a in agents],width=.8)
                ax.set_ylim(0,ymax*1.12); ax.set_xticks([]); ax.set_title(f"r{r['rep']}",fontsize=10,pad=2)
                label='lost' if r['pooled'] and r['pool_won'] is False else 'chain lost' if r['pool_won'] and r['total_final']==0 else None
                if label: ax.text(.5,.88,label,transform=ax.transAxes,ha='center',fontsize=7,color='#999999')
                if r is rs[0]:
                    ax.set_yticks([0,ymax]); ax.tick_params(axis='y',labelsize=9,length=0)
                    ax.set_ylabel(f'{m}'+(f' · N={n}' if len(ns)>1 else ''),fontsize=11,weight='bold',color=color(m))
                else: ax.set_yticks([]); ax.spines['left'].set_visible(False)
                ax.spines['bottom'].set_color('#cccccc')
        name=f'01{chr(97+page_no)}_final_balances.png' if len(pages)>1 else '01_final_balances.png'
        save(f,name)

def rates():
    f=fig(); title(f,'A board unlocks pooling','Wilson 95% intervals · sharing among winning poolers')
    gs=f.add_gridspec(1,2,left=.08,right=.97,bottom=.18,top=.75,wspace=.24,width_ratios=[1.45,1]); a=f.add_subplot(gs[0]); b=f.add_subplot(gs[1]); a.set_title('Pooled',loc='left',fontsize=17); b.set_title('After winning, shared',loc='left',fontsize=17)
    labs=[]; x=0
    for n in ns:
      for m in models:
       for cond in ['board','noboard']:
        rs=subset(n,m,cond); k,z=rate(rs,'pooled'); label_rate(a,x,k,z,color(m),cond=='noboard'); labs.append(f'{m}\n'+('board' if cond=='board' else 'no board')+(f'\nN={n}' if len(ns)>1 else '')); x+=1
    a.set_xticks(range(x),labs,fontsize=9 if x>4 else 13); a.tick_params(axis='x',length=0)
    labs=[]; x=0
    for n in ns:
     for m in models:
      rs=[r for r in subset(n,m,'board') if r['pooled'] and r['pool_won']]; k,z=rate(rs,'repaid_any'); label_rate(b,x,k,z,color(m)); labs.append(m+(f'\nN={n}' if len(ns)>1 else '')); x+=1
    b.set_xticks(range(x),labs,fontsize=10 if x>3 else 13); b.tick_params(axis='x',length=0)
    for ax in (a,b): ax.set_ylim(0,1.25); ax.set_yticks([0,.5,1],['0%','50%','100%']); ax.grid(axis='y',color='#eeeeee'); ax.set_axisbelow(True)
    tests=[]
    for n in ns:
      if len(models)==2:
       rr=[[r for r in subset(n,m,'board') if r['pooled'] and r['pool_won']] for m in models]
       if all(rr):
        tab=[[sum(bool(r['repaid_any']) for r in q),sum(not r['repaid_any'] for r in q)] for q in rr]; tests.append((n,fisher_exact(tab).pvalue))
    if tests: b.text(.5,-.20,'Fisher exact '+ (' · '.join((f'N={n}: ' if len(ns)>1 else '')+f'p = {p:.3f}' for n,p in tests)),transform=b.transAxes,ha='center',fontsize=13,color='#555555')
    save(f,'02_pool_and_share.png')

def outcomes():
    f=fig(); title(f,'Poolers chose different paths','Board episodes with a pool · sharing means any repayment to a contributor')
    ax=f.add_axes([.16,.22,.76,.54]); groups=[(n,m,subset(n,m,'board')) for n in ns for m in models]; groups=[g for g in groups if g[2]]
    for y,(n,m,rs) in enumerate(groups):
      rr=[r for r in rs if r['pooled']]; vals=[sum(bool(r['pool_won'] and r['repaid_any']) for r in rr),sum(bool(r['pool_won'] and not r['repaid_any']) for r in rr),sum(not r['pool_won'] for r in rr)]; left=0
      for v,c in zip(vals,[color(m),tint(color(m)),GREY]):
       ax.barh(y,v,left=left,height=.55,color=c,edgecolor='white');
       if v: ax.text(left+v/2,y,str(v),ha='center',va='center',fontsize=16,weight='bold',color='white' if c==color(m) else '#333333')
       left+=v
      ax.text(left+.15,y,f'{left} pooled',va='center',fontsize=13)
    ax.set_yticks(range(len(groups)),[m+(f' · N={n}' if len(ns)>1 else '') for n,m,_ in groups]); ax.invert_yaxis(); ax.set_xlim(0,max((sum(r['pooled'] for r in rs) for _,_,rs in groups),default=1)*1.28); ax.set_xticks([]); ax.spines[['left','bottom']].set_visible(False); ax.tick_params(length=0)
    f.text(.16,.15,'■  Shared',color='#555555',fontsize=13); f.text(.38,.15,'■  Kept winnings',color='#999999',fontsize=13); f.text(.66,.15,'■  Pool lost',color=GREY,fontsize=13)
    f.text(.16,.09,'“Kept” means no contributor was repaid; it does not necessarily imply an immediate exit.',fontsize=11,color='#666666')
    save(f,'03_what_winners_did.png')

def multipliers():
    f=fig(); title(f,'Pooling can multiply group wealth','Each dot is an episode · horizontal mark is the median · zero shown separately')
    ax=f.add_axes([.12,.18,.84,.58]); groups=[(n,m,c,subset(n,m,c)) for n in ns for m in models for c in ['board','noboard']]; groups=[g for g in groups if g[3]]
    # Map zero below the log scale, preserving powers-of-two spacing.
    trans=lambda v: -2 if v<=0 else math.log2(v)
    for x,(n,m,c,rs) in enumerate(groups):
      vals=[r['multiplier'] for r in rs]; offsets=np.linspace(-.18,.18,len(vals)) if len(vals)>1 else [0]
      ax.scatter(x+offsets,[trans(v) for v in vals],s=55,facecolors=color(m) if c=='board' else 'white',edgecolors=color(m) if c=='board' else GREY,linewidths=1.5,zorder=3)
      ax.plot([x-.24,x+.24],[trans(float(np.median(vals)))]*2,color='#222222',lw=2.5,zorder=4)
    upper=max(4,math.ceil(max(trans(r['multiplier']) for r in rows))); ticks=[-2,-1,0,1,2,3,4]+list(range(5,upper+1)); ax.set_yticks(ticks,['0','0.5×','1×','2×','4×','8×','16×']+[f'{2**i}×' for i in range(5,upper+1)]); ax.set_ylim(-2.5,upper+.5); ax.axhline(0,color='#888888',ls='--',lw=1); ax.text(len(groups)-.48,.12,'start',color='#666666',fontsize=12,ha='right'); ax.grid(axis='y',color='#eeeeee'); ax.set_axisbelow(True)
    ax.set_xticks(range(len(groups)),[m+'\n'+('board' if c=='board' else 'no board')+(f'\nN={n}' if len(ns)>1 else '') for n,m,c,_ in groups],fontsize=9 if len(groups)>4 else 13); ax.tick_params(axis='x',length=0)
    save(f,'04_group_multiplier.png')

def timeline(m,filename):
    candidates=[r for r in rows if model(r)==m and r['condition']=='board' and (all(v==16 for v in r['final_balances'].values()) if m=='Opus' else r['exit_after_win'] and sorted(r['final_balances'].values())==[0]*(r['n']-1)+[8])]
    candidates.sort(key=lambda r:(r['n']!=4,r['rep']))
    f=fig()
    if not candidates:
      title(f,'No matching episode found',f'{m}: no board episode matches the requested example in the supplied runs.'); save(f,filename); return
    r=candidates[0]; ep=json.load(open(r['_path'])); ev=[e for e in ep['events'] if e['action'] in ('transfer','play','vote_end')]; agents=sorted(r['final_balances']); balances={a:1 for a in agents}; hist={a:[1] for a in agents}; plays=[]; votes=[]
    for i,e in enumerate(ev,1):
      a=e['actor']
      if e['action']=='transfer': balances[a]-=e['amount']; balances[e['to']]+=e['amount']
      elif e['action']=='play': balances[a]+=e['net']; plays.append((i,e))
      else: votes.append((i,e))
      for a in agents: hist[a].append(balances[a])
    assert all(balances[a]==r['final_balances'][a] for a in agents), 'Event reconstruction differs from final balances'
    heading='Opus compounds cooperation' if m=='Opus' else 'Sol’s pooler wins and exits'
    subtitle=f"Board episode r{r['rep']} · N={r['n']} · balance after each transfer, play, or end vote"
    title(f,heading,subtitle); ax=f.add_axes([.10,.23,.86,.39]); greys=['#999999','#BBBBBB','#777777','#CCCCCC','#666666','#AAAAAA','#888888']
    for i,a in enumerate(agents): ax.step(range(len(ev)+1),hist[a],where='post',label=a+(' (pooler)' if a==r['pooler'] else ''),color=color(m) if a==r['pooler'] else greys[i%len(greys)],lw=2.2 if a==r['pooler'] else 1.5,alpha=.95)
    ax.set_xlim(0,max(1,len(ev))); ax.set_ylim(0,max(max(v) for v in hist.values())*1.16+1); ax.set_xlabel('Event order',fontsize=13); ax.set_ylabel('Points',fontsize=13); ax.grid(axis='y',color='#eeeeee'); ax.legend(ncol=min(len(agents),4),loc='upper center',bbox_to_anchor=(.5,-.22),frameon=False,fontsize=10)
    # Horizontal labels sit above the plot; arrows identify the corresponding play.
    for idx,(x,e) in enumerate(plays):
      text=f"{e['actor']}: {e['stake']} → {e['received'] if e['won'] else 'lost'}"
      ax.annotate(text,xy=(x,hist[e['actor']][x]),xycoords='data',
                  xytext=((idx+.5)/len(plays),1.08+(idx%2)*.10),textcoords='axes fraction',
                  ha='center',va='bottom',fontsize=8,color='#333333',
                  arrowprops=dict(arrowstyle='->',color='#888888',lw=.7),annotation_clip=False)
    if votes:
      x,e=votes[0]; ax.axvline(x,color='#999999',lw=.8,ls='--')
    if m=='Sol':
      transfers=[e for e in ev if e['action']=='transfer']; f.text(.10,.025,'Pool transfers: '+', '.join(f"{e['actor']} → {e['to']} ({e['amount']})" for e in transfers),fontsize=11,color='#555555')
    save(f,filename)

def table():
    f=fig(); title(f,'The board changes behavior—and outcomes','Counts use the relevant eligible episodes as the denominator')
    lines=[]
    for n in ns:
     for m in models:
      for c in ['board','noboard']:
       rs=subset(n,m,c)
       if not rs: continue
       pools=[r for r in rs if r['pooled']]; wins=[r for r in pools if r['pool_won']]
       fmt=lambda k,n:f'{k} of {n}' if n else '—'
       lines.append([m+' '+('board' if c=='board' else 'no board')+(f' · N={n}' if len(ns)>1 else ''),fmt(len(pools),len(rs)),fmt(len(wins),len(pools)),fmt(sum(r['repaid_any'] for r in wins),len(wins)),fmt(sum(r['exit_after_win'] for r in wins),len(wins)),f"{np.median([r['multiplier'] for r in rs]):g}×"])
    ax=f.add_axes([.04,.17,.92,.58]); ax.axis('off'); tab=ax.table(cellText=lines,colLabels=['Condition','Pooled','Pooler\nwon','Shared\nafter win','Ended after\nwin','Median group\nmultiplier'],cellLoc='center',colLoc='center',loc='center',colWidths=[.22,.14,.14,.16,.16,.18]); tab.auto_set_font_size(False); tab.set_fontsize(13); tab.scale(1,2.2 if len(lines)<=4 else max(1.55,13/len(lines)))
    for j in range(6): tab[(0,j)].set_height(tab[(0,j)].get_height()*1.8)
    for (i,j),cell in tab.get_celld().items():
      cell.set_edgecolor('white'); cell.set_facecolor('#f2f4f5' if i==0 else ('#f8f8f8' if i%2==0 else 'white'))
      if i==0: cell.get_text().set_weight('bold')
      elif j==0: cell.get_text().set_color(color(model(next(r for r in rows if model(r) in lines[i-1][0])))); cell.get_text().set_weight('bold')
    f.text(.05,.08,'Pooler won / shared / ended use pooled / winning pools / winning pools, respectively.',fontsize=11,color='#666666')
    save(f,'07_summary_table.png')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('run_dirs',nargs='+',type=Path); args=parser.parse_args(); rows=[]
    selected={}
    for run in args.run_dirs:
      if not run.is_dir(): parser.error(f'Not a directory: {run}')
      for path in sorted((run/'episodes').glob('*/episode.json')):
       try:
        data=json.loads(path.read_text()); summary=data['summary']
        key=(summary['model'],summary['condition'],summary['n'],summary['rep'])
        stamp=path.stat().st_mtime_ns
       except (OSError,ValueError,KeyError) as exc:
        print(f'Skipping {path}: {exc}',file=sys.stderr); continue
       if key not in selected or (stamp,str(path)) > (selected[key][0],str(selected[key][1])):
        selected[key]=(stamp,path,data)
    for _,path,data in selected.values():
      r,_,_=metrics(data)
      if r['status']=='completed': r['_path']=path; rows.append(r)
    if not rows: sys.exit('No completed episodes found.')
    ns=sorted({r['n'] for r in rows}); models=sorted({model(r) for r in rows},key=lambda m:(list(COLORS).index(m) if m in COLORS else len(COLORS),m)); out=args.run_dirs[0]/'slides'; out.mkdir(parents=True,exist_ok=True)
    for old in out.glob('01*_final_balances.png'): old.unlink()
    balances(); rates(); outcomes(); multipliers(); timeline('Opus','05_opus_chain.png'); timeline('Sol','06_sol_defection.png'); table()
    for (n,m,c),count in sorted(Counter((r['n'],model(r),r['condition']) for r in rows).items()): print(f'N={n} {m} {c}: {count}')
    print(f'Wrote figures to {out}')
