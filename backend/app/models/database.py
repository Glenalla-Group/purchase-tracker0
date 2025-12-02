from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, Date, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


# ============================================================================
# AUTH MODELS
# ============================================================================

class UserRole(Base):
    """
    User Roles table - stores available user roles (admin, user, etc.)
    """
    __tablename__ = 'user_roles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)  # 'admin', 'user', etc.
    description = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    users = relationship("User", back_populates="role")
    
    def __repr__(self):
        return f"<UserRole(id={self.id}, name={self.name})>"


class User(Base):
    """
    Users table - stores user accounts for authentication
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)  # Full name
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=True)  # Hashed password (nullable for OAuth users)
    role_id = Column(Integer, ForeignKey('user_roles.id'), nullable=False)
    
    # OAuth fields
    google_id = Column(String(255), unique=True, nullable=True, index=True)  # Google OAuth ID
    oauth_provider = Column(String(50), nullable=True)  # 'google', 'facebook', etc.
    
    # Metadata
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    role = relationship("UserRole", back_populates="users")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class PasswordResetToken(Base):
    """
    Password Reset Tokens table - stores tokens for password reset requests
    """
    __tablename__ = 'password_reset_tokens'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")
    
    def __repr__(self):
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, used={self.used})>"


# ============================================================================
# EXISTING MODELS
# ============================================================================


class WholesaleEnum(enum.Enum):
    """Enum for wholesale status"""
    YES = "yes"
    NO = "no"
    NA = "n/a"


class LocationEnum(enum.Enum):
    """Enum for retailer locations"""
    EU = "EU"
    USA = "USA"
    CANADA = "CANADA"
    AU = "AU"
    UK = "UK"
    SA = "SA"


class AsinBank(Base):
    """
    ASIN Bank table - stores all ASINs with their associated lead_id and size
    """
    __tablename__ = 'asin_bank'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(String(100), nullable=False, index=True)
    size = Column(String(50))
    asin = Column(String(100), nullable=False)
    
    # Relationships
    oa_sourcing_asin1 = relationship("OASourcing", foreign_keys="OASourcing.asin1_id", back_populates="asin1_ref")
    oa_sourcing_asin2 = relationship("OASourcing", foreign_keys="OASourcing.asin2_id", back_populates="asin2_ref")
    oa_sourcing_asin3 = relationship("OASourcing", foreign_keys="OASourcing.asin3_id", back_populates="asin3_ref")
    oa_sourcing_asin4 = relationship("OASourcing", foreign_keys="OASourcing.asin4_id", back_populates="asin4_ref")
    oa_sourcing_asin5 = relationship("OASourcing", foreign_keys="OASourcing.asin5_id", back_populates="asin5_ref")
    oa_sourcing_asin6 = relationship("OASourcing", foreign_keys="OASourcing.asin6_id", back_populates="asin6_ref")
    oa_sourcing_asin7 = relationship("OASourcing", foreign_keys="OASourcing.asin7_id", back_populates="asin7_ref")
    oa_sourcing_asin8 = relationship("OASourcing", foreign_keys="OASourcing.asin8_id", back_populates="asin8_ref")
    oa_sourcing_asin9 = relationship("OASourcing", foreign_keys="OASourcing.asin9_id", back_populates="asin9_ref")
    oa_sourcing_asin10 = relationship("OASourcing", foreign_keys="OASourcing.asin10_id", back_populates="asin10_ref")
    oa_sourcing_asin11 = relationship("OASourcing", foreign_keys="OASourcing.asin11_id", back_populates="asin11_ref")
    oa_sourcing_asin12 = relationship("OASourcing", foreign_keys="OASourcing.asin12_id", back_populates="asin12_ref")
    oa_sourcing_asin13 = relationship("OASourcing", foreign_keys="OASourcing.asin13_id", back_populates="asin13_ref")
    oa_sourcing_asin14 = relationship("OASourcing", foreign_keys="OASourcing.asin14_id", back_populates="asin14_ref")
    oa_sourcing_asin15 = relationship("OASourcing", foreign_keys="OASourcing.asin15_id", back_populates="asin15_ref")

    def __repr__(self):
        return f"<AsinBank(id={self.id}, lead_id={self.lead_id}, size={self.size}, asin={self.asin})>"


class OASourcing(Base):
    """
    OA Sourcing table - Lead Submittal data
    """
    __tablename__ = 'oa_sourcing'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime)
    submitted_by = Column(String(100))
    lead_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Foreign key to retailers table
    retailer_id = Column(Integer, ForeignKey('retailers.id'), nullable=True, index=True)
    
    product_name_pt_input = Column(String(500))
    product_name = Column(String(500))
    product_sku = Column(String(200))
    retailer_link = Column(Text)
    amazon_link = Column(Text)
    unique_id = Column(String(200))  # Product unique ID from retailer link (e.g., HJ7395 from FootLocker)
    purchased = Column(String(50))
    purchase_more_if_available = Column(String(50))
    pros = Column(Text)
    cons = Column(Text)
    other_notes_concerns = Column(Text)
    head_of_product_review_notes = Column(Text)
    feedback_and_notes_on_quantity = Column(Text)
    suggested_total_qty = Column(Integer)
    pairs_per_lead_id = Column(Integer)
    pairs_per_sku = Column(Integer)
    ppu_including_ship = Column(Float)
    rsp = Column(Float)
    margin = Column(Float)
    promo_code = Column(String(100))
    sales_rank = Column(String(100))
    
    # ASIN references - foreign keys to asin_bank
    asin1_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin1_recommended_quantity = Column(Integer)
    
    asin2_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin2_recommended_quantity = Column(Integer)
    
    asin3_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin3_recommended_quantity = Column(Integer)
    
    asin4_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin4_recommended_quantity = Column(Integer)
    
    asin5_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin5_recommended_quantity = Column(Integer)
    
    asin6_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin6_recommended_quantity = Column(Integer)
    
    asin7_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin7_recommended_quantity = Column(Integer)
    
    asin8_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin8_recommended_quantity = Column(Integer)
    
    asin9_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin9_recommended_quantity = Column(Integer)
    
    asin10_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin10_recommended_quantity = Column(Integer)
    
    asin11_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin11_recommended_quantity = Column(Integer)
    
    asin12_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin12_recommended_quantity = Column(Integer)
    
    asin13_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin13_recommended_quantity = Column(Integer)
    
    asin14_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin14_recommended_quantity = Column(Integer)
    
    asin15_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True)
    asin15_recommended_quantity = Column(Integer)
    
    # Additional fields
    asin1_buy_box = Column(Float)
    asin1_new_price = Column(Float)
    pick_pack_fee = Column(Float)
    referral_fee = Column(Float)
    total_fee = Column(Float)
    margin_using_rsp = Column(Float)
    monitored = Column(Boolean)
    sourcer = Column(String(100))
    
    # Relationships
    retailer = relationship("Retailer", back_populates="oa_sourcing_leads")
    
    asin1_ref = relationship("AsinBank", foreign_keys=[asin1_id])
    asin2_ref = relationship("AsinBank", foreign_keys=[asin2_id])
    asin3_ref = relationship("AsinBank", foreign_keys=[asin3_id])
    asin4_ref = relationship("AsinBank", foreign_keys=[asin4_id])
    asin5_ref = relationship("AsinBank", foreign_keys=[asin5_id])
    asin6_ref = relationship("AsinBank", foreign_keys=[asin6_id])
    asin7_ref = relationship("AsinBank", foreign_keys=[asin7_id])
    asin8_ref = relationship("AsinBank", foreign_keys=[asin8_id])
    asin9_ref = relationship("AsinBank", foreign_keys=[asin9_id])
    asin10_ref = relationship("AsinBank", foreign_keys=[asin10_id])
    asin11_ref = relationship("AsinBank", foreign_keys=[asin11_id])
    asin12_ref = relationship("AsinBank", foreign_keys=[asin12_id])
    asin13_ref = relationship("AsinBank", foreign_keys=[asin13_id])
    asin14_ref = relationship("AsinBank", foreign_keys=[asin14_id])
    asin15_ref = relationship("AsinBank", foreign_keys=[asin15_id])
    
    purchase_trackers = relationship("PurchaseTracker", back_populates="oa_sourcing")

    def __repr__(self):
        return f"<OASourcing(id={self.id}, lead_id={self.lead_id}, product_name={self.product_name})>"


class PurchaseTracker(Base):
    """
    Purchase Tracker table - tracks individual purchases
    ULTRA-OPTIMIZED: Minimal redundancy, maximum normalization
    """
    __tablename__ = 'purchase_tracker'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign keys (required)
    oa_sourcing_id = Column(Integer, ForeignKey('oa_sourcing.id'), nullable=False, index=True)
    asin_bank_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True, index=True)
    
    # Denormalized for performance (optional but recommended)
    lead_id = Column(String(100), index=True)
    
    # Purchase metadata
    date = Column(Date)
    platform = Column(String(100))
    order_number = Column(String(200))
    # NOTE: supplier removed - same as oa_sourcing.retailer_name
    # NOTE: unique_id removed - product unique_id belongs in oa_sourcing table
    
    # Quantities
    og_qty = Column(Integer)
    final_qty = Column(Integer)
    
    # Pricing (if different from planned - otherwise use oa_sourcing.ppu/rsp)
    rsp = Column(Float)  # Actual selling price if different from planned
    
    # Fulfillment tracking (NUMBERS not dates - like workflow stages: 1, 2, 3, etc.)
    address = Column(Text)
    shipped_to_pw = Column(Integer)  # Number indicating stage/status
    arrived = Column(Integer)  # Number indicating stage/status
    checked_in = Column(Integer)  # Number indicating stage/status
    shipped_out = Column(Integer)  # Number indicating stage/status
    delivery_date = Column(Date)  # Actual date field
    status = Column(String(100))
    location = Column(String(200))
    in_bound = Column(Boolean)
    tracking = Column(String(200))
    
    # FBA fields
    outbound_name = Column(String(500))
    fba_shipment = Column(String(200))
    fba_msku = Column(String(200))
    concat = Column(String(500))
    audited = Column(Boolean, default=False)
    
    # Refund tracking
    cancelled_qty = Column(Integer)
    amt_of_cancelled_qty_credit_card = Column(Float)
    amt_of_cancelled_qty_gift_card = Column(Float)
    expected_refund_amount = Column(Float)
    amount_refunded = Column(Float)
    refund_status = Column(String(100))
    refund_method = Column(String(100))
    date_of_refund = Column(Date)
    
    # Misc
    notes = Column(Text)
    validation_bank = Column(String(200))
    
    # Relationships
    oa_sourcing = relationship("OASourcing", back_populates="purchase_trackers")
    asin_bank_ref = relationship("AsinBank")
    
    # Properties to access removed fields
    @property
    def ppu(self):
        """Get PPU from oa_sourcing (planned price)"""
        return self.oa_sourcing.ppu_including_ship if self.oa_sourcing else None
    
    @property
    def asin(self):
        """Get ASIN from asin_bank"""
        return self.asin_bank_ref.asin if self.asin_bank_ref else None
    
    @property
    def size(self):
        """Get size from asin_bank"""
        return self.asin_bank_ref.size if self.asin_bank_ref else None
    
    @property
    def total_spend(self):
        """Calculate total spend: ppu * final_qty"""
        ppu = self.ppu
        if ppu and self.final_qty:
            return round(ppu * self.final_qty, 2)
        return 0
    
    @property
    def profit(self):
        """Calculate profit: (rsp - ppu) * final_qty"""
        ppu = self.ppu
        rsp = self.rsp or (self.oa_sourcing.rsp if self.oa_sourcing else 0)
        if rsp and ppu and self.final_qty:
            return round((rsp - ppu) * self.final_qty, 2)
        return 0
    
    @property
    def margin_percent(self):
        """Calculate margin percentage: ((rsp - ppu) / rsp) * 100"""
        ppu = self.ppu
        rsp = self.rsp or (self.oa_sourcing.rsp if self.oa_sourcing else 0)
        if rsp and ppu and rsp > 0:
            return round(((rsp - ppu) / rsp) * 100, 2)
        return 0
    
    @property
    def product_name(self):
        """Get product name from oa_sourcing"""
        return self.oa_sourcing.product_name if self.oa_sourcing else None
    
    @property
    def sourced_by(self):
        """Get sourcer from oa_sourcing"""
        return self.oa_sourcing.submitted_by if self.oa_sourcing else None
    
    @property
    def sku_upc(self):
        """Get SKU/UPC from oa_sourcing"""
        return self.oa_sourcing.product_sku if self.oa_sourcing else None
    
    @property
    def supplier(self):
        """Get supplier from retailer relationship"""
        if self.oa_sourcing and self.oa_sourcing.retailer:
            return self.oa_sourcing.retailer.name
        return None

    def __repr__(self):
        return f"<PurchaseTracker(id={self.id}, lead_id={self.lead_id}, order={self.order_number})>"


class Checkin(Base):
    """
    Checkin table - tracks items checked in at warehouse/fulfillment center
    """
    __tablename__ = 'checkin'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_number = Column(String(200), index=True)  # Link to purchase order
    item_name = Column(String(500))  # Product name
    asin_bank_id = Column(Integer, ForeignKey('asin_bank.id'), nullable=True, index=True)  # FK to asin_bank
    quantity = Column(Integer, nullable=False)  # Number of items checked in
    checked_in_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # Date & time of check-in
    
    # Relationship
    asin_bank_ref = relationship("AsinBank", backref="checkins")
    
    # Properties for easy access
    @property
    def asin(self):
        """Get ASIN from asin_bank"""
        return self.asin_bank_ref.asin if self.asin_bank_ref else None
    
    @property
    def size(self):
        """Get size from asin_bank"""
        return self.asin_bank_ref.size if self.asin_bank_ref else None

    def __repr__(self):
        return f"<Checkin(id={self.id}, order={self.order_number}, item={self.item_name}, qty={self.quantity})>"


class Retailer(Base):
    """
    Retailer table - stores retailer information and statistics
    """
    __tablename__ = 'retailers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True, index=True)
    link = Column(Text)  # Retailer website link
    wholesale = Column(String(10))  # yes, no, n/a
    cancel_for_bulk = Column(Boolean, default=False)  # yes/no
    location = Column(String(50))  # EU, USA, CANADA, AU, UK, SA
    shopify = Column(Boolean, default=False)  # yes/no
    
    # Statistics (calculated fields)
    total_spend = Column(Float, default=0.0)
    total_qty_of_items_ordered = Column(Integer, default=0)
    percent_of_cancelled_qty = Column(Float, default=0.0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    oa_sourcing_leads = relationship("OASourcing", back_populates="retailer")

    def __repr__(self):
        return f"<Retailer(id={self.id}, name={self.name}, location={self.location})>"

