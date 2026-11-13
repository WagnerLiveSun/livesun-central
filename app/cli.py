import os
import time
import click
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from flask import current_app
from app.extensions import db
from app.models import Produto, Plano, UsuarioCentral, Assinatura
from app.security import passwords, service_token, encrypt
from app.services.auditoria_service import audit


class AdminPassword(click.ParamType):
    name = 'senha'

    def convert(self, value, param, ctx):
        if not isinstance(value, str) or not value.strip():
            self.fail('Informe uma senha não vazia. Tente novamente.', param, ctx)
        if len(value.strip()) > 128:
            self.fail('A senha excede o limite técnico de 128 caracteres.', param, ctx)
        return value


def seed():
    product = db.session.scalar(db.select(Produto).filter_by(codigo='PROPOSTAS'))
    if product is None:
        product = Produto(codigo='PROPOSTAS', nome='LiveSun Propostas',
                          url_producao='https://propostas.livesun.com.br',
                          url_webhook='https://propostas.livesun.com.br/webhooks/assinatura',
                          permite_multiplos_planos=False, permite_modulos=False, ativo=True)
        db.session.add(product)
        db.session.flush()
        audit(product, 'SEED_PRODUTO')
    if not db.session.scalar(db.select(Plano).filter_by(produto_id=product.id, codigo='PROPOSTAS')):
        plan = Plano(produto_id=product.id, codigo='PROPOSTAS', nome='LiveSun Propostas',
                     descricao='Plano único do LiveSun Propostas', valor_mensal=0, periodicidade='mensal',
                     limite_personalizado_json={}, ativo=True)
        db.session.add(plan)
        db.session.flush()
        audit(plan, 'SEED_PLANO')
    secret = os.getenv('PROPOSTAS_WEBHOOK_SECRET')
    if secret and not product.webhook_secret:
        if len(secret) < 32:
            raise click.ClickException('PROPOSTAS_WEBHOOK_SECRET deve ter 32 caracteres ou mais.')
        product.webhook_secret = encrypt(secret)
    db.session.commit()


def seed_comercial():
    product = db.session.scalar(db.select(Produto).filter_by(codigo='COMERCIAL'))
    if product is None:
        product = Produto(codigo='COMERCIAL', nome='LiveSun Comercial', permite_multiplos_planos=True,
                          permite_modulos=False, ativo=True)
        db.session.add(product)
        db.session.flush()
        audit(product, 'SEED_PRODUTO_COMERCIAL')
        db.session.commit()


def bootstrap_admin():
    """Primeira instalação em nuvem pelo ambiente, sem senha padrão ou shell web."""
    if db.session.scalar(db.select(UsuarioCentral.id).where(UsuarioCentral.perfil == 'superadmin',
                                                         UsuarioCentral.ativo.is_(True))):
        return
    email = os.getenv('BOOTSTRAP_ADMIN_EMAIL', '').strip()
    password = os.getenv('BOOTSTRAP_ADMIN_PASSWORD', '')
    if not email and not password:
        return
    if not email or not password:
        raise click.ClickException('Configure ambas as variáveis BOOTSTRAP_ADMIN_EMAIL e BOOTSTRAP_ADMIN_PASSWORD.')
    from app.schemas import UserInput
    from app.services.catalogo_service import save
    try:
        save(UsuarioCentral, UserInput, {'nome': os.getenv('BOOTSTRAP_ADMIN_NAME', 'Administrador'),
            'email': email.lower(), 'senha': password, 'perfil': 'superadmin', 'ativo': True})
        db.session.commit()
    except (ValidationError, SQLAlchemyError, ValueError):
        db.session.rollback()
        raise click.ClickException('Não foi possível criar o primeiro administrador. Confira as variáveis de bootstrap.') from None
    click.echo('Primeiro superadmin criado. Remova BOOTSTRAP_ADMIN_PASSWORD do ambiente após o primeiro acesso.')


def register_commands(app):
    @app.cli.command('seed')
    def seed_command():
        seed()
        seed_comercial()
        bootstrap_admin()
        click.echo('Produto PROPOSTAS e plano único configurados; nenhum cliente ou operador criado.')

    @app.cli.command('create-admin')
    @click.option('--email', prompt=True)
    @click.option('--nome', prompt=True)
    @click.option('--password', prompt='Senha', hide_input=True,
                  confirmation_prompt='Confirme a senha', type=AdminPassword())
    def create_admin(email, nome, password):
        from app.schemas import UserInput
        from app.services.catalogo_service import save
        try:
            save(UsuarioCentral, UserInput, {'nome': nome, 'email': email.lower(), 'senha': password,
                                             'perfil': 'superadmin', 'ativo': True})
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            fields = ', '.join(sorted({str(item['loc'][0]) for item in error.errors(include_input=False)}))
            raise click.ClickException('Cadastro inválido. Confira os campos: ' + fields + '.') from None
        except IntegrityError:
            db.session.rollback()
            raise click.ClickException('Já existe um operador com esse e-mail. Use outro e-mail ou entre com a conta existente.') from None
        except SQLAlchemyError:
            db.session.rollback()
            raise click.ClickException('Não foi possível salvar o operador. Verifique a conexão com o banco.') from None
        click.echo('Superadmin criado.')

    @app.cli.command('service-token')
    @click.argument('codigo')
    @click.option('--hours', default=24, type=click.IntRange(1, 8760))
    @click.option('--scope', multiple=True, type=click.Choice(['read', 'write', 'webhooks']))
    @click.option('--rotate', is_flag=True, help='Revoga todos os JWTs anteriores do produto.')
    def token(codigo, hours, scope, rotate):
        product = db.session.scalar(db.select(Produto).filter_by(codigo=codigo))
        if product is None:
            raise click.ClickException('Produto inexistente.')
        if rotate:
            product.token_version += 1
        audit(product, 'TOKEN_SERVICO_EMITIDO')
        db.session.commit()
        click.echo(service_token(product, scope or ('read',), hours))

    @app.cli.command('worker')
    @click.option('--once', is_flag=True)
    def worker(once):
        from app.services.webhook_service import dispatch_one
        from app.services.cobranca_service import maintenance
        last_maintenance = 0
        while True:
            try:
                if time.monotonic() - last_maintenance > 60:
                    maintenance()
                    from app.services.webhook_service import recover_deliveries
                    recover_deliveries()
                    from app.services.cadastro_service import pull_pending
                    pull_pending()
                    last_maintenance = time.monotonic()
                sent = dispatch_one()
                from app.services.asaas_service import process_one as process_asaas
                from app.services.purga_service import process_one as process_purge
                sent = process_asaas() or sent
                sent = process_purge() or sent
                from app.services.cadastro_service import deliver_one
                sent = deliver_one() or sent
            except Exception:
                db.session.rollback()
                current_app.logger.error('worker', extra={'safe_event': 'worker_iteration_failed'})
                sent = False
            finally:
                db.session.remove()
            if once:
                break
            if not sent:
                time.sleep(1)

    @app.cli.command('reconcile')
    @click.option('--repair', is_flag=True)
    def reconcile(repair):
        from app.services.reconciliacao_service import reconcile_all
        result = reconcile_all(repair)
        click.echo(f"Verificadas: {result['verificadas']}; divergentes: {result['divergentes']}; indisponíveis: {result['indisponiveis']}")