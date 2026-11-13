from argon2.exceptions import VerificationError, InvalidHashError
from flask import render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user
from app.extensions import db, limiter
from app.models import UsuarioCentral
from app.security import passwords, operator_required
from app.services.auditoria_service import audit
from . import admin

_DUMMY_HASH = passwords.hash('not-a-real-login-password')


@admin.route('/login', methods=['GET', 'POST'])
@limiter.limit('5 per minute', methods=['POST'])
def login_view():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('senha', '')
        user = db.session.scalar(db.select(UsuarioCentral).filter_by(email=email)) if len(email) <= 254 else None
        try:
            valid = len(password) <= 128 and passwords.verify(user.senha_hash if user else _DUMMY_HASH, password)
        except (VerificationError, InvalidHashError):
            valid = False
        if user and user.ativo and valid:
            session.clear()
            login_user(user, fresh=True)
            session.permanent = True
            audit(user, 'LOGIN_OPERADOR')
            db.session.commit()
            return redirect(url_for('admin.dashboard'))
        flash('Credenciais inválidas.', 'error')
    return render_template('login.html')


@admin.post('/logout')
@operator_required()
def logout_view():
    logout_user()
    session.clear()
    return redirect(url_for('admin.login_view'))