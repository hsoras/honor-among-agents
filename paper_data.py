"""Recount retained v2 episodes for the paper; no model/API calls."""
import json
from collections import Counter, defaultdict
from pathlib import Path
from analyze_v2 import episode_variant, metrics, short_model, fisher, mcnemar

BASE = Path(__file__).resolve().parent
OUT = BASE / 'tmp/pdfs'

def load():
    selected = {}
    for root in sorted((BASE / 'results-v2').iterdir()):
        cp = root / 'config.json'
        if not cp.exists() or 'pilot' in root.name:
            continue
        cfg = json.loads(cp.read_text())
        if cfg.get('mock'):
            continue
        for path in sorted((root / 'episodes').glob('*/episode.json')):
            data = json.loads(path.read_text())
            s = data['summary']
            variant = episode_variant(data, root)
            # The reported objective control consists of board games only.
            if variant == 'noobj' and s['condition'] != 'board':
                continue
            if s['n'] != 4 or s['rep'] not in range(20):
                continue
            if variant == 'noobj' and s['status'] not in ('completed', 'truncated'):
                continue
            key = variant, s['model'], s['condition'], s['rep']
            if key not in selected or root.name > selected[key][0].parents[2].name:
                selected[key] = (path, data)
    rows = []
    for (variant, _, _, _), (path, data) in sorted(selected.items()):
        r, _, _ = metrics(data, variant)
        # Independently replay the event accounting against the saved summary.
        balances = {f'agent_{i}': 1 for i in range(1, 5)}
        for e in data['events']:
            if e['action'] == 'transfer':
                balances[e['actor']] -= e['amount']
                balances[e['to']] += e['amount']
            elif e['action'] == 'play':
                balances[e['actor']] -= e['stake']
                balances[e['actor']] += e['received']
        assert balances == data['summary']['final_balances'] == r['final_balances'], path
        r['path'] = str(path.relative_to(BASE))
        r['name'] = short_model(r['model'])
        r['seed'] = data['spec']['seed']
        if r['pool_won']:
            pi = next(i for i, e in enumerate(data['events']) if e['action'] == 'play' and e['actor'] == r['pooler'])
            r['prewin_posts'] = [e['text'] for e in data['events'][:pi] if e['action'] == 'post' and e['actor'] == r['pooler']]
        rows.append(r)
    return rows

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load()
    (OUT / 'paper_data.json').write_text(json.dumps(rows, indent=2))
    groups = defaultdict(list)
    for r in rows:
        groups[r['variant'], r['name'], r['condition']].append(r)
    for key, rs in groups.items():
        wins = [r for r in rs if r['pool_won']]
        print(key, 'n', len(rs), 'status', dict(Counter(r['status'] for r in rs)),
              'pool', sum(r['pooled'] for r in rs), 'win', len(wins),
              'whole', sum(r['contributors_whole'] for r in wins),
              'exit', sum(r['exit_after_win'] for r in wins),
              '16each', sum(all(x == 16 for x in r['final_balances'].values()) for r in rs),
              'zero', sum(r['total_final'] == 0 for r in rs),
              'mean', round(sum(r['total_final'] for r in rs) / len(rs), 2))
    print('Total retained episodes:', len(rows))
    print('Main statuses:', Counter(r['status'] for r in rows if r['variant'] == 'main'))
    for r in rows:
        if r['variant'] == 'main' and r['name'] in ('Sol 6.1', 'Astra 6') and r['pool_won']:
            print('PROMISE', r['name'], r['rep'], r['prewin_posts'])
    print('Main family Fisher:', fisher(17, 2, 0, 24))
    print('No-objective family Fisher:', fisher(26, 5, 28, 4))
