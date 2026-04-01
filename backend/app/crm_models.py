from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func 
from sqlalchemy.orm import relationship 
 
from .database import Base 
 
class Customer(Base): 
    __tablename__ = 'customers' 
 
    id = Column(Integer, primary_key=True, index=True) 
    name = Column(String(256), nullable=False) 
    email = Column(String(128)) 
    phone = Column(String(64)) 
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=True) 
    account_status = Column(String(64), default='inactive') 
    consent_status = Column(String(32), default='unknown') 
    engagement_score = Column(Integer, default=0) 
    last_engaged_at = Column(DateTime(timezone=True)) 
    customer_metadata = Column('metadata', String, default='') 
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()) 
 
    vendor = relationship('Vendor') 
