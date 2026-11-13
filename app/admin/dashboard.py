from datetime import date, timedelta
from flask import render_template, current_app
from app.extensions import db
from app.models import Cliente, Assinatura, Cobranca, WebhookEntrega, Auditoria, SolicitacaoCadastro
from app.security import operator_required
from . import admin


@admin.get('/')
@operator_required()
def dashboard():
    def count(model, *criteria):
        return db.session.scalar(db.select(db.func.count()).select_from(model).where(*criteria))
    metrics = {'Clientes': count(Cliente)}
    metrics['Cadastros aguardando habilitação'] = count(SolicitacaoCadastro, SolicitacaoCadastro.status=='PENDENTE')
    metrics['Vínculos aguardando confirmação'] = count(SolicitacaoCadastro, SolicitacaoCadastro.status=='VINCULO_PENDENTE')
    for status in ('ATIVA', 'TRIAL', 'SUSPENSA', 'BLOQUEADA', 'CANCELADA'):
        metrics[status] = count(Assinatura, Assinatura.status == status)
    metrics['Próximos vencimentos (7 dias)'] = count(Assinatura, Assinatura.slot_vigente == 1,
        Assinatura.data_proxima_cobranca.between(date.today(), date.today() + timedelta(days=7)))
    metrics['Cobranças abertas'] = count(Cobranca, Cobranca.status == 'ABERTA')
    metrics['Cobranças atrasadas'] = count(Cobranca, Cobranca.status == 'ATRASADA')
    metrics['Webhooks com falha'] = count(WebhookEntrega, WebhookEntrega.status.in_(['FALHA', 'ESGOTADA']))
    recent = db.session.scalars(db.select(Auditoria).order_by(Auditoria.id.desc()).limit(15)).all()
    return render_template('dashboard.html', title='Visão geral', metrics=metrics, recent=recent)


@admin.get('/configuracoes')
@operator_required()
def settings():
    return render_template('settings.html', title='Configurações', engine=current_app.config['DB_ENGINE'],
                           ttl=current_app.config['ENTITLEMENT_TTL_SECONDS'])