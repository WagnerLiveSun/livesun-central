"""Códigos de integração do Comercial, separados dos nomes exibidos."""
import unicodedata
from .assinatura_service import BusinessError

COMMERCIAL_TIERS = (('BASIC', 'Básico'), ('INTERMEDIATE', 'Intermediário'), ('PREMIUM', 'Premium'))


def commercial_code(value, period):
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', str(value or ''))
                         if not unicodedata.combining(c)).strip().upper()
    normalized = normalized.removesuffix('_ANUAL')
    aliases = {'BASICO':'BASIC', 'INTERMEDIARIO':'INTERMEDIATE',
               'BASIC':'BASIC', 'INTERMEDIATE':'INTERMEDIATE', 'PREMIUM':'PREMIUM'}
    if normalized not in aliases:
        raise BusinessError('Selecione a categoria do plano Comercial: Básico, Intermediário ou Premium.')
    if period not in ('mensal','anual'):
        raise BusinessError('Selecione a periodicidade mensal ou anual.')
    return aliases[normalized] + ('_ANUAL' if period == 'anual' else '')