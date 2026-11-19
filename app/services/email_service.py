"""Brevo simples; timeout/resposta perdida nunca provocam reenvio cego."""
import requests
from flask import current_app, render_template


def send_template_email(recipient, name, subject, template, context=None):
    cfg = current_app.config
    html = render_template(template, nome=name, **(context or {}))
    if not cfg.get('BREVO_API_KEY') or not cfg.get('BREVO_SENDER_EMAIL'):
        return 'FALHA', 'CONFIGURACAO'
    try:
        with requests.Session() as http:
            http.trust_env = False
            response = http.post('https://api.brevo.com/v3/smtp/email',
                headers={'api-key': cfg['BREVO_API_KEY'], 'accept': 'application/json'},
                json={'sender': {'name': cfg['BREVO_SENDER_NAME'], 'email': cfg['BREVO_SENDER_EMAIL']},
                    'to': [{'email': recipient, 'name': name}], 'subject': subject,
                    'htmlContent': html},
                timeout=(5, 15), allow_redirects=False)
        if response.status_code == 201:
            return 'ACEITA_BREVO', None
        if response.status_code == 429:
            return 'FALHA_TEMPORARIA', 'LIMITE_PROVEDOR'
        if 400 <= response.status_code < 500:
            return 'FALHA', 'RECUSADO_PROVEDOR'
        return 'INCERTO', 'RESPOSTA_NAO_CONCLUSIVA'
    except requests.RequestException:
        return 'INCERTO', 'COMUNICACAO'


def send_access_email(recipient, name, html):
    cfg = current_app.config
    if not cfg.get('BREVO_API_KEY') or not cfg.get('BREVO_SENDER_EMAIL'):
        return 'FALHA', 'CONFIGURACAO'
    try:
        with requests.Session() as http:
            http.trust_env = False
            response = http.post('https://api.brevo.com/v3/smtp/email',
                headers={'api-key': cfg['BREVO_API_KEY'], 'accept': 'application/json'},
                json={'sender': {'name': cfg['BREVO_SENDER_NAME'], 'email': cfg['BREVO_SENDER_EMAIL']},
                    'to': [{'email': recipient, 'name': name}],
                    'subject': 'Seu acesso ao LiveSun Propostas foi liberado', 'htmlContent': html},
                timeout=(5, 15), allow_redirects=False)
        if response.status_code == 201:
            return 'ACEITA_BREVO', None
        if response.status_code == 429:
            return 'FALHA_TEMPORARIA', 'LIMITE_PROVEDOR'
        if 400 <= response.status_code < 500:
            return 'FALHA', 'RECUSADO_PROVEDOR'
        return 'INCERTO', 'RESPOSTA_NAO_CONCLUSIVA'
    except requests.RequestException:
        return 'INCERTO', 'COMUNICACAO'