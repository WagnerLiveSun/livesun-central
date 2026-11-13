"""Supervisiona OpenSSH e aplicação sem shell, senhas em argumentos ou TOFU."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]


class TunnelError(RuntimeError):
    """Mensagens fixas, sem conteúdo do secret file ou URL com senha."""


def log(event):
    print(json.dumps({'event': event}), flush=True)


def port(value):
    try:
        parsed = int(value)
    except (ValueError, TypeError):
        raise TunnelError('Porta de túnel inválida.') from None
    if not 1 <= parsed <= 65535:
        raise TunnelError('Porta de túnel inválida.')
    return parsed


@dataclass(frozen=True)
class Settings:
    host: str
    user: str
    ssh_port: int
    remote_port: int
    local_port: int
    key_path: Path
    known_hosts: Path
    startup_timeout: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]):
        from sqlalchemy.engine import make_url
        host = env.get('SSH_HOST', 'wagner.montudb.com')
        user = env.get('SSH_USER', 'opc')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host):
            raise TunnelError('SSH_HOST inválido.')
        if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_-]*', user):
            raise TunnelError('SSH_USER inválido.')
        try:
            url = make_url(env.get('DATABASE_URL', ''))
        except Exception:
            raise TunnelError('Configure DATABASE_URL para o túnel local.') from None
        local_port = port(env.get('SSH_LOCAL_PORT', '55433'))
        if (env.get('DB_ENGINE') != 'postgresql' or url.drivername != 'postgresql+psycopg'
                or url.host != '127.0.0.1' or url.port != local_port or not url.database
                or not url.username or not url.password):
            raise TunnelError('DATABASE_URL deve usar postgresql+psycopg e 127.0.0.1 na porta do túnel.')
        if url.database in ('postgres', 'template0', 'template1'):
            raise TunnelError('Use banco exclusivo do Central.')
        try:
            timeout = int(env.get('SSH_STARTUP_TIMEOUT_SECONDS', '90'))
        except ValueError:
            raise TunnelError('Timeout SSH inválido.') from None
        if not 5 <= timeout <= 300:
            raise TunnelError('Timeout SSH deve estar entre 5 e 300 segundos.')
        return cls(host, user, port(env.get('SSH_PORT', '22')),
                   port(env.get('SSH_REMOTE_PORT', '55433')), local_port,
                   Path(env.get('SSH_KEY_PATH', '/etc/secrets/SKey')),
                   Path(env.get('SSH_KNOWN_HOSTS_PATH', str(ROOT/'deploy/montudb_known_hosts'))), timeout)


def command_for(mode, env):
    if mode == 'web':
        http_port = port(env.get('PORT', '10000'))
        return [sys.executable, '-m', 'gunicorn', '--bind', f'0.0.0.0:{http_port}',
                '--workers', '2', '--threads', '4', '--timeout', '60', 'wsgi:app']
    if mode == 'worker':
        return [sys.executable, '-m', 'flask', '--app', 'wsgi', 'worker']
    if mode == 'prepare':
        return [sys.executable, str(ROOT/'scripts/render_prepare.py')]
    if mode == 'check':
        return None
    raise TunnelError('Modo de inicialização inválido.')


def ssh_command(settings, private_key, known_hosts, executable):
    return [executable, '-F', os.devnull, '-N', '-T',
            '-i', str(private_key), '-p', str(settings.ssh_port),
            '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none',
            '-o', 'PasswordAuthentication=no', '-o', 'KbdInteractiveAuthentication=no',
            '-o', 'StrictHostKeyChecking=yes', '-o', f'UserKnownHostsFile={known_hosts}',
            '-o', 'GlobalKnownHostsFile=' + os.devnull, '-o', 'UpdateHostKeys=no',
            '-o', 'HostKeyAlgorithms=ssh-ed25519', '-o', f'HostKeyAlias={settings.host}',
            '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1',
            '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
            '-o', 'ExitOnForwardFailure=yes', '-o', 'LogLevel=ERROR',
            '-L', f'127.0.0.1:{settings.local_port}:127.0.0.1:{settings.remote_port}',
            f'{settings.user}@{settings.host}']


def secure_key_copy(source, target):
    # Secret files podem estar montados como somente leitura/modo 0644.
    # A cópia efêmera com modo 0600 evita relaxar as proteções do OpenSSH.
    if not source.is_file():
        raise TunnelError('Secret File SSH não encontrado. Configure /etc/secrets/SKey neste serviço.')
    with source.open('rb') as original:
        metadata = os.fstat(original.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 65536 or metadata.st_size < 32:
            raise TunnelError('Secret File SSH inválido.')
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as destination:
            shutil.copyfileobj(original, destination)
    return target


def check_known_hosts(settings):
    if not settings.known_hosts.is_file():
        raise TunnelError('Arquivo known_hosts confiável ausente. Não aceite chave automaticamente.')
    lines = settings.known_hosts.read_text(encoding='utf-8').splitlines()
    if not any(len(parts := line.split()) == 3 and parts[0] == settings.host
               and parts[1] == 'ssh-ed25519' for line in lines if line and not line.startswith('#')):
        raise TunnelError('Host SSH sem chave ed25519 fixada no known_hosts.')


def assert_local_port_free(settings):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(('127.0.0.1', settings.local_port))
        except OSError:
            raise TunnelError('Porta local do túnel já ocupada. Não reutilize conexão desconhecida.') from None


def database_ready(env):
    import psycopg
    from sqlalchemy.engine import make_url
    url = make_url(env['DATABASE_URL'])
    options = dict(url.query)
    options['connect_timeout'] = 3
    try:
        with psycopg.connect(host=url.host, port=url.port, dbname=url.database,
                             user=url.username, password=url.password, **options) as conn:
            conn.execute('SELECT 1').fetchone()
        return True
    except psycopg.Error:
        return False


def stop(process):
    if process is None or process.poll() is not None:
        return
    try:
        if os.name == 'posix':
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=10)
    except (subprocess.TimeoutExpired, ProcessLookupError):
        if process.poll() is None:
            if os.name == 'posix':
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait(timeout=5)


def supervise(mode, env=None):
    env = dict(os.environ if env is None else env)
    if env.get('SSH_ENABLED', 'false').lower() != 'true':
        raise TunnelError('Este inicializador exige SSH_ENABLED=true; use o inicializador local para acesso direto.')
    settings = Settings.from_env(env)
    executable = shutil.which('ssh')
    if not executable:
        raise TunnelError('OpenSSH ausente. Use o Dockerfile do projeto no Render.')
    check_known_hosts(settings)
    assert_local_port_free(settings)
    command = command_for(mode, env)
    stopping = False
    def handle_signal(signum, frame):
        nonlocal stopping
        stopping = True
    previous = {}
    for signum in (signal.SIGTERM, signal.SIGINT):
        previous[signum] = signal.signal(signum, handle_signal)
    ssh = app = None
    preparing = False
    prepared = mode != 'web'
    try:
        with tempfile.TemporaryDirectory(prefix='central-ssh-') as folder, tempfile.TemporaryFile() as ssh_errors:
            private_key = secure_key_copy(settings.key_path, Path(folder)/'identity')
            arguments = ssh_command(settings, private_key, settings.known_hosts, executable)
            next_attempt, deadline = 0, time.monotonic() + settings.startup_timeout
            failures = 0
            ready = False
            while not stopping:
                if app is not None:
                    exit_code = app.poll()
                    if exit_code is not None:
                        if not preparing or exit_code != 0:
                            return exit_code
                        app = None
                        preparing, prepared = False, True
                        log('database_preparation_completed')
                if ssh is not None and ssh.poll() is not None:
                    ssh = None
                    if ready:
                        ready = False
                        deadline = time.monotonic() + settings.startup_timeout
                        log('ssh_tunnel_disconnected')
                    failures += 1
                    next_attempt = time.monotonic() + min(10, 2 ** min(failures, 3))
                if not ready and time.monotonic() >= deadline:
                    raise TunnelError('Túnel/banco indisponível. Confira Secret File, chave do host, firewall e credenciais PostgreSQL.')
                if ssh is None and time.monotonic() >= next_attempt:
                    ssh = subprocess.Popen(arguments, env={**env, 'SSH_ASKPASS_REQUIRE':'never'},
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=ssh_errors,
                        start_new_session=os.name == 'posix')
                if ssh is not None and not ready and ssh.poll() is None and database_ready(env):
                    # Só libera a aplicação se o processo SSH ainda possuir o encaminhamento.
                    if ssh.poll() is not None:
                        continue
                    ready, failures = True, 0
                    log('ssh_tunnel_and_database_ready')
                    if command is None:
                        return 0
                if ready and app is None and command is not None:
                    preparing = not prepared
                    child_command = command_for('prepare', env) if preparing else command
                    app = subprocess.Popen(child_command, cwd=ROOT, env=env, start_new_session=os.name == 'posix')
                    log('database_preparation_started' if preparing else 'application_started')
                time.sleep(0.5)
            return 0
    finally:
        stop(app)
        stop(ssh)
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main():
    parser = argparse.ArgumentParser(description='Central com túnel SSH privado MontuDB.')
    parser.add_argument('mode', choices=('prepare', 'web', 'worker', 'check'))
    args = parser.parse_args()
    try:
        return supervise(args.mode)
    except TunnelError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        # Não registrar exceções que possam trazer URL, chave ou resposta SSH.
        print('Falha ao iniciar túnel/aplicação. Confira a configuração do ambiente.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())