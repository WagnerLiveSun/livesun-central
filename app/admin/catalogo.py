import json
import secrets
from typing import get_args
from flask import abort, render_template, request, redirect, url_for
from flask_login import current_user
from app.extensions import db
from app.models import Cliente, Produto, Plano, Modulo, UsuarioCentral, PlanoModulo
from app.schemas import ClienteInput, ProdutoInput, PlanoInput, ModuloInput, UserInput
from app.security import operator_required
from app.services.catalogo_service import save, set_plan_modules
from app.services.auditoria_service import snapshot
from app.services.plano_codigo import commercial_code, COMMERCIAL_TIERS
from app.services.assinatura_service import BusinessError
from . import admin

CATALOG = {
    'clientes': (Cliente, ClienteInput, 'Clientes'),
    'produtos': (Produto, ProdutoInput, 'Produtos'),
    'planos': (Plano, PlanoInput, 'Planos'),
    'modulos': (Modulo, ModuloInput, 'Módulos'),
    'usuarios': (UsuarioCentral, UserInput, 'Usuários do Central'),
}


def permitted(kind):
    allowed = ('superadmin',) if kind == 'usuarios' else ('superadmin', 'comercial')
    if current_user.perfil not in allowed:
        abort(403)


@admin.get('/cadastros/<kind>')
@operator_required()
def listing(kind):
    if kind not in CATALOG:
        abort(404)
    if kind == 'usuarios' and current_user.perfil != 'superadmin':
        abort(403)
    model, schema, title = CATALOG[kind]
    query = db.select(model)
    product_id = request.args.get('produto',type=int)
    if kind in ('planos','modulos') and product_id:
        query = query.where(model.produto_id == product_id)
    page = db.paginate(query.order_by(model.id.desc()), per_page=30, max_per_page=30)
    rows = [snapshot(obj) for obj in page.items]
    columns = {'clientes': ['id', 'codigo_externo', 'razao_social', 'email_principal', 'status'],
               'produtos': ['id', 'codigo', 'nome', 'ativo'],
               'planos': ['id', 'produto_id', 'nome', 'valor_mensal', 'ativo'],
               'modulos': ['id', 'produto_id', 'codigo', 'nome'],
               'usuarios': ['id', 'nome', 'email', 'perfil', 'ativo']}[kind]
    writable = current_user.perfil == 'superadmin' or (kind != 'usuarios' and current_user.perfil == 'comercial')
    return render_template('list.html', title=title, rows=rows, columns=columns, page=page,
                           kind=kind, writable=writable)


def form_values(schema):
    data = {}
    for name, field in schema.model_fields.items():
        raw = request.form.get(name, '').strip()
        annotation = str(field.annotation)
        if field.annotation is bool:
            data[name] = name in request.form
        elif 'dict' in annotation or 'list' in annotation:
            try:
                data[name] = json.loads(raw or ('{}' if 'dict' in annotation else '[]'))
            except json.JSONDecodeError:
                raise BusinessError('Formato inválido no campo ' + name.replace('_',' ') + '. Informe JSON válido.') from None
        elif raw:
            data[name] = raw
        elif field.is_required():
            data[name] = raw
        elif field.default is None:
            data[name] = None
    return data


