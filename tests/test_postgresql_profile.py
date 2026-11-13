from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]


def test_postgresql_launcher_selects_separate_profile():
    batch=(ROOT.parent/'Iniciar_LiveSun_Central_PostgreSQL.bat').read_text(encoding='utf-8')
    assert '--env-file .env.postgresql %*' in batch
    assert 'PASSWORD' not in batch
    original=(ROOT.parent/'Iniciar_LiveSun_Central.bat').read_text(encoding='utf-8')
    assert 'scripts\\iniciar_local.py %*' in original


def test_profiles_ignored_except_example():
    lines=(ROOT/'.gitignore').read_text(encoding='utf-8').splitlines()
    assert '.env' in lines and '.env.*' in lines and '!.env.example' in lines


def test_startup_loads_selected_profile_before_factory():
    source=(ROOT/'scripts/iniciar_local.py').read_text(encoding='utf-8')
    ast.parse(source)
    assert "parser.add_argument('--env-file'" in source
    assert source.index('load_dotenv(env_path, override=True)')<source.index('app = create_app()')


def test_database_preparer_has_no_destructive_operations():
    source=(ROOT/'scripts/preparar_postgresql_local.py').read_text(encoding='utf-8')
    ast.parse(source)
    assert 'DROP DATABASE' not in source and 'drop_all' not in source
    assert "dbname='postgres'" in source
    assert "sql.Identifier(url.database)" in source
    assert 'print(str(error))' not in source