"""Preparação explícita de clínicas existentes, sem ler o banco do produto."""
import json
from urllib.parse import urlsplit
import requests
from app.extensions import db
from app.models import Produto
from app.schemas import CadastroProdutoInput
from app.security import decrypt
from .assinatura_service import BusinessError
from .cadastro_service import receive
from .webhook_service import signed_headers, validate_destination


def product():
    row = db.session.scalar(db.select(Produto).where(Produto.codigo == 'CLINICAS'))
    if not row or not row.ativo or not row.url_producao or not row.webhook_secret:
        raise BusinessError('Configure a URL e o segredo do produto Clínicas antes de consultar empresas.')
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
                    raise BusinessError('Clínicas não confirmou a consulta. Confira o serviço e o segredo compartilhado.')
                raw = response.raw.read(262145, decode_content=True)
                if len(raw) > 262144:
                    raise BusinessError('Resposta do Clínicas excede o tamanho permitido.')
                data = json.loads(raw)
        if not isinstance(data, dict) or data.get('produto') != 'CLINICAS':
            raise ValueError()
        return data
    except (requests.RequestException, OSError, ValueError, TypeError):
        raise BusinessError('Não foi possível consultar Clínicas. Nenhum cadastro foi alterado.') from None


def validate_company(item):
    if not isinstance(item, dict) or not isinstance(item.get('dados'), dict):
        raise BusinessError('Resposta de clínicas inválida.')
    identifier = item['dados'].get('empresa_id')
    linked = item.get('cliente_id')
    if (type(identifier) is not int or not 1 <= identifier <= 2147483647
            or type(item.get('ativo')) is not bool or type(item.get('cadastro_novo')) is not bool
            or type(item.get('gestor_ativo')) is not bool
            or (linked is not None and (type(linked) is not int or linked <= 0))):
        raise BusinessError('Identificação da clínica inválida.')
    return item


def list_companies(cursor=0):
    data = fetch(f'/central/empresas?apos={cursor}')
    rows, next_cursor = data.get('empresas'), data.get('proximo')
    if not isinstance(rows, list) or len(rows) > 50:
        raise BusinessError('Lista de clínicas inválida.')
    last = cursor
    for item in rows:
        validate_company(item)
        if item['dados']['empresa_id'] <= last:
            raise BusinessError('Ordem de clínicas inválida.')
        last = item['dados']['empresa_id']
    if next_cursor is not None and (type(next_cursor) is not int or next_cursor != last or next_cursor <= cursor):
        raise BusinessError('Paginação de clínicas inválida.')
    return rows, next_cursor


def prepare_registration(identifier):
    item = validate_company(fetch(f'/central/empresas/{identifier}').get('empresa'))
    if (item['dados']['empresa_id'] != identifier or not item['ativo'] or item['cliente_id'] is not None
            or item['cadastro_novo'] or not item['gestor_ativo']):
        raise BusinessError('Clínica inativa, já vinculada, sem gestor ativo ou originada por autocadastro. Revise antes de continuar.')
    try:
        data = CadastroProdutoInput.model_validate(item['dados']).model_dump(mode='json')
    except ValueError:
        raise BusinessError('Complete CPF/CNPJ, e-mail e dados do responsável no Clínicas antes de preparar o vínculo.') from None
    return receive(product(), data)[0]