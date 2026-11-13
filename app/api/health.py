from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from . import api


@api.get('/health')
def health():
    try:
        db.session.execute(text('SELECT 1'))
        return {'servico': 'ok', 'banco': 'ok'}
    except SQLAlchemyError:
        db.session.rollback()
        return {'servico': 'ok', 'banco': 'indisponivel'}, 503