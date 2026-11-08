import json
import subprocess
import sys
from pathlib import Path

from episode_v2 import EpisodeSpec, run_episode
from llm import ChatCompletion, Budget


def test_parallel_results_and_persistent_reasoning(tmp_path):
    class Client:
        def chat(self, **kwargs):
            calls = [{'id': 'a', 'type': 'function', 'function': {'name': 'vote_end', 'arguments': '{}'}},
                     {'id': 'b', 'type': 'function', 'function': {'name': 'play', 'arguments': '{"stake":1}'}}]
            msg = {'role': 'assistant', 'content': None, 'tool_calls': calls,
                   'reasoning_details': [{'text': 'preserve me'}]}
            return ChatCompletion(msg, 1, 1, 0, 'tool_calls', 'mock')
    budget = Budget(100, 100, 100, {'m': (0, 0)})
    result = run_episode(EpisodeSpec('m', True, 4, 0, 1), Client(), budget, tmp_path/'ep', 'system')
    assert result['status'] == 'completed'
    data = json.loads((tmp_path/'ep/episode.json').read_text())
    history = data['conversations']['agent_1']
    assert history[2]['reasoning_details'] == [{'text': 'preserve me'}]
    assert history[3]['tool_call_id'] == 'a'
    assert history[4]['tool_call_id'] == 'b' and history[4]['content'].startswith('NOT EXECUTED')


def test_mock_cli_files():
    run = subprocess.run([sys.executable, 'run_v2.py', '--mock', '--pilot', '--models', 'mock/test', '--ns', '4'],
                         check=True, capture_output=True, text=True)
    folder = Path(run.stdout.strip().splitlines()[-1])
    assert all((folder / name).exists() for name in ('config.json', 'metrics.json', 'records.jsonl'))
    episodes = list((folder / 'episodes').iterdir())
    assert len(episodes) == 2
    for ep in episodes:
        assert (ep/'episode.json').exists() and (ep/'transcript.jsonl').exists()
        assert json.loads((ep/'episode.json').read_text())['summary']['status'] in ('completed', 'truncated')


def test_fixed_horizon_disables_vote(tmp_path):
    from llm import MockClient
    spec = EpisodeSpec('m', True, 4, 10, 20265118, no_end_vote=True)
    result = run_episode(spec, MockClient(), None, tmp_path/'fixed', 'system')
    data = json.loads((tmp_path/'fixed'/'episode.json').read_text())
    assert data['spec']['no_end_vote'] is True
    assert result['status'] == 'completed'
    assert result['rounds'] == 8 or result['total_final'] == 0
    assert not any(e['action'] == 'vote_end' for e in data['events'])


def test_shifted_repetitions_and_zero_counts(tmp_path, monkeypatch):
    import run_v2
    monkeypatch.setattr(run_v2, 'HERE', tmp_path)
    import shutil
    from pathlib import Path
    shutil.copytree(Path(__file__).resolve().parents[1]/'prompts-v2', tmp_path/'prompts-v2')
    run_v2.main(['--mock', '--models', 'm', '--ns', '4', '--board-reps', '2', '--noboard-reps', '0', '--rep-start', '10'])
    out = next((tmp_path/'results-v2').iterdir())
    assert json.loads((out/'config.json').read_text())['rep_start'] == 10
    episodes = sorted((out/'episodes').iterdir())
    assert [p.name for p in episodes] == ['m__board__n4__r10', 'm__board__n4__r11']
    assert [json.loads((p/'episode.json').read_text())['spec']['seed'] for p in episodes] == [20265118, 20265119]
