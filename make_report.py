#!/usr/bin/env python3
"""Generate pooled-gamble descriptive figures/report from local result artifacts."""
import json, pathlib, collections, math, re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BASE = pathlib.Path(__file__).resolve().parent
RESULTS = BASE / 'results'
OUT = BASE / 'figures'
OUT.mkdir(exist_ok=True)

COLORS = {'board':'#d97706', 'noboard':'#2563eb'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                     'axes.spines.right':False,'axes.titleweight':'bold',
                     'figure.facecolor':'white','axes.facecolor':'white'})

def read_data():
    episodes=[]; runs=[]
    for d in sorted(RESULTS.iterdir()):
        if not d.is_dir() or not (d/'config.json').exists(): continue
        cfg=json.loads((d/'config.json').read_text()); c=cfg.get('config',{})
        files=sorted((d/'episodes').glob('*')) if (d/'episodes').exists() else []
        statuses=collections.Counter(); completed=0; partial=0
        for p in files:
            epfile=p/'episode.json'
            raw=json.loads(epfile.read_text()) if epfile.exists() else {}
            s=raw.get('summary',{})
            st=s.get('status')
            if not epfile.exists(): partial+=1; statuses['incomplete_artifact']+=1
            else: statuses[st or 'unknown']+=1
            # Transcript data are token metadata only; reply contents are never retained in report.
            tr=p/'transcript.jsonl'; trows=[]
            if tr.exists():
                for line in tr.read_text().splitlines():
                    try: trows.append(json.loads(line))
                    except json.JSONDecodeError: pass
            nameparts=p.name.split('__')
            model=s.get('model')
            if model is None:
                slug=nameparts[0] if nameparts else ''
                model=next((m for m in c.get('models',[]) if m.replace('/','_').replace('.','-')==slug or m.replace('/','_')==slug),slug.replace('_','/'))
            condition=s.get('condition') or (nameparts[1] if len(nameparts)>1 else 'unknown')
            match=re.search(r'__n(\d+)__r(\d+)',p.name)
            info=dict(s); info.update(model=model,condition=condition,
                n=s.get('n',int(match.group(1)) if match else 0),rep=s.get('rep',int(match.group(2)) if match else -1),
                status=st,run=d.name, path=str(p.relative_to(BASE)), raw=raw,
                max_tokens=c.get('max_tokens'), reasoning_setting=(c.get('reasoning') or {}).get(model),
                transcript_calls=len(trows), reasoning_tokens=sum(x.get('reasoning_tokens',0) or 0 for x in trows),
                completion_tokens=sum(x.get('completion_tokens',0) or 0 for x in trows),
                length_replies=sum(x.get('finish_reason')=='length' for x in trows),
                transcript_finish=collections.Counter(x.get('finish_reason','?') for x in trows))
            info['cohort']=('reasoning enabled' if info['reasoning_setting'] and info['reasoning_setting'].get('enabled') else
                            'reasoning off' if info['reasoning_setting'] and info['reasoning_setting'].get('enabled') is False else
                            'reasoning unspecified')
            episodes.append(info)
            if st=='completed': completed+=1
        run_models=set()
        for p in files:
            if (p/'episode.json').exists():
                try: run_models.add(json.loads((p/'episode.json').read_text()).get('summary',{}).get('model'))
                except Exception: pass
        settings=c.get('reasoning') or {}
        enabled=any(isinstance(settings.get(m),dict) and settings[m].get('enabled') for m in run_models)
        explicit_off=bool(run_models) and all(settings.get(m) is None or settings.get(m) is False or
            (isinstance(settings.get(m),dict) and not settings[m].get('enabled',False)) for m in run_models)
        run_cohort='reasoning enabled' if enabled else 'reasoning off' if explicit_off else 'reasoning unspecified'
        runs.append(dict(run=d.name,planned=cfg.get('planned_episodes'),artifacts=len(files),completed=completed,
                         partial=partial,statuses=statuses,cohort=run_cohort,
                         max_tokens=c.get('max_tokens'),mock=cfg.get('mock',False)))
    return episodes,runs

def paired_cohort(eps, model, cohort):
    return [e for e in eps if e.get('status')=='completed' and e.get('model')==model and e['cohort']==cohort]