@admin.route('/cadastros/<kind>/novo', methods=['GET', 'POST'])
@admin.route('/cadastros/<kind>/<int:identifier>/editar', methods=['GET', 'POST'])
@operator_required('superadmin', 'comercial')
def edit(kind, identifier=None):
    if kind not in CATALOG:
        abort(404)
    permitted(kind)
    model, schema, title = CATALOG[kind]
    obj = db.get_or_404(model, identifier) if identifier else None
    products = db.session.scalars(db.select(Produto).where(db.or_(Produto.ativo.is_(True),
        Produto.id == (obj.produto_id if obj and kind in ('planos','modulos') else 0))).order_by(Produto.nome)).all() if kind in ('planos','modulos') else []
    if kind == 'modulos':
        products = [p for p in products if p.permite_modulos or (obj and obj.produto_id == p.id)]
    if request.method == 'POST':
        data = form_values(schema)
        if kind == 'planos':
            product = db.session.get(Produto, request.form.get('produto_id',type=int))
            if product and product.codigo == 'COMERCIAL':
                if obj:
                    data['codigo'] = obj.codigo
                    if commercial_code(obj.codigo,data.get('periodicidade','mensal')) != obj.codigo:
                        raise BusinessError('Para outro ciclo, cadastre um novo plano. O código contratado é preservado.')
                else:
                    selected = request.form.get('categoria_comercial') or data.get('codigo') or data.get('nome')
                    data['codigo'] = commercial_code(selected,data.get('periodicidade','mensal'))
            elif obj:
                data['codigo'] = obj.codigo
            elif not data.get('codigo'):
                data['codigo'] = ('PROPOSTAS' if product and product.codigo == 'PROPOSTAS'
                                  else 'PLN_' + secrets.token_hex(4).upper())
        if not identifier and kind == 'clientes' and not data.get('codigo_externo'):
            data['codigo_externo'] = 'CLI_' + secrets.token_hex(6).upper()
        if not identifier and kind in ('produtos','planos','modulos') and not data.get('codigo'):
            data['codigo'] = {'produtos':'PRD_','planos':'PLN_','modulos':'MOD_'}[kind] + secrets.token_hex(4).upper()
        obj = save(model, schema, data, identifier)
        db.session.commit()
        return redirect(url_for('admin.listing', kind=kind))
    if kind == 'planos':
        selected_product = obj.produto_id if obj else request.args.get('produto',type=int)
        if selected_product not in {p.id for p in products}:
            selected_product = products[0].id if products else None
        selected = db.session.get(Produto, selected_product) if selected_product else None
        included = {m.modulo_id for m in db.session.scalars(db.select(PlanoModulo).filter_by(plano_id=obj.id,liberado=True))} if obj else set()
        return render_template('plan_form.html',title='Editar plano' if obj else 'Novo plano',
            obj=obj,products=products,selected_product=selected_product,
            selected_commercial=bool(selected and selected.codigo=='COMERCIAL'),tiers=COMMERCIAL_TIERS,
            included_modules=included)
    values = snapshot(obj) if obj else {}
    fields = []
    for name, field in schema.model_fields.items():
        annotation = str(field.annotation)
        default = field.get_default(call_default_factory=True) if not field.is_required() else ''
        value = values.get(name, default)
        if name == 'senha':
            value = ''
        is_json = 'dict' in annotation or 'list' in annotation
        if is_json:
            value = json.dumps(value if isinstance(value, (dict, list)) else ({} if 'dict' in annotation else []), ensure_ascii=False)
        choices = []
        if name == 'codigo' and kind == 'planos' and obj and obj.produto.codigo == 'COMERCIAL':
            choices = [(code,code) for code in ('BASIC','INTERMEDIATE','PREMIUM','BASIC_ANUAL','INTERMEDIATE_ANUAL','PREMIUM_ANUAL')]
        elif name == 'produto_id':
            choices = [(p.id,p.nome) for p in products]
        elif 'Literal' in annotation:
            choices = [(v,v.capitalize()) for v in get_args(field.annotation)]
        is_select = bool(choices) or name == 'produto_id' or 'Literal' in annotation
        fields.append({'name': name, 'choices': choices, 'value': value if value is not None else '',
                       'locked': bool(obj and name in ('produto_id','codigo')),
                       'type': 'checkbox' if field.annotation is bool else 'password' if name == 'senha'
                       else 'select' if is_select else 'textarea' if is_json or name in ('descricao', 'observacoes') else 'text',
                       'required': field.is_required() and not (not identifier and name in ('codigo','codigo_externo'))})
    included = {m.modulo_id for m in db.session.scalars(db.select(PlanoModulo).filter_by(plano_id=obj.id, liberado=True))} if kind == 'planos' and obj else set()
    return render_template('form.html', title=title, fields=fields, obj=obj, kind=kind, included_modules=included)


@admin.post('/planos/<int:identifier>/modulos')
@operator_required('superadmin', 'comercial')
def plan_modules(identifier):
    plan = db.get_or_404(Plano, identifier)
    module_ids = ([int(value) for value in request.form.get('modulo_ids', '').split(',') if value.strip()]
                  if 'modulo_ids' in request.form else [int(value) for value in request.form.getlist('modulo_id')])
    set_plan_modules(plan, module_ids)
    db.session.commit()
    return redirect(url_for('admin.edit', kind='planos', identifier=identifier))