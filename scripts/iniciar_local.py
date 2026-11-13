"""Inicializador local: preserva dados, aplica migrations e inicia web + worker."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def check_database(app):
    from sqlalchemy import inspect, text
    from app.extensions import db
    with app.app_context():
        with db.engine.connect() as connection:
            connection.execute(text('SELECT 1'))
            tables = set(inspect(connection).get_table_names())
            if tables and 'alembic_version' not in tables:
                raise RuntimeError('Banco nao vazio e sem controle Alembic. Nenhuma tabela foi alterada. Revise o banco antes de continuar.')


def prepare(app):
    from flask_migrate import upgrade, check
    from sqlalchemy import inspect
    from app.extensions import db
    from app.cli import seed
    from app.models import UsuarioCentral
    check_database(app)
    with app.app_context():
        upgrade()
        check()
        seed()
        count = db.session.scalar(db.select(db.func.count()).select_from(UsuarioCentral).where(
            UsuarioCentral.perfil == 'superadmin', UsuarioCentral.ativo.is_(True)))
        print(f'Banco preparado: {len(inspect(db.engine).get_table_names())} tabelas; migrations e seed OK.', flush=True)
        return bool(count)


def main():
    parser = argparse.ArgumentParser(description='Inicializar LiveSun Central para testes locais.')
    parser.add_argument('--prepare-only', action='store_true', help='Somente migrations e seed, sem servidor ou prompts.')
    parser.add_argument('--port', type=int, default=5001)
    parser.add_argument('--env-file', default='.env', help='Perfil local de ambiente, relativo à raiz do projeto.')
    args = parser.parse_args()
    os.chdir(ROOT)
    env_path = Path(args.env_file)
    if not env_path.is_absolute():
        env_path = ROOT / env_path
    if not env_path.is_file():
        print('Configure o arquivo de ambiente selecionado antes de iniciar.', file=sys.stderr)
        return 1
    from dotenv import load_dotenv
    # Subprocessos web/worker/admin herdam o mesmo perfil, sem trocar o .env padrão.
    load_dotenv(env_path, override=True)
    from app import create_app
    app = create_app()
    if app.config['APP_ENV'] != 'development':
        print('Este inicializador e exclusivo para APP_ENV=development.', file=sys.stderr)
        return 1
    try:
        if not args.prepare_only:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', args.port))
        has_admin = prepare(app)
    except Exception as error:
        # Nao exibir excecao SQLAlchemy: pode conter dados/credenciais.
        print('Falha ao preparar banco ou porta local. Confira o banco, o perfil de ambiente e as migrations. Tipo: ' + type(error).__name__, file=sys.stderr)
        return 1
    if args.prepare_only:
        if not has_admin:
            print('Primeiro inicio interativo solicitara criacao do superadmin.')
        return 0
    if not has_admin:
        print('\nCrie o primeiro operador. Nao existe senha padrao.\nEscolha uma senha nao vazia; ela nao aparece ao digitar.', flush=True)
        result = subprocess.run([sys.executable, '-m', 'flask', '--app', 'wsgi', 'create-admin'], cwd=ROOT)
        if result.returncode:
            return result.returncode
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    worker = subprocess.Popen([sys.executable, '-m', 'flask', '--app', 'wsgi', 'worker'],
                              cwd=ROOT, creationflags=creationflags)
    url = f'http://127.0.0.1:{args.port}/login'
    print(f'\nLiveSun Central: {url}\nPressione Ctrl+C para encerrar web e worker.\n', flush=True)
    def open_when_ready():
        import requests
        for _ in range(40):
            try:
                if requests.get(url, timeout=1).status_code == 200:
                    webbrowser.open(url)
                    return
            except requests.RequestException:
                pass
            time.sleep(0.5)
    threading.Thread(target=open_when_ready, daemon=True).start()
    try:
        # Sem debugger/reloader; acesso apenas pela maquina local.
        app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        worker.terminate()
        try:
            worker.wait(timeout=10)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait()
    return 0


if __name__ == '__main__':
    sys.exit(main())