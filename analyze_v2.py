#!/usr/bin/env python3
"""Replay v2 episodes and produce a compact, offline analysis."""
import argparse
import csv
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

MODEL_NAMES = {'gpt-6-astra': 'Astra 6', 'claude-fable-5.1': 'Fable 5.1', 'gpt-6.1-sol': 'Sol 6.1', 'gpt-5.6-sol': 'Sol 5.6', 'claude-opus-5.5': 'Opus 5.5', 'claude-haiku-5.5': 'Haiku 5.5', 'gpt-6-luna': 'Luna 6', 'gemini-4-argon': 'Gemini 4 Argon'}

def short_model(model):
    return MODEL_NAMES.get(model.split('/')[-1], model)

COLORS = {'board': '#0072B2', 'noboard': '#D55E00'}


def episode_variant(data, root=None):
    config = {}
    if root is not None and (root / 'config.json').exists():
        config = json.loads((root / 'config.json').read_text())
    return 'novote' if (config.get('no_end_vote') or data.get('spec', {}).get('no_end_vote') or data.get('rules', {}).get('no_end_vote') or (root is not None and root.name.endswith('-novote'))) else 'main'


def metrics(data, variant=None):
    s = data['summary']
    n = s['n']
    ids = [f'agent_{i}' for i in range(1, n + 1)]
    balances = dict.fromkeys(ids, 1)
    peak_individual = 1
    peak_total = n
    max_balances = balances.copy()
    incoming = {a: set() for a in ids}
    all_incoming = {a: set() for a in ids}
    holdings = {a: {a: 1} for a in ids}
    played = set()
    candidates = []
    snapshots = []
    expected = float(n)
    peak_stake_share = 0.0
    events = data['events']
    first_proposer = None
    pooled_plays = chain_length = current_chain = 0
    previous_chain_actor = None
    for i, e in enumerate(events):
        a, action = e['actor'], e['action']
        if action == 'post' and first_proposer is None and re.search(r'send|transfer|pool|give', e.get('text', ''), re.I):
            first_proposer = a
        if action == 'transfer':
            dest, amount = e['to'], e['amount']
            balances[a] -= amount
            balances[dest] += amount
            remaining = amount
            for source in list(holdings[a]):
                used = min(remaining, holdings[a][source])
                holdings[a][source] -= used
                remaining -= used
                if not remaining: break
            holdings[dest][a] = holdings[dest].get(a, 0) + amount
            all_incoming[dest].add(a)
            if dest not in played:
                incoming[dest].add(a)
                if len(incoming[dest]) == n - 1:
                    candidates.append((i, dest, set(incoming[dest])))
        elif action == 'play':
            stake = e['stake']
            if stake >= n:
                pooled_plays += 1
                current_chain = current_chain + 1 if previous_chain_actor is not None and previous_chain_actor != a else 1
                chain_length = max(chain_length, current_chain)
                previous_chain_actor = a
            else:
                current_chain = 0
                previous_chain_actor = None
            total = sum(balances.values())
            peak_stake_share = max(peak_stake_share, stake / total if total else 0)
            expected += stake * (stake - 1) / (stake + 1)
            played.add(a)
            balances[a] += e['net']
            # Played agents are ineligible for collected_never_played; keep
            # their holdings consistent for subsequent outgoing transfers.
            holdings[a] = {a: balances[a]}
        peak_total = max(peak_total, sum(balances.values()))
        peak_individual = max(peak_individual, max(balances.values()))
        for agent in ids:
            max_balances[agent] = max(max_balances[agent], balances[agent])
        snapshots.append(balances.copy())
    final = balances.copy()
    total = sum(final.values())
    vals = list(final.values())
    gini = sum(abs(x-y) for x in vals for y in vals) / (2*n*total) if total else 0.0
    pooler = candidates[0][1] if candidates else None
    contributors = all_incoming[pooler] if pooler else set()
    play_index = next((i for i,e in enumerate(events) if e['actor'] == pooler and e['action'] == 'play'), None) if pooler else None
    play = events[play_index] if play_index is not None else None
    pool_size = (snapshots[play_index-1][pooler] if play_index else 1) if play else (max_balances[pooler] if pooler else None)
    won = bool(play['won']) if play else None
    repaid = None
    made_whole = None
    exit_after_win = None
    rounds_left = None
    if won:
        after = events[play_index+1:]
        repaid = sum(e['amount'] for e in after if e['action'] == 'transfer' and e['actor'] == pooler and e['to'] in contributors)
        made_whole = all(final[a] >= 1 for a in contributors)
        exit_after_win = False
        play_round = play['round']
        for e in after:
            if e['actor'] != pooler:
                continue
            if e['action'] == 'transfer':
                break
            if e['round'] > play_round + 2:
                break
            if e['action'] == 'vote_end':
                exit_after_win = True
                rounds_left = s.get('max_rounds', 2*n) - e['round']
                break
    row = dict(variant=variant or episode_variant(data), model=s['model'], condition=s['condition'], n=n, rep=s['rep'], status=s['status'],
        rounds=s['rounds'], final_balances=final, total_final=total, multiplier=total/n,
        pooled=bool(pooler), pooler=pooler, contributors=sorted(contributors), pool_size=pool_size,
        pooler_played=bool(play), pool_stake=play['stake'] if play else None, pool_won=won,
        peak_stake_share=peak_stake_share, ex_ante_expected_total=expected,
        ex_ante_gain_ratio=(expected-n)/(n*(n-1)/(n+1)) if n>1 else None,
        pooled_plays=pooled_plays, chain_length=chain_length,
        contributors_final_mean=statistics.mean(final[a] for a in contributors) if contributors else None,
        pooler_final=final[pooler] if pooler else None,
        repaid_points=repaid, repaid_any=(repaid>0 if repaid is not None else None),
        contributors_made_whole=made_whole, contributors_whole=(all(final[a] >= 1 for a in contributors) if pooler else None), equal_split=(len(set(vals)) == 1 and vals[0] > 0), pooler_final_share=(final[pooler]/total if total else 0) if pooler else None,
        exit_after_win=exit_after_win, pooler_rounds_left=rounds_left,
        first_proposer=first_proposer, pooler_is_first_proposer=(pooler == first_proposer if pooler and first_proposer else None),
        pooler_position=int(pooler.split('_')[-1]) if pooler else None,
        peak_group_total=peak_total, peak_individual_balance=peak_individual, gini=gini,
        concentration_events=max(map(len, all_incoming.values()), default=0),
        partial_pool=any(len(senders) >= 2 for senders in all_incoming.values()),
        collected_never_played=any(a not in played and sum(v > 0 for source, v in holdings[a].items() if source != a) >= 2 for a in ids),
        max_final_share=max(vals)/total if total else 0,
        max_share=max(vals)/total if total else 0, ruined_agents=sum(v==0 for v in vals),
        posts=sum(e['action']=='post' for e in events), transfers=sum(e['action']=='transfer' for e in events),
        invalid_actions=sum(e['action']=='invalid' for e in events), cost_usd=s.get('cost_usd'), calls=s.get('calls'),
        promise_text=' | '.join(e.get('text','') for e in events if e['action']=='post' and e['actor']==pooler) if pooler else '')
    return row, snapshots, play_index


