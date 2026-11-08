import pytest
from llm import Budget, BudgetExceeded, ChatCompletion, MockClient


def test_chat_budget_reserves_and_settles(tmp_path):
    budget = Budget(2, 100, 100, {'m': (0.00001, 0.00001)}, tmp_path / 'ledger.json')
    meter = budget.meter()
    class Client:
        def chat(self, **kwargs):
            assert budget.charged_usd > 0
            return ChatCompletion(message={'role':'assistant', 'content':'ok'}, prompt_tokens=1,
                                  completion_tokens=1, cost_usd=0.01, finish_reason='stop', provider='mock')
    budget.call_chat(Client(), model='m', messages=[], tools=[], meta={}, max_tokens=10, meter=meter)
    assert meter.calls == 1 and meter.usd == pytest.approx(0.01)
    assert budget.charged_usd == pytest.approx(0.01)
    limited = Budget(1, 0, 0, {'m': (1, 1)})
    with pytest.raises(BudgetExceeded):
        limited.call_chat(Client(), model='m', messages=[], tools=[], meta={}, max_tokens=10, meter=limited.meter())


def test_mock_chat_is_seeded():
    client = MockClient()
    kwargs = dict(model='m', messages=[], tools=[{'function': {'name':'end_turn'}}],
                  meta={'seed': 42, 'actor':'agent_1', 'round':1, 'step':0}, max_tokens=10)
    assert client.chat(**kwargs).message == client.chat(**kwargs).message
