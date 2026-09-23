"""SQLAlchemy Declarative Base。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的独立声明基类。"""