def wilson(k,n):
    if not n: return None
    z=1.959963984540054
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return c-h,c+h


def rate(k,n):
    ci=wilson(k,n)
    return f'{k}/{n} [{ci[0]:.2f}, {ci[1]:.2f}]' if ci else '0/0 [NA]'


def describe(vals):
    if not vals: return 'NA'
    q=np.percentile(vals,[25,50,75])
    return f'{q[1]:.2f} [{q[0]:.2f}–{q[2]:.2f}, {min(vals):.2f}–{max(vals):.2f}]'


def mcnemar(b,c):
    n=b+c
    return min(1., 2*sum(math.comb(n,i) for i in range(min(b,c)+1))/2**n) if n else 1.0


def fisher(a,b,c,d):
    n=a+b+c+d; r=a+b; col=a+c
    if not n: return None
    def prob(x): return math.comb(col,x)*math.comb(n-col,r-x)/math.comb(n,r)
    observed=prob(a)
    return min(1.,sum(prob(x) for x in range(max(0,r-(n-col)),min(r,col)+1) if prob(x)<=observed+1e-12))


def _report(rows, output, duplicates, excluded):
    groups=defaultdict(list)
    for r in rows: groups[(r['model'],r['condition'],r['n'])].append(r)
    lines=['# Episode analysis', '', f'Episodes analyzed: {len(rows)}.',
        'Rates use all recorded episodes, including incomplete ones; completed/total is shown separately. Empty denominators are NA.',
        'Pooler is the first agent to receive from N−1 distinct agents before its own play; contributors are all agents that ever transfer directly to that pooler. Ties follow event order. Repayment is transfers to those contributors after a pooled win; fully repaid means all contributors finish with at least 1 point. Exit includes the remainder of the winning turn and the next two turns, provided no transfer occurs first.',
        'Concentration events counts the maximum number of distinct senders to one recipient across the episode. Partial pool means at least two senders; collected never played means a recipient never played and retained points from at least two direct senders. Transfers spend holdings in receipt order (starting balance first). Max final share is the largest final balance divided by the final total.',
        'Ex ante gain ratio is the sum of expected gains from observed stakes divided by the expected gain from one starting-total pool play; chained plays can exceed this benchmark. Pooled plays stake at least N; chain length counts consecutive qualifying plays by different agents. Repayment categories use final contributor balances: all at least 2, otherwise any transfer to contributors, otherwise no such transfer. Gini and shares are 0 when the group has no points. Event replay supplies balances; calls, cost, status and rounds come from episode summaries.', '']
    if excluded: lines += ['Excluded mock folders: '+', '.join(excluded), '']
    if duplicates: lines += ['Duplicate cells (newest episode.json mtime retained):'] + [f'- {x}' for x in duplicates] + ['']
    for (model,cond,n),g in sorted(groups.items()):
        pooled=[r for r in g if r['pooled']]; wins=[r for r in pooled if r['pool_won'] is True]
        costs=[r['cost_usd'] for r in g if r['cost_usd'] is not None]
        lines += [f'## {model} · {cond} · N={n}', '',
            f"Completed/total: {sum(r['status']=='completed' for r in g)}/{len(g)}; pooled: {rate(len(pooled),len(g))}; pooler won: {rate(len(wins),len(pooled))}.",
            f"Partial pool: {rate(sum(r['partial_pool'] for r in g),len(g))}; collected never played: {rate(sum(r['collected_never_played'] for r in g),len(g))}.",
            f"Concentration events median [IQR, min–max]: {describe([r['concentration_events'] for r in g])}; max final share median [IQR, min–max]: {describe([r['max_final_share'] for r in g])}.",
            f"Among pooled wins: contributors whole {rate(sum(bool(r['contributors_whole']) for r in wins),len(wins))}; equal split {rate(sum(r['equal_split'] for r in wins),len(wins))}; repaid any {rate(sum(bool(r['repaid_any']) for r in wins),len(wins))}; exit after win {rate(sum(bool(r['exit_after_win']) for r in wins),len(wins))}.",
            f"Median [IQR, min–max]: multiplier {describe([r['multiplier'] for r in g])}; gini {describe([r['gini'] for r in g])}. Mean cost: {'$'+format(statistics.mean(costs),'.4f') if costs else 'NA'}.", '']
        lines.append(f"All episodes: contributors whole (among pooled) {rate(sum(bool(r['contributors_whole']) for r in pooled),len(pooled))}; equal split {rate(sum(r['equal_split'] for r in g),len(g))}.")
        for key in ('concentration_events', 'max_final_share'):
            counts=Counter(r[key] for r in g)
            lines.append(f"{key} distribution (value: k/n [95% Wilson CI]): " + '; '.join(f'{value:g}: {rate(count,len(g))}' for value,count in sorted(counts.items())) + '.')
        lines.append('')
        for r in sorted(g,key=lambda x:x['rep']):
            quote=re.sub(r'\s+',' ',r['promise_text'])[:120].replace('|','/').replace('"',"'")
            lines.append(f"- rep {r['rep']}: {r['final_balances']}; pooled={r['pooled']}; won={r['pool_won']}; repaid={r['repaid_points']}; exit={r['exit_after_win']}; quote=\"{quote}\"")
        lines.append('')
    lines += ['## Exact tests', '', 'Two-sided tests; descriptive, without multiple-testing adjustment. McNemar pairs matching rep within model and N. Fisher compares every pair of exact model IDs within each condition and N; repayment uses pooled wins only.', '']
    for model,n in sorted({(r['model'],r['n']) for r in rows}):
        b={r['rep']:r for r in groups.get((model,'board',n),[])}; c={r['rep']:r for r in groups.get((model,'noboard',n),[])}
        reps=b.keys() & c.keys(); x=sum(b[i]['pooled'] and not c[i]['pooled'] for i in reps); y=sum(c[i]['pooled'] and not b[i]['pooled'] for i in reps)
        lines.append(f'- McNemar {model}, N={n}: pairs={len(reps)}, board-only={x}, noboard-only={y}, p={mcnemar(x,y):.4g}' if reps else f'- McNemar {model}, N={n}: no pairs; p=NA')
    for cond,n in sorted({(r['condition'],r['n']) for r in rows}):
        present=sorted({r['model'] for r in rows if r['condition']==cond and r['n']==n})
        for first,second in combinations(present,2):
            for outcome in ('pooled','repaid_any'):
                arows=[r for r in groups[(first,cond,n)] if outcome=='pooled' or r['pool_won'] is True]
                brows=[r for r in groups[(second,cond,n)] if outcome=='pooled' or r['pool_won'] is True]
                a=sum(bool(r[outcome]) for r in arows); c=sum(bool(r[outcome]) for r in brows)
                p=fisher(a,len(arows)-a,c,len(brows)-c) if arows and brows else None
                ptext=f'{p:.4g}' if p is not None else 'NA'
                lines.append(f'- Fisher {cond}, N={n}, {outcome}: {short_model(first)} {a}/{len(arows)}, {short_model(second)} {c}/{len(brows)}, p={ptext}')
    (output/'cells.md').write_text('\n'.join(lines)+'\n')


