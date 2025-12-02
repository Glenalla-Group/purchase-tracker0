"""
Example of how to integrate database storage for extracted email information.

This is a template showing how to add SQLite/PostgreSQL storage.
Uncomment and modify as needed for your use case.
"""

# Uncomment to use:
# pip install sqlalchemy asyncpg  # For PostgreSQL
# pip install sqlalchemy aiosqlite  # For SQLite

"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class EmailRecord(Base):
    '''Database model for storing processed emails.'''
    
    __tablename__ = 'emails'
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(255), unique=True, index=True, nullable=False)
    thread_id = Column(String(255), index=True)
    subject = Column(String(500))
    sender = Column(String(255), index=True)
    received_date = Column(DateTime)
    processed_at = Column(DateTime, default=datetime.utcnow)
    
    # Extracted information
    order_number = Column(String(100), index=True)
    total_amount = Column(String(50))
    merchant = Column(String(255), index=True)
    purchase_date = Column(String(100))
    
    # Raw data
    html_content = Column(Text)
    extracted_data = Column(JSON)  # Store all extracted data as JSON
    
    # Processing status
    extraction_successful = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)


class PurchaseItem(Base):
    '''Database model for storing individual purchase items.'''
    
    __tablename__ = 'purchase_items'
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey('emails.id'), nullable=False)
    item_name = Column(String(500))
    quantity = Column(Integer)
    price = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


# Database setup
# For SQLite (development):
# DATABASE_URL = "sqlite+aiosqlite:///./purchase_tracker.db"

# For PostgreSQL (production):
# DATABASE_URL = "postgresql+asyncpg://user:password@localhost/purchase_tracker"

async def init_database(database_url: str):
    '''Initialize database and create tables.'''
    engine = create_async_engine(database_url, echo=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    return engine


async def get_session(engine) -> AsyncSession:
    '''Get database session.'''
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


async def save_email_record(session: AsyncSession, extracted_info: dict):
    '''
    Save extracted email information to database.
    
    Args:
        session: Database session
        extracted_info: ExtractedInfo object from email parser
    '''
    record = EmailRecord(
        message_id=extracted_info['email_id'],
        subject=extracted_info['subject'],
        sender=extracted_info['sender'],
        order_number=extracted_info.get('order_number'),
        total_amount=extracted_info.get('total_amount'),
        merchant=extracted_info.get('merchant'),
        purchase_date=extracted_info.get('purchase_date'),
        extracted_data=extracted_info['extracted_data'],
        extraction_successful=extracted_info['extraction_successful'],
        error_message=extracted_info.get('error_message'),
        processed_at=datetime.utcnow()
    )
    
    session.add(record)
    await session.commit()
    await session.refresh(record)
    
    return record


async def get_email_by_message_id(session: AsyncSession, message_id: str):
    '''Retrieve email record by message ID.'''
    from sqlalchemy import select
    
    result = await session.execute(
        select(EmailRecord).where(EmailRecord.message_id == message_id)
    )
    return result.scalar_one_or_none()


async def get_recent_purchases(session: AsyncSession, limit: int = 10):
    '''Get recent purchase records.'''
    from sqlalchemy import select
    
    result = await session.execute(
        select(EmailRecord)
        .where(EmailRecord.order_number.isnot(None))
        .order_by(EmailRecord.processed_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


# Integration with FastAPI
# Add to app/main.py:

'''
from examples.database_example import init_database, get_session

@app.on_event("startup")
async def startup():
    app.state.db_engine = await init_database("sqlite+aiosqlite:///./purchase_tracker.db")

@app.on_event("shutdown")
async def shutdown():
    await app.state.db_engine.dispose()
'''

# Integration with webhook.py:

'''
from examples.database_example import save_email_record, get_session

async def process_email_notification(message_id: str, db_session: AsyncSession):
    # ... existing code ...
    
    if extracted_info.extraction_successful:
        # Save to database
        record = await save_email_record(db_session, extracted_info.dict())
        logger.info(f"Saved email record with ID {record.id}")
'''
"""

print(__doc__)