def figure_main(eps):
    # A full 3-replicate paired cohort exists for DeepSeek, no reasoning, from one run.
    data=[e for e in eps if e.get('status')=='completed' and e['run']=='20261107-233924' and e['model']=='deepseek/deepseek-v4.1-flash-1017']
    fig,axs=plt.subplots(1,4,figsize=(15.5,4.2))
    for ax,metric,title,ylabel in zip(axs[:3],['total_final','plays','stake_total'],['Final group points','Games played','Total points staked'],['points (start = group size)','plays per episode','points staked per episode']):
        for cond in ['noboard','board']:
            vals=[]; sizes=[]
            for n in [2,4,8]:
                cell=[e[metric] for e in data if e['n']==n and e['condition']==cond]
                vals.append(np.mean(cell) if cell else np.nan); sizes.append(n)
                if cell: ax.scatter([n]*len(cell),cell,color=COLORS[cond],alpha=.58,s=30,zorder=3)
            ax.plot(sizes,vals,color=COLORS[cond],marker='o',lw=2,label=cond)
        ax.set_xticks([2,4,8]); ax.set_xlabel('Group size N'); ax.set_ylabel(ylabel); ax.set_title(title)
        ax.grid(axis='y',alpha=.2)
    ax=axs[3]
    # Each dot is a completed episode; total final points; explicitly limited to the complete baseline cohort.
    for cond,offset in [('noboard',-.12),('board',.12)]:
        for e in [x for x in data if x['condition']==cond]:
            ax.scatter(e['n']+offset,e['transfers'],s=65,color=COLORS[cond],edgecolor='white',linewidth=.6)
    ax.set_xticks([2,4,8]); ax.set_xlabel('Group size N'); ax.set_ylabel('Transfers per episode'); ax.set_title('Transfers')
    ax.set_ylim(-.5, max(2,max((e['transfers'] for e in data),default=0)+1)); ax.grid(axis='y',alpha=.2)
    handles=[plt.Line2D([0],[0],marker='o',color=COLORS[c],label=c,lw=2) for c in ['noboard','board']]
    fig.legend(handles=handles,loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.5,1.04))
    fig.suptitle('Pooled gamble · complete baseline cohort',y=1.13,fontsize=15,fontweight='bold')
    fig.text(.5,-.025,'DeepSeek V4.1 Flash 1017 · reasoning off · 3 episodes per condition × group size. Dots = episodes; lines = cell means.',ha='center',fontsize=9,color='#475569')
    fig.tight_layout()
    fig.savefig(OUT/'baseline_outcomes.png',dpi=200,bbox_inches='tight'); fig.savefig(OUT/'baseline_outcomes.svg',bbox_inches='tight'); plt.close(fig)

