import os
from sqlalchemy import create_engine, Column, Integer, String, Date, Float
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import date

# Database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/stocks_db")

# SQLAlchemy setup
Base = declarative_base()
engine = create_engine(DATABASE_URL, pool_pre_ping=True) # Add pool_pre_ping for connection health
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class StockRecord(Base):
    __tablename__ = "stock_records"

    id = Column(Integer, primary_key=True, index=True)
    company_code = Column(String, index=True, nullable=False) # Not unique, as same stock can be purchased multiple times
    purchased_amount = Column(Float, nullable=False)
    purchased_status = Column(String, default="recorded")
    request_data = Column(Date, default=date.today)

    def __repr__(self):
        return f"<StockRecord(company_code='{self.company_code}', purchased_amount={self.purchased_amount})>"

def create_db_and_tables():
    """Creates all defined database tables."""
    Base.metadata.create_all(engine)

def get_db():
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()