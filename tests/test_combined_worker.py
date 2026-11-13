import signal
from unittest.mock import Mock

import pytest
from test_ssh_tunnel import tunnel, environment


@pytest.mark.parametrize('ending', ['worker_failure', 'worker_zero', 'web_failure', 'signal', 'prepare_failure'])
def test_combined_process_lifecycle(tmp_path, monkeypatch, ending):
    env = environment(tmp_path)
    ssh, prepare, web, worker = Mock(), Mock(), Mock(), Mock()
    ssh.poll.return_value = None
    prepare.poll.return_value = 1 if ending == 'prepare_failure' else 0
    web.poll.return_value = 7 if ending == 'web_failure' else None
    worker.poll.return_value = 9 if ending == 'worker_failure' else 0 if ending == 'worker_zero' else None
    worker.returncode = 9 if ending == 'worker_failure' else 0
    processes = iter([ssh, prepare, web, worker])
    calls, stopped, handlers = [], [], {}

    def popen(args, **kwargs):
        calls.append(args)
        return next(processes)

    def register(signum, handler):
        previous = handlers.get(signum, signal.SIG_DFL)
        handlers[signum] = handler
        return previous

    def sleep(duration):
        if ending == 'signal' and len(calls) == 4:
            handlers[signal.SIGTERM](signal.SIGTERM, None)

    monkeypatch.setattr(tunnel.shutil, 'which', lambda name: 'ssh')
    monkeypatch.setattr(tunnel, 'assert_local_port_free', lambda settings: None)
    monkeypatch.setattr(tunnel.subprocess, 'Popen', popen)
    monkeypatch.setattr(tunnel, 'database_ready', lambda e: True)
    monkeypatch.setattr(tunnel.signal, 'signal', register)
    monkeypatch.setattr(tunnel.time, 'sleep', sleep)
    monkeypatch.setattr(tunnel, 'stop', stopped.append)
    expected = {'worker_failure': 9, 'worker_zero': 1, 'web_failure': 7, 'signal': 0, 'prepare_failure': 1}
    assert tunnel.supervise('web-worker', env) == expected[ending]
    assert 'render_prepare.py' in calls[1][-1]
    if ending == 'prepare_failure':
        assert len(calls) == 2
        assert worker not in stopped
    else:
        assert len(calls) == 4
        assert 'gunicorn' in calls[2]
        assert calls[3][-1] == 'worker'
        assert stopped == [web, worker, ssh]
    assert sum('-L' in command for command in calls) == 1