def figure_reasoning(eps):
    data=[e for e in eps if e.get('status')=='completed' and e['cohort']=='reasoning enabled' and e['run']=='20261107-235633']
    fig,axs=plt.subplots(1,2,figsize=(10,4.3))
    # paired N=2 condition comparison from completed reasoning-on replicate set
    cell=[e for e in data if e['model']=='deepseek/deepseek-v4.1-flash-1017' and e['n']==2]
    ax=axs[0]
    for cond in ['noboard','board']:
        es=sorted([e for e in cell if e['condition']==cond],key=lambda x:x['rep'])
        xs=[0 if cond=='noboard' else 1]*len(es)
        ax.scatter(xs,[e['total_final'] for e in es],s=70,color=COLORS[cond],label=cond,zorder=3)
        if es: ax.plot([xs[0],xs[-1]] if len(es)>1 else [xs[0],xs[0]],[es[0]['total_final'],es[-1]['total_final']],color=COLORS[cond],alpha=.28)
    ax.set_xticks([0,1],['No board','Board']); ax.set_ylabel('Final group points'); ax.set_title('Reasoning-on episodes (N=2)')
    ax.set_ylim(-.3, max([2]+[e['total_final'] for e in cell])+.7); ax.grid(axis='y',alpha=.2)
    # response completion diagnostics by run/model; length-ended calls reflect max-token completion cap
    ax=axs[1]; runs=collections.defaultdict(lambda:[0,0])
    for e in eps:
        if e.get('transcript_calls',0):
            key=f"{e['run']}\n{e['model'].split('/')[-1]}"
            runs[key][0]+=e['transcript_calls']; runs[key][1]+=e['length_replies']
    labels=list(runs); vals=[runs[k][1]/runs[k][0] for k in labels]
    ax.bar(range(len(labels)),vals,color=['#a855f7' if 'glm' in k else '#0f766e' for k in labels],width=.7)
    ax.set_xticks(range(len(labels)),labels,rotation=35,ha='right',fontsize=8); ax.set_ylim(0,1); ax.set_ylabel('Share of responses ending at length cap')
    ax.set_title('Output truncation by run'); ax.grid(axis='y',alpha=.2)
    for i,(k,v) in enumerate(zip(labels,vals)): ax.text(i,v+.025,f'{runs[k][1]}/{runs[k][0]}',ha='center',fontsize=8)
    fig.suptitle('Reasoning and response-length diagnostics',y=1.03,fontsize=14,fontweight='bold')
    fig.text(.5,-.13,'Outcomes include only status=completed episodes. The truncation panel counts saved transcript responses, including partial runs; it is a response-level diagnostic, not an episode success rate.',ha='center',fontsize=8.5,color='#475569')
    fig.tight_layout(); fig.savefig(OUT/'reasoning_and_truncation.png',dpi=200,bbox_inches='tight'); fig.savefig(OUT/'reasoning_and_truncation.svg',bbox_inches='tight'); plt.close(fig)

