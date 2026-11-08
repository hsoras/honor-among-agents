import json

import pytest

import run_v2
from llm import APIError


def endpoint(slug, params=('max_tokens', 'tools', 'reasoning')):
    return {'tag': slug, 'provider_name': slug, 'status': 0,
            'supported_parameters': params, 'pricing': {'prompt': '0.1', 'completion': '0.2'}}


def test_override_pins_provider_and_records_prices(tmp_path, monkeypatch):
    monkeypatch.setattr(run_v2, 'HERE', tmp_path)
    monkeypatch.setattr(run_v2, 'load_dotenv', lambda *a: None)
    monkeypatch.setattr(run_v2, 'fetch_endpoints', lambda model: [endpoint('other'), endpoint('anthropic')])
    pinned = []
    monkeypatch.setattr(run_v2, 'OpenRouterClient', lambda **kw: pinned.append(kw) or object())
    monkeypatch.setattr(run_v2, 'run_episode', lambda spec, *a: {'model': spec.model, 'n': spec.n, 'rep': spec.rep, 'condition': spec.condition})
    prompts = tmp_path / 'prompts-v2'
    prompts.mkdir()
    for name in ('system_board.md', 'system_noboard.md'):
        (prompts / name).write_text('hello')
    run_v2.main(['--live', '--models', 'test/model', '--provider', 'test/model=anthropic', '--pilot'])
    config = json.loads(next((tmp_path / 'results-v2').glob('*/config.json')).read_text())
    assert config['provider_overrides'] == {'test/model': 'anthropic'}
    assert config['routes']['test/model']['price_usd_per_token'] == [0.1, 0.2]
    assert pinned[0]['provider_order'] == ['anthropic']


@pytest.mark.parametrize('endpoints, message', [([endpoint('other')], 'not found'), ([endpoint('anthropic', ('max_tokens',))], 'tools, and reasoning')])
def test_invalid_override(tmp_path, monkeypatch, endpoints, message):
    monkeypatch.setattr(run_v2, 'HERE', tmp_path)
    monkeypatch.setattr(run_v2, 'load_dotenv', lambda *a: None)
    monkeypatch.setattr(run_v2, 'fetch_endpoints', lambda model: endpoints)
    with pytest.raises(APIError, match=message):
        run_v2.main(['--live', '--models', 'test/model', '--provider', 'test/model=anthropic', '--pilot'])
