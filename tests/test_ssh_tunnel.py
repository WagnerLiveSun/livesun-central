import importlib.util
import os
from pathlib import Path
import signal
import sys
from unittest.mock import Mock
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('central_tunnel', ROOT/'scripts/with_ssh_tunnel.py')
tunnel = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tunnel
spec.loader.exec_module(tunnel)


def environment(tmp_path):
    key = tmp_path/'fake-key'
    key.write_bytes(b'FICTITIOUS KEY FOR TEST ONLY - NOT A REAL KEY')
    return {'SSH_ENABLED':'true','DB_ENGINE':'postgresql',
        'DATABASE_URL':'postgresql+psycopg://test:secret@127.0.0.1:55433/DbCentral?sslmode=disable',
        'SSH_KEY_PATH':str(key), 'SSH_KNOWN_HOSTS_PATH':str(ROOT/'deploy/montudb_known_hosts'),
        'SSH_STARTUP_TIMEOUT_SECONDS':'5'}


def test_expected_secret_file_and_secure_ssh_options(tmp_path):
    env=environment(tmp_path)
    del env['SSH_KEY_PATH']
    settings=tunnel.Settings.from_env(env)
    assert str(settings.key_path).replace('\\','/')=='/etc/secrets/SKey'
    command=tunnel.ssh_command(settings,Path('/tmp/private'),'known_hosts','ssh')
    assert 'StrictHostKeyChecking=yes' in command
    assert 'BatchMode=yes' in command and 'ExitOnForwardFailure=yes' in command
    assert '127.0.0.1:55433:127.0.0.1:55433' in command
    assert 'opc@wagner.montudb.com' in command
    assert 'secret' not in ' '.join(command)
    assert 'accept-new' not in command


@pytest.mark.parametrize('overrides',[
    {'SSH_HOST':'-oProxyCommand=bad'}, {'SSH_USER':'opc@other'}, {'SSH_PORT':'0'},
    {'SSH_LOCAL_PORT':'5432'}, {'DB_ENGINE':'mysql'},
    {'DATABASE_URL':'postgresql+psycopg://test:secret@external:55433/DbCentral'},
    {'DATABASE_URL':'postgresql+psycopg://test:secret@127.0.0.1:55433/postgres'}])
def test_invalid_settings_rejected(tmp_path,overrides):
    with pytest.raises(tunnel.TunnelError):
        tunnel.Settings.from_env({**environment(tmp_path),**overrides})


def test_key_copied_privately_without_changing_source(tmp_path):
    source=tmp_path/'source'
    content=b'FICTITIOUS KEY - TESTS ONLY DO NOT USE IN PRODUCTION'
    source.write_bytes(content)
    target=tmp_path/'private'
    tunnel.secure_key_copy(source,target)
    assert source.read_bytes()==content and target.read_bytes()==content
    if os.name=='posix':
        assert target.stat().st_mode & 0o777==0o600
    with pytest.raises(FileExistsError):
        tunnel.secure_key_copy(source,target)


def test_missing_secret_and_untrusted_host_rejected(tmp_path):
    env=environment(tmp_path)
    with pytest.raises(tunnel.TunnelError):
        tunnel.secure_key_copy(tmp_path/'absent',tmp_path/'output')
    env['SSH_HOST']='other.example'
    with pytest.raises(tunnel.TunnelError):
        tunnel.check_known_hosts(tunnel.Settings.from_env(env))


def test_child_commands_include_prepare_web_worker():
    assert 'render_prepare.py' in ' '.join(tunnel.command_for('prepare',{}))
    assert 'gunicorn' in tunnel.command_for('web',{'PORT':'10000'})
    assert tunnel.command_for('worker',{})[-1]=='worker'
    assert tunnel.command_for('check',{}) is None


def test_application_not_started_before_database_ready(tmp_path,monkeypatch):
    env=environment(tmp_path)
    ssh=Mock();ssh.poll.return_value=None
    child=Mock();child.poll.side_effect=[None,0];child.returncode=0
    calls=[]
    def popen(args,**kwargs):
        calls.append((args,kwargs))
        return ssh if len(calls)==1 else child
    ready=iter([False,True])
    monkeypatch.setattr(tunnel.shutil,'which',lambda name:'ssh')
    monkeypatch.setattr(tunnel,'assert_local_port_free',lambda settings:None)
    monkeypatch.setattr(tunnel.subprocess,'Popen',popen)
    monkeypatch.setattr(tunnel,'database_ready',lambda e:next(ready))
    monkeypatch.setattr(tunnel.time,'sleep',lambda duration:None)
    monkeypatch.setattr(tunnel,'stop',lambda process:None)
    assert tunnel.supervise('worker',env)==0
    assert len(calls)==2
    assert calls[1][0][-1]=='worker'


def test_timeout_never_starts_app_or_logs_key(tmp_path,monkeypatch,capsys):
    env=environment(tmp_path)
    ssh=Mock();ssh.poll.return_value=None
    calls=[]
    monkeypatch.setattr(tunnel.shutil,'which',lambda name:'ssh')
    monkeypatch.setattr(tunnel,'assert_local_port_free',lambda settings:None)
    monkeypatch.setattr(tunnel.subprocess,'Popen',lambda args,**kwargs:(calls.append(args) or ssh))
    monkeypatch.setattr(tunnel,'database_ready',lambda e:False)
    counter=iter(range(100))
    monkeypatch.setattr(tunnel.time,'monotonic',lambda:next(counter))
    monkeypatch.setattr(tunnel.time,'sleep',lambda duration:None)
    monkeypatch.setattr(tunnel,'stop',lambda process:None)
    with pytest.raises(tunnel.TunnelError):
        tunnel.supervise('worker',env)
    assert len(calls)==1 and 'worker' not in calls[0]
    captured=capsys.readouterr()
    assert 'FICTITIOUS' not in captured.out+captured.err


def test_no_secrets_in_docker_context():
    ignored=(ROOT/'.dockerignore').read_text()
    assert '.env.*' in ignored and 'SKey' in ignored and '*.key' in ignored
    docker=(ROOT/'Dockerfile').read_text()
    assert 'openssh-client' in docker and 'USER central' in docker