def main():
    eps,runs=read_data(); figure_main(eps); figure_reasoning(eps)
    completed=[e for e in eps if e.get('status')=='completed']
    latest=[e for e in eps if e['run']=='20261108-000433']
    latest_calls=sum(e['transcript_calls'] for e in latest)
    latest_reason=sum(e['reasoning_tokens'] for e in latest)
    latest_length=sum(e['length_replies'] for e in latest)
    latest_partial=sum(1 for e in latest if e.get('status') is None)
    latest_done=sum(1 for e in latest if e.get('status')=='completed')
    lines=['# Pooled gamble: preliminary results and run audit','',
      '**Exploratory and preliminary.** This report is generated by `make_report.py` from local run artifacts. It uses complete episodes for outcome descriptions, keeps model/condition/configuration cohorts separate, and does not include raw prompts or replies. Incomplete runs may still be changing.', '',
      '## What the available complete episodes show','',
      'The cleanest comparison is the earlier DeepSeek V4.1 Flash 1017 cohort without reasoning: run `20261107-233924`, with 3 completed episodes in each board/no-board × N=2/4/8 cell. Mean group totals were identical by condition at N=2 (1.33), N=4 (4.67), and differed by only 0.33 points at N=8 (8.33 board; 8.00 no-board). Mean plays were 2 in each condition at N=2 and 4 at N=4; at N=8, 7.67 (board) and 8 (no-board). Mean total points staked were also similar: N=2, 2 in both; N=4, 8 in both; N=8, 8 (board) vs 8 (no-board). No transfers occurred in these 18 episodes. These tiny cells are descriptive; they do not establish equivalence or a board effect.','',
      '![Baseline outcome figures](figures/baseline_outcomes.png)','',
      'The later reasoning-enabled DeepSeek run (`20261107-235633`) has completed N=2 episodes in both conditions, 3 per condition. Their final totals were 0, 2, 2 in each condition (mean 1.33); all 12 episodes included plays, and there were no transfers. Each N=2 episode staked 2 points total. Only two N=4 episodes completed (one per condition); other artifacts in that run lack final episode summaries. This is too little data to compare reasoning-on with reasoning-off: the prompt/output budget and run timing also changed, and model sampling is unseeded.','',
      'No completed multiplier-variant episodes were found. A multiplier-x2–10 pilot folder is present, but its episode folders lack final summaries, so it contributes no outcome data yet. Stakes in the original variant are whole point amounts chosen per play; transferred volume is zero in every completed episode inspected.','',
      '![Reasoning and truncation diagnostics](figures/reasoning_and_truncation.png)','',
      '## Run inventory','',
      '| Run | Config | Episode folders | Completed | Other saved statuses / partial folders | Notes |','|---|---|---:|---:|---|---|']
    for r in runs:
        other=', '.join(f'{k}: {v}' for k,v in sorted(r['statuses'].items()) if k!='completed') or '—'
        if r['partial']: other += f'; no episode summary: {r["partial"]}'
        notes=('max_tokens='+str(r['max_tokens'])+'; '+r['cohort'])
        if r['run']=='20261107-234018': notes+='; GLM responses frequently hit output cap'
        if r['run']=='20261108-000433': notes+='; reasoning-on run; includes completed and in-progress artifacts'
        if 'multiplier-x' in r['run']: notes+='; multiplier pilot; no completed episode summaries'
        if r['run']=='20261108-000714-pilot': notes+='; reasoning-enabled pilot aborted by budget guard'
        lines.append(f"| `{r['run']}` | {r['cohort']}, {r['max_tokens']} max tokens | {r['artifacts']} | {r['completed']} | {other} | {notes} |")
    lines += ['', '## Reasoning, truncation, and completeness','',
      'The initial 36-episode grid (`20261107-233924`) was configured with reasoning disabled for DeepSeek and GLM reasoning mandatory for GLM; all 18 DeepSeek episodes completed, while GLM attempts failed with HTTP 400 before useful gameplay. A separate GLM run (`20261107-234018`) used a 2,048-token cap and saved 8 episodes: 2 completed, 3 truncated at the episode turn limit, and 3 failed. Across its 93 saved responses, 81 ended with `finish_reason=length`; this points to response-length pressure, and invalid-action counts were high. The completion/behavior results from those episodes should not be pooled with the DeepSeek cohort.', '',
      f'Reasoning was explicitly enabled in the 8,192-token runs. For `20261107-235633`, saved transcript metadata show 22 length-ended responses among 52 calls; its 6 completed N=2 DeepSeek episodes had **zero reported reasoning tokens** on their response records, although the run configuration requested reasoning. The newer run `20261108-000433` is still changing during this audit: at report generation it had {latest_done} completed episode summaries and {latest_partial} folders without summaries, with {latest_calls} responses saved ({latest_reason:,} reported reasoning tokens; {latest_length} ended with `finish_reason=length`). The incomplete folders cannot be treated as completed episodes. The figure’s response-length rates are per-call diagnostics; `length` indicates a response was cut off by the configured generation limit, not necessarily that the whole episode was incomplete.', '',
      'Across all completed episodes, outcome figures exclude errors and truncated episodes. Inventory distinguishes explicit failed/truncated summaries from transcript-only folders. Historical pilot runs are retained in the inventory but not added to the primary full-grid comparison, avoiding duplicate or differently configured replicates. No raw data, prompts, or model replies are copied into this report.', '',
      '## Limitations and next steps','',
      '- The full baseline cohort has only 3 episodes per cell; paired seeds control game draws and turn order, not model sampling randomness.',
      '- Conditions contain transfer/action signaling in both arms; the board contrast is the incremental effect of explicit posts in this harness.',
      '- Models act in homogeneous groups. Results do not generalize to mixed groups or other model versions/providers.',
      '- Completion and parsing behavior differ by model/config. Excluding incomplete episodes is appropriate for outcome summaries but can create selection bias.',
      '- Point units are toy simulation points, not money or calibrated utility; group totals are not the agents’ stated objective.',
      '- Multiplier-x results are not available in the inspected artifacts.', '',
      '## Reproduction','',
      'From the workspace root, run `python experiments/pooled-gamble/make_report.py`. It scans saved `results/*/config.json` and `episodes/*/episode.json` plus transcript token/finish metadata, writes only figures and this report, and does not make API calls. Figure sources are `figures/baseline_outcomes.svg` and `figures/reasoning_and_truncation.svg`.']
    (BASE/'PRELIMINARY_REPORT.md').write_text('\n'.join(lines)+'\n')
    print(f'Wrote {BASE / "PRELIMINARY_REPORT.md"}')
    print('Completed episodes:',len(completed),'run folders:',len(runs))

if __name__=='__main__': main()