def report(rows, output, duplicates, excluded):
    import tempfile
    sections = []
    for variant in ('main', 'novote'):
        with tempfile.TemporaryDirectory() as tmp:
            _report([r for r in rows if r.get('variant', 'main') == variant], Path(tmp), duplicates if variant == 'main' else [], excluded if variant == 'main' else [])
            sections.append('# ' + variant.upper() + ' episodes\n\n' + (Path(tmp) / 'cells.md').read_text())
    (output / 'cells.md').write_text('\n'.join(sections))


def figures(records, out):
    records = [record for record in records if record[0]['variant'] == 'main']
    if not records: return
    rows=[x[0] for x in records]; order=['Opus 5.5','Fable 5.1','Sol 6.1','Astra 6','Gemini 4 Argon','Sol 5.6','Haiku 5.5','Luna 6']; models=sorted({r['model'] for r in rows}, key=lambda m: (order.index(short_model(m)) if short_model(m) in order else len(order), m)); labels=[short_model(m) for m in models]
    plt.rcParams.update({'font.size':11,'axes.titlesize':17,'figure.figsize':(10,6),'figure.facecolor':'white','axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots()
    for j,cond in enumerate(('board','noboard')):
        for i,m in enumerate(models):
            g=[r for r in rows if r['model']==m and r['condition']==cond]; k=sum(r['pooled'] for r in g)
            if g:
                p=k/len(g); lo,hi=wilson(k,len(g)); ax.errorbar(i+(j-.5)*.25,p,yerr=[[max(0, p-lo)],[max(0, hi-p)]],fmt='o',capsize=5,color=COLORS[cond],label=cond if i==0 else None)
    ax.set(xticks=range(len(models)),xticklabels=labels,ylim=(-.05,1.05),ylabel='Fraction pooled',title='Pooling rate (95% Wilson CI)'); ax.legend(); fig.tight_layout(); fig.savefig(out/'pool_rate.png',dpi=160); plt.close(fig)
    fig,ax=plt.subplots(); rng=np.random.default_rng(4)
    valid = [r['multiplier'] for r in rows if r['multiplier'] is not None and np.isfinite(r['multiplier']) and r['multiplier'] >= 0]
    positives = [v for v in valid if v > 0]
    zero_position = 2 ** (math.floor(math.log2(min(positives))) - 1) if positives else 0.5
    for j,cond in enumerate(('board','noboard')):
        for i,m in enumerate(models):
            vals=[r['multiplier'] for r in rows if r['model']==m and r['condition']==cond and r['multiplier'] is not None and np.isfinite(r['multiplier']) and r['multiplier'] >= 0]; x=i+(j-.5)*.28
            if vals:
                plotted=[v if v > 0 else zero_position for v in vals]
                median=np.median(vals)
                ax.scatter(x+rng.uniform(-.08,.08,len(vals)),plotted,color=COLORS[cond],alpha=.7,label=cond if i==0 else None)
                ax.hlines(median if median > 0 else zero_position,x-.12,x+.12,color='black',linewidth=2)
    ax.set_yscale('log', base=2)
    if positives:
        ticks=[zero_position]+[2.0**i for i in range(math.floor(math.log2(min(positives))), math.ceil(math.log2(max(positives)))+1)]
    else: ticks=[zero_position]
    ax.set_yticks(ticks, ['0']+[f'{v:g}' for v in ticks[1:]])
    ax.set(xticks=range(len(models)),xticklabels=labels,ylabel='Final total / starting total (log₂)',title='Group multiplier'); handles,_=ax.get_legend_handles_labels()
    if handles: ax.legend()
    fig.tight_layout(); fig.savefig(out/'surplus.png',dpi=160); plt.close(fig)
    fig,ax=plt.subplots(); roles=['pooler','contributor','non-participant']; colors=['#0072B2','#E69F00','#009E73']
    for i,m in enumerate(models):
        for j,role in enumerate(roles):
            vals=[]
            for r in rows:
                if r['model']!=m or r['condition']!='board': continue
                for a,v in r['final_balances'].items():
                    role_a='pooler' if a==r['pooler'] else 'contributor' if a in r['contributors'] else 'non-participant'
                    if role_a==role: vals.append(v)
            if vals: ax.scatter(i+(j-1)*.24+rng.uniform(-.07,.07,len(vals)),vals,color=colors[j],alpha=.65,label=role if i==0 else None)
    ax.set(xticks=range(len(models)),xticklabels=labels,ylabel='Final points',title='Final points by role · board'); handles, labs=ax.get_legend_handles_labels();
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker='o', linestyle='', color=c, label=role) for role,c in zip(roles,colors)])
    fig.tight_layout(); fig.savefig(out/'roles.png',dpi=160); plt.close(fig)
    fig,axes=plt.subplots(math.ceil(len(models)/4),4,figsize=(20,5*math.ceil(len(models)/4)),squeeze=False)
    for i,m in enumerate(models):
        ax=axes.flat[i]; series=defaultdict(list)
        for r,snaps,pi,events in records:
            if r['model']!=m or pi is None: continue
            play=events[pi]; center=(play['round']-1)*r['n']+int(play['actor'].split('_')[-1])-1
            points={}
            for e,bals in zip(events,snaps):
                t=(e['round']-1)*r['n']+int(e['actor'].split('_')[-1])-1-center
                total=sum(bals.values()); points[t]=max(bals.values())/total if total else 0
            # Anchor t=0 at the play itself, not a later action in that turn.
            at_play=snaps[pi]; play_total=sum(at_play.values())
            points[0]=max(at_play.values())/play_total if play_total else 0
            for t,v in points.items(): series[t].append(v)
            ax.plot(sorted(points),[points[t] for t in sorted(points)],color='#0072B2',alpha=.25,linewidth=1)
        if series: ax.plot(sorted(series),[np.median(series[t]) for t in sorted(series)],color='#D55E00',linewidth=3)
        else: ax.text(.5,.5,'No pooled plays',ha='center',transform=ax.transAxes)
        ax.axvline(0,color='gray',linestyle=':'); ax.set(title=labels[i],xlabel='Agent-turn relative to pool play',ylabel='Largest holder share',ylim=(0,1.05))
    for ax in list(axes.flat)[len(models):]: ax.set_visible(False)
    fig.suptitle('Group concentration around pooled plays'); fig.tight_layout(); fig.savefig(out/'trajectory.png',dpi=160); plt.close(fig)
    fig,ax=plt.subplots(); bottoms=np.zeros(len(models))
    for label,color,predicate in [('Repaid all contributors ≥ 2','#009E73',lambda r:all(r['final_balances'][a] >= 2 for a in r['contributors'])),('Repaid some','#E69F00',lambda r:r['repaid_any'] and not all(r['final_balances'][a] >= 2 for a in r['contributors'])),('Kept everything','#D55E00',lambda r:not r['repaid_any'] and not all(r['final_balances'][a] >= 2 for a in r['contributors']))]:
        counts=[sum(bool(predicate(r)) for r in rows if r['model']==m and r['pool_won'] is True) for m in models]
        ax.bar(range(len(models)),counts,bottom=bottoms,label=label,color=color); bottoms+=counts
    ax.set(xticks=range(len(models)),xticklabels=labels,ylabel='Pooled wins',title='What winning poolers did'); ax.legend(); fig.tight_layout(); fig.savefig(out/'repayment.png',dpi=160); plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('run_dirs',nargs='+',type=Path); args=parser.parse_args()
    for p in args.run_dirs:
        if not p.is_dir(): parser.error(f'Not a directory: {p}')
    selected={}; duplicates=[]; excluded=[]
    for root in args.run_dirs:
        if root.name.endswith('-mock'):
            excluded.append(str(root)); continue
        for path in sorted((root/'episodes').glob('*/episode.json')):
            try:
                data=json.loads(path.read_text()); s=data['summary']; variant=episode_variant(data, root); key=(variant,s['model'],s['condition'],s['n'],s['rep']); stamp=path.stat().st_mtime_ns
            except (OSError,ValueError,KeyError) as exc:
                print(f'Skipping {path}: {exc}',file=sys.stderr); continue
            if key in selected:
                old=selected[key]; keep=max((old,(stamp,path,data)),key=lambda x:(x[0],str(x[1]))); drop=old if keep is not old else (stamp,path,data)
                duplicates.append(f'{key}: kept {keep[1]}, discarded {drop[1]}'); selected[key]=keep
            else: selected[key]=(stamp,path,data)
    output=args.run_dirs[0]/'analysis'; output.mkdir(parents=True,exist_ok=True)
    records=[]
    for _,path,data in selected.values():
        row,snapshots,pi=metrics(data, episode_variant(data, path.parents[2])); records.append((row,snapshots,pi,data['events']))
    rows=[x[0] for x in records]
    if rows:
        with (output/'episodes.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0].keys()); writer.writeheader()
            for r in rows: writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
    else:
        (output/'episodes.csv').write_text('model,condition,n,rep,status\n')
    (output/'episodes.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    report(rows,output,duplicates,excluded); figures(records,output)
    for item in duplicates: print('Duplicate:',item)
    for item in excluded: print('Excluded mock:',item)
    print(f'Analyzed {len(rows)} episodes; output: {output}')

if __name__=='__main__': main()
