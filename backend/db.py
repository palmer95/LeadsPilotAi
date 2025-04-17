# db.py
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

# SQLite DB
engine = create_engine("sqlite:///leads.db", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Models
class Company(Base):
    __tablename__ = 'companies'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    description = Column(Text)
    leads = relationship("Lead", back_populates="company")

class Lead(Base):
    __tablename__ = 'leads'
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'))
    name = Column(String)
    contact = Column(String)
    interested_package = Column(String) 
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    company = relationship("Company", back_populates="leads")

# Create tables
Base.metadata.create_all(engine)
