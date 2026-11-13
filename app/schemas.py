from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, hide_input_in_errors=True)


class ClienteInput(Schema):
    codigo_externo: str = Field(min_length=1, max_length=100)
    razao_social: str = Field(min_length=1, max_length=200)
    nome_fantasia: str | None = Field(default=None, max_length=200)
    cnpj_cpf: str | None = Field(default=None, max_length=18)
    email_principal: EmailStr
    telefone: str | None = Field(default=None, max_length=30)
    status: Literal['ATIVO', 'INATIVO', 'EXCLUIDO'] = 'ATIVO'
    observacoes: str | None = Field(default=None, max_length=5000)


class ProdutoInput(Schema):
    codigo: str = Field(pattern=r'^[A-Z][A-Z0-9_]{1,49}$')
    nome: str = Field(min_length=1, max_length=150)
    descricao: str | None = Field(default=None, max_length=5000)
    url_producao: str | None = Field(default=None, max_length=500)
    permite_multiplos_planos: bool = False
    permite_modulos: bool = False
    ativo: bool = True


class PlanoInput(Schema):
    produto_id: int = Field(gt=0)
    codigo: str = Field(pattern=r'^[A-Z][A-Z0-9_]{1,49}$')
    nome: str = Field(min_length=1, max_length=150)
    descricao: str | None = Field(default=None, max_length=5000)
    valor_mensal: Decimal = Field(default=Decimal('0'), ge=0, max_digits=12, decimal_places=2)
    periodicidade: Literal['mensal', 'anual'] = 'mensal'
    limite_usuarios: int | None = Field(default=None, ge=0)
    limite_registros: int | None = Field(default=None, ge=0)
    limite_armazenamento_mb: int | None = Field(default=None, ge=0)
    limite_personalizado_json: dict[str, int] = Field(default_factory=dict)
    ativo: bool = True

    @field_validator('limite_personalizado_json')
    @classmethod
    def limits(cls, value):
        if len(value) > 50 or any(v < 0 or len(k) > 100 for k, v in value.items()):
            raise ValueError('Limites inválidos.')
        return value


class ModuloInput(Schema):
    produto_id: int = Field(gt=0)
    codigo: str = Field(pattern=r'^[A-Z][A-Z0-9_]{1,49}$')
    nome: str = Field(min_length=1, max_length=150)
    descricao: str | None = Field(default=None, max_length=5000)
    depende_de: list[str] = Field(default_factory=list, max_length=50)
    obrigatorio: bool = False
    ativo: bool = True


class AssinaturaInput(Schema):
    cliente_id: int = Field(gt=0)
    produto_id: int = Field(gt=0)
    plano_id: int = Field(gt=0)
    status: Literal['TRIAL', 'ATIVA'] = 'TRIAL'
    data_inicio: date | None = None
    data_fim: date | None = None
    data_proxima_cobranca: date | None = None


class StatusInput(Schema):
    status: Literal['ATIVA', 'SUSPENSA', 'BLOQUEADA', 'CANCELADA', 'EXPIRADA', 'EXCLUIDA']
    motivo: str = Field(min_length=3, max_length=500)


class PlanChange(Schema):
    plano_id: int = Field(gt=0)


class ModuleChange(Schema):
    modulo_id: int = Field(gt=0)
    liberado: bool
    limite: int | None = Field(default=None, ge=0)


class LimitsInput(Schema):
    limites: dict[str, int] = Field(max_length=50)

    @field_validator('limites')
    @classmethod
    def valid_limits(cls, value):
        return PlanoInput.limits(value)


class WebhookInput(Schema):
    url_webhook: str = Field(max_length=500)
    webhook_secret: str = Field(min_length=32, max_length=200)


class ChargeInput(Schema):
    assinatura_id: int = Field(gt=0)
    competencia: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    valor: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    vencimento: date
    gateway: str | None = Field(default=None, max_length=50)
    referencia_externa: str | None = Field(default=None, max_length=150)
    observacoes: str | None = Field(default=None, max_length=5000)


class UserInput(Schema):
    nome: str = Field(min_length=1, max_length=150)
    email: EmailStr
    perfil: Literal['superadmin', 'comercial', 'financeiro', 'suporte', 'auditor']
    ativo: bool = True
    senha: str | None = Field(default=None, min_length=1, max_length=128)


class CadastroProdutoInput(Schema):
    evento_id: str = Field(pattern=r'^cad_[a-f0-9]{32}$')
    empresa_id: int = Field(gt=0, le=2147483647)
    razao_social: str = Field(min_length=1, max_length=200)
    nome_fantasia: str | None = Field(default=None, max_length=200)
    cnpj_cpf: str = Field(pattern=r'^\d{11}(?:\d{3})?$')
    email: EmailStr
    telefone: str | None = Field(default=None, max_length=30)
    responsavel: str = Field(min_length=1, max_length=150)