import json
import httpx
import pytest
from sczx_api import algorithm
from sczx_api.task_policy import TaskBudget,TaskBudgetExceeded


def test_algorithm_transport_checks_shared_budget_during_stream(monkeypatch):
    monkeypatch.setenv('SCZX_ALGORITHM_SECRET','algorithm-budget-test-secret-at-least-32')
    now=[0.];budget=TaskBudget(clock=lambda:now[0]);original=httpx.Client
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"operation":"learning_task",'
            now[0]=46.
            yield b'"result":{}}'
    transport=httpx.MockTransport(lambda request:httpx.Response(200,stream=Stream()))
    monkeypatch.setattr(algorithm.httpx,'Client',lambda **kwargs:original(transport=transport,**kwargs))
    with pytest.raises(TaskBudgetExceeded) as error:algorithm.compute({'operation':'learning_task'},budget=budget)
    assert error.value.stage=='algorithm_read'


def test_expired_algorithm_budget_never_sends_network_request(monkeypatch):
    monkeypatch.setattr(algorithm.httpx,'Client',lambda **kwargs:pytest.fail('expired request reached network'))
    budget=TaskBudget(started=0,clock=lambda:46.)
    with pytest.raises(TaskBudgetExceeded) as error:algorithm.compute({'operation':'learning_task'},budget=budget)
    assert error.value.stage=='algorithm_start'
