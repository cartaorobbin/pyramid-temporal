"""SQLAlchemy models for testing."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import zope.sqlalchemy

Base = declarative_base()


class User(Base):
    """User model for testing pyramid-temporal integration."""
    
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False, unique=True)
    enriched = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, name='{self.name}', email='{self.email}', enriched={self.enriched})>"
    
    def to_dict(self) -> dict:
        """Convert user to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'enriched': self.enriched,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


def create_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(engine)


def get_session_maker(engine):
    """Create a session maker bound to the engine."""
    return sessionmaker(bind=engine)


def get_tm_session(session_factory, transaction_manager, request=None):
    """Get a SQLAlchemy session instance backed by a transaction.
    
    This function follows the legal-entity pattern for transaction management.
    The session will be automatically committed or rolled back based on the
    transaction manager state.
    
    Args:
        session_factory: SQLAlchemy session factory
        transaction_manager: Transaction manager instance
        request: Optional request object for context
        
    Returns:
        SQLAlchemy session registered with transaction manager
    """
    dbsession = session_factory(info={"request": request})
    zope.sqlalchemy.register(dbsession, transaction_manager=transaction_manager)
    return dbsession
