from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Text,
    Boolean,
    JSON
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# SQLite DB
engine = create_engine("sqlite:///leads.db", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Models
class Client(Base):
    __tablename__ = 'clients'
    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)
    business_name = Column(String, nullable=False)
    location = Column(String)
    description = Column(Text)
    calendar_id = Column(String)
    calendar_tokens = Column(JSON)
    faqs = relationship("FAQ", back_populates="client", cascade="all, delete-orphan")
    workflows = relationship("Workflow", back_populates="client", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="client", cascade="all, delete-orphan")
    users = relationship("AdminUser", back_populates="client", cascade="all, delete-orphan")

class AdminUser(Base):
    __tablename__ = 'admin_users'

    id                   = Column(Integer, primary_key=True)
    email                = Column(String, unique=True, nullable=False)
    password_hash        = Column(String, nullable=True)
    invite_token         = Column(String, unique=True, nullable=True)
    invite_token_expiry  = Column(DateTime, nullable=True)
    client_id            = Column(Integer, ForeignKey('clients.id'), nullable=False)
    role                 = Column(String, default='admin')
    created_at           = Column(DateTime, default=datetime.utcnow)

    client               = relationship("Client", back_populates="users")

class FAQ(Base):
    __tablename__ = 'faqs'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0)
    client = relationship("Client", back_populates="faqs")

class Workflow(Base):
    __tablename__ = 'workflows'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    name = Column(String, nullable=False)
    config = Column(JSON, nullable=False)
    enabled = Column(Boolean, default=True)
    client = relationship("Client", back_populates="workflows")

class Lead(Base):
    __tablename__ = 'leads'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    responses = Column(JSON)
    booking_status = Column(String, default='new')
    event_link = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow) # noqa:UP003
    updated_at = Column(DateTime, default=datetime.utcnow) # noqa:UP003
    client = relationship("Client", back_populates="leads")

# Create tables
Base.metadata.create_all(engine)
