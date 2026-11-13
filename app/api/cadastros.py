from flask import request, g
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import SolicitacaoCadastro
from app.security import service_required
from app.services.cadastro_service import receive, status_payload
from . import api


@api.post('/cadastros')
@service_required('read')
def register_customer_request():
    # read permite apenas solicitar análise; não cria assinatura nem concede acesso.
    payload = request.get_json()
    try:
        row, created = receive(g.service_product,payload)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        from app.schemas import CadastroProdutoInput
        data=CadastroProdutoInput.model_validate(payload)
        row=db.session.scalar(db.select(SolicitacaoCadastro).filter_by(
            produto_id=g.service_product.id,empresa_origem=str(data.empresa_id),evento_origem=data.evento_id))
        if not row:
            raise
        created=False
    return status_payload(row), 202 if created else 200