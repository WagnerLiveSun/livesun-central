"""Descoberta explícita de empresas Propostas; sem acesso direto ao banco do produto."""
from urllib.parse import urlsplit
import requests
from app.extensions import db
from app.models import Produto
from app.schemas import CadastroProdutoInput
from app.security import decrypt
from .assinatura_service import BusinessError
from .cadastro_service import receive
from .webhook_service import validate_destination, signed_headers


def product():
    row = db.session.scalar(db.select(Produto).where(Produto.codigo == 'PROPOSTAS'))
    if not row or not row.ativo or not row.url_producao or not row.webhook_secret:
        raise BusinessError('Configure a conexão e o segredo do produto Propostas antes de consultar empresas.')
    return row


def fetch(path):
    row = product()
    url = row.url_producao.rstrip('/') + path
    validate_destination(url)
    parsed = urlsplit(url)
    signed_path = parsed.path + ('?' + parsed.query if parsed.query else '')
    headers = signed_headers(decrypt(row.webhook_secret), signed_path.encode())
    try:
        with requests.Session() as http:
            http.trust_env = False
            with http.get(url, headers=headers, timeout=(3, 15), allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise BusinessError('Propostas indisponível ou integração não publicada/configurada. Confira o segredo compartilhado.')
                raw = response.raw.read(262145, decode_content=True)
                if len(raw) > 262144:
                    raise BusinessError('Resposta do Propostas excede o tamanho permitido.')
                import json
                data = json.loads(raw)
        if not isinstance(data, dict) or data.get('produto') != 'PROPOSTAS':
            raise ValueError()
        return data
    except (requests.RequestException, OSError, ValueError, TypeError):
        raise BusinessError('Não foi possível consultar empresas do Propostas. Nenhum cadastro foi alterado.') from None


def validate_company(item):
    if not isinstance(item, dict) or not isinstance(item.get('dados'), dict):
        raise BusinessError('Resposta de empresas inválida.')
    identifier = item['dados'].get('empresa_id')
    linked = item.get('cliente_id')
    if (type(identifier) is not int or not 1 <= identifier <= 2147483647
            or type(item.get('ativo')) is not bool
            or (linked is not None and (type(linked) is not int or linked <= 0))):
        raise BusinessError('Identificação da empresa inválida.')
    return item


def list_companies(cursor=0):
    data = fetch(f'/central/empresas?apos={cursor}')
    rows, next_cursor = data.get('empresas'), data.get('proximo')
    if not isinstance(rows, list) or len(rows) > 50:
        raise BusinessError('Lista de empresas inválida.')
    last = cursor
    for item in rows:
        validate_company(item)
        if item['dados']['empresa_id'] <= last:
            raise BusinessError('Ordem de empresas inválida.')
        last = item['dados']['empresa_id']
    if next_cursor is not None and (type(next_cursor) is not int or next_cursor != last or next_cursor <= cursor):
        raise BusinessError('Paginação de empresas inválida.')
    return rows, next_cursor


def prepare_registration(identifier):
    item = validate_company(fetch(f'/central/empresas/{identifier}').get('empresa'))
    if item['dados']['empresa_id'] != identifier:
        raise BusinessError('Propostas retornou outra empresa. Operação cancelada.')
    if not item['ativo'] or item['cliente_id'] is not None:
        raise BusinessError('Empresa inativa ou já vinculada no Propostas. Revise o vínculo existente.')
    data = CadastroProdutoInput.model_validate(item['dados']).model_dump(mode='json')
    row, _ = receive(product(), data)
    return row