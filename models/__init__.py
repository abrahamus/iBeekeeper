from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .user import User
from .transaction import Transaction
from .document import Document
from .transaction_code import TransactionCode
from .app_settings import AppSettings