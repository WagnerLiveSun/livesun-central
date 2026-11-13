from datetime import timedelta, date
from flask import current_app
from app.extensions import db
from app.models import AssinaturaModulo, Entitlement
from app.models.base import now, iso


def effective(subscription):
    allowed = (subscription.status in ('ATIVA', 'TRIAL') and subscription.produto.ativo
               and subscription.cliente.status == 'ATIVO'
               and (not subscription.data_fim or subscription.data_fim >= date.today()))
    if subscription.status == 'TRIAL' and subscription.trial_ate and subscription.trial_ate <= date.today():
        allowed = False
    limits, modules = {}, []
    if allowed:
        plan = subscription.plano
        for key, value in {'usuarios': plan.limite_usuarios, 'registros': plan.limite_registros,
                           'armazenamento_mb': plan.limite_armazenamento_mb}.items():
            if value is not None:
                limits[key] = value
        limits.update(plan.limite_personalizado_json or {})
        for entry in db.session.scalars(db.select(Entitlement).filter_by(assinatura_id=subscription.id)):
            if entry.ativo:
                limits[entry.chave] = entry.limite if entry.limite is not None else entry.valor
        if subscription.produto.permite_modulos:
            modules = [{'codigo': m.modulo.codigo, 'limite': m.limite}
                       for m in db.session.scalars(db.select(AssinaturaModulo).filter_by(
                           assinatura_id=subscription.id, liberado=True)) if m.modulo.ativo]
    generated = now()
    return {'cliente_id': str(subscription.cliente_id), 'produto': subscription.produto.codigo,
            'assinatura_id': subscription.id, 'status': subscription.status, 'plano': subscription.plano.codigo,
            'acesso_produto': allowed, 'modulos': modules, 'limites': limits,
            'versao': subscription.versao, 'bonificada': subscription.cortesia,
            'bonificacao_ate': subscription.cortesia_ate.isoformat() if subscription.cortesia_ate else None,
            'excluida_em': iso(subscription.excluida_em), 'gerado_em': iso(generated),
            'valido_ate': iso(generated + timedelta(seconds=current_app.config['ENTITLEMENT_TTL_SECONDS']))}