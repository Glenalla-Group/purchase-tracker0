"""
Unified (retailer, email_type) classification layer for retailer emails.

Classifies incoming emails into retailer + type before routing to processors.
Check order: SHIPPING and CANCELLATION first (to avoid misclassification),
then ORDER_CONFIRMATION.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.models.email import EmailData

from app.services.footlocker_parser import FootlockerEmailParser
from app.services.champs_parser import ChampsEmailParser
from app.services.dicks_parser import DicksEmailParser
from app.services.hibbett_parser import HibbettEmailParser
from app.services.dtlr_parser import DTLREmailParser
from app.services.shoepalace_parser import ShoepalaceEmailParser
from app.services.snipes_parser import SnipesEmailParser
from app.services.finishline_parser import FinishLineEmailParser
from app.services.shopsimon_parser import ShopSimonEmailParser
from app.services.jdsports_parser import JDSportsEmailParser
from app.services.revolve_parser import RevolveEmailParser
from app.services.asos_parser import ASOSEmailParser
from app.services.urban_parser import UrbanOutfittersEmailParser
from app.services.bloomingdales_parser import BloomingdalesEmailParser
from app.services.anthropologie_parser import AnthropologieEmailParser
from app.services.nike_parser import NikeEmailParser
from app.services.carbon38_parser import Carbon38EmailParser
from app.services.gazelle_parser import GazelleEmailParser
from app.services.netaporter_parser import NetAPorterEmailParser
from app.services.fit2run_parser import Fit2RunEmailParser
from app.services.sns_parser import SNSEmailParser
from app.services.adidas_parser import AdidasEmailParser
from app.services.concepts_parser import ConceptsEmailParser
from app.services.sneaker_parser import SneakerPoliticsEmailParser
from app.services.orleans_parser import OrleansEmailParser
from app.services.endclothing_parser import ENDClothingEmailParser
from app.services.shopwss_parser import ShopWSSEmailParser

logger = logging.getLogger(__name__)


class EmailType(str, Enum):
    """Type of retailer email."""
    CONFIRMATION = "confirmation"
    SHIPPING = "shipping"
    CANCELLATION = "cancellation"


@dataclass
class ClassificationResult:
    """Result of email classification."""
    retailer_id: str       # e.g. "footlocker", "nike"
    email_type: EmailType  # CONFIRMATION, SHIPPING, or CANCELLATION
    display_name: str      # e.g. "Footlocker", "Nike"


class RetailerEmailClassifier:
    """
    Classifies retailer emails into (retailer_id, email_type).
    
    Detection order:
    1. SHIPPING / CANCELLATION for retailers that support them
       (Footlocker, Champs, Dick's, Hibbett, DTLR)
    2. ORDER_CONFIRMATION for all supported retailers
    """

    def __init__(self):
        self._footlocker = FootlockerEmailParser()
        self._champs = ChampsEmailParser()
        self._dicks = DicksEmailParser()
        self._hibbett = HibbettEmailParser()
        self._dtlr = DTLREmailParser()
        self._shoepalace = ShoepalaceEmailParser()
        self._snipes = SnipesEmailParser()
        self._finishline = FinishLineEmailParser()
        self._shopsimon = ShopSimonEmailParser()
        self._jdsports = JDSportsEmailParser()
        self._urban = UrbanOutfittersEmailParser()
        self._bloomingdales = BloomingdalesEmailParser()
        self._anthropologie = AnthropologieEmailParser()
        self._nike = NikeEmailParser()
        self._carbon38 = Carbon38EmailParser()
        self._gazelle = GazelleEmailParser()
        self._netaporter = NetAPorterEmailParser()
        self._fit2run = Fit2RunEmailParser()
        self._sns = SNSEmailParser()
        self._adidas = AdidasEmailParser()
        self._concepts = ConceptsEmailParser()
        self._sneaker = SneakerPoliticsEmailParser()
        self._orleans = OrleansEmailParser()
        self._revolve = RevolveEmailParser()
        self._asos = ASOSEmailParser()
        self._endclothing = ENDClothingEmailParser()
        self._shopwss = ShopWSSEmailParser()

    def classify(self, email_data: EmailData) -> Optional[ClassificationResult]:
        """
        Classify email into (retailer_id, email_type).
        
        Returns None if not a supported retailer email.
        """
        # 1. Check shipping/cancellation first (avoids misclassification)
        result = self._check_shipping_or_cancellation(email_data)
        if result:
            return result

        # 2. Check order confirmation
        return self._check_order_confirmation(email_data)

    def _check_shipping_or_cancellation(self, email_data: EmailData) -> Optional[ClassificationResult]:
        """Check for shipping or cancellation emails. Returns first match."""
        # ASOS shipping FIRST: "Your order's on its way!" is unique - avoid other parsers stealing via broad "order" match
        subject_lower = (email_data.subject or "").lower()
        sender_lower = (email_data.sender or "").lower()
        if "on its way" in subject_lower:
            if "orders@asos.com" in sender_lower or "glenallagroupc@gmail.com" in sender_lower:
                return ClassificationResult("asos", EmailType.SHIPPING, "ASOS")
        
        # Footlocker (with kids variant)
        if self._footlocker.is_footlocker_email(email_data):
            if self._footlocker.is_shipping_email(email_data):
                is_kids = self._footlocker.is_kids_footlocker_email(email_data)
                rid = "kidsfootlocker" if is_kids else "footlocker"
                disp = "Kids Foot Locker" if is_kids else "Footlocker"
                return ClassificationResult(rid, EmailType.SHIPPING, disp)
            if self._footlocker.is_cancellation_email(email_data):
                is_kids = self._footlocker.is_kids_footlocker_email(email_data)
                rid = "kidsfootlocker" if is_kids else "footlocker"
                disp = "Kids Foot Locker" if is_kids else "Footlocker"
                return ClassificationResult(rid, EmailType.CANCELLATION, disp)

        # Champs
        if self._champs.is_champs_email(email_data):
            if self._champs.is_shipping_email(email_data):
                return ClassificationResult("champs", EmailType.SHIPPING, "Champs Sports")
            if self._champs.is_cancellation_email(email_data):
                return ClassificationResult("champs", EmailType.CANCELLATION, "Champs Sports")

        # Dick's
        if self._dicks.is_dicks_email(email_data):
            if self._dicks.is_shipping_email(email_data):
                return ClassificationResult("dicks", EmailType.SHIPPING, "Dick's")
            if self._dicks.is_cancellation_email(email_data):
                return ClassificationResult("dicks", EmailType.CANCELLATION, "Dick's")

        # Hibbett
        if self._hibbett.is_hibbett_email(email_data):
            if self._hibbett.is_shipping_email(email_data):
                return ClassificationResult("hibbett", EmailType.SHIPPING, "Hibbett")
            if self._hibbett.is_cancellation_email(email_data):
                return ClassificationResult("hibbett", EmailType.CANCELLATION, "Hibbett")

        # DTLR
        if self._dtlr.is_dtlr_email(email_data):
            if self._dtlr.is_shipping_email(email_data):
                return ClassificationResult("dtlr", EmailType.SHIPPING, "DTLR")
            if self._dtlr.is_cancellation_email(email_data):
                return ClassificationResult("dtlr", EmailType.CANCELLATION, "DTLR")

        # Finish Line (shipping/update emails - includes partial ship+cancel)
        if self._finishline.is_finishline_email(email_data):
            if self._finishline.is_shipping_email(email_data):
                return ClassificationResult("finishline", EmailType.SHIPPING, "Finish Line")
            if self._finishline.is_cancellation_email(email_data):
                return ClassificationResult("finishline", EmailType.CANCELLATION, "Finish Line")

        # JD Sports (same HTML template as Finish Line, different from email)
        if self._jdsports.is_jdsports_email(email_data):
            if self._jdsports.is_shipping_email(email_data):
                return ClassificationResult("jdsports", EmailType.SHIPPING, "JD Sports")
            if self._jdsports.is_cancellation_email(email_data):
                return ClassificationResult("jdsports", EmailType.CANCELLATION, "JD Sports")

        # Revolve (shipping and cancellation)
        if self._revolve.is_revolve_email(email_data):
            if self._revolve.is_shipping_email(email_data):
                return ClassificationResult("revolve", EmailType.SHIPPING, "Revolve")
            if self._revolve.is_cancellation_email(email_data):
                return ClassificationResult("revolve", EmailType.CANCELLATION, "Revolve")
        
        # ASOS (shipping only)
        if self._asos.is_asos_email(email_data):
            if self._asos.is_shipping_email(email_data):
                return ClassificationResult("asos", EmailType.SHIPPING, "ASOS")

        # Snipes (shipping and cancellation)
        if self._snipes.is_snipes_email(email_data):
            if self._snipes.is_shipping_email(email_data):
                return ClassificationResult("snipes", EmailType.SHIPPING, "Snipes")
            if self._snipes.is_cancellation_email(email_data):
                return ClassificationResult("snipes", EmailType.CANCELLATION, "Snipes")

        # Shoe Palace (shipping and cancellation)
        if self._shoepalace.is_shoepalace_email(email_data):
            if self._shoepalace.is_shipping_email(email_data):
                return ClassificationResult("shoepalace", EmailType.SHIPPING, "Shoe Palace")
            if self._shoepalace.is_cancellation_email(email_data):
                return ClassificationResult("shoepalace", EmailType.CANCELLATION, "Shoe Palace")

        # END Clothing (shipping)
        if self._endclothing.is_endclothing_email(email_data):
            if self._endclothing.is_shipping_email(email_data):
                return ClassificationResult("endclothing", EmailType.SHIPPING, "END Clothing")

        # ShopWSS (cancellation first, then shipping) - "Order X has been canceled" vs "is about to ship"
        if self._shopwss.is_shopwss_email(email_data):
            if self._shopwss.is_cancellation_email(email_data):
                return ClassificationResult("shopwss", EmailType.CANCELLATION, "ShopWSS")
            if self._shopwss.is_shipping_email(email_data):
                return ClassificationResult("shopwss", EmailType.SHIPPING, "ShopWSS")

        return None

    def _check_order_confirmation(self, email_data: EmailData) -> Optional[ClassificationResult]:
        """Check for order confirmation. Returns first match."""
        subject_lower = (email_data.subject or "").lower()
        sender_lower = (email_data.sender or "").lower()

        # Snipes EARLY: "Confirmation of Your SNIPES Order #SNP..." is unique - avoid other parsers stealing
        if "snipes order" in subject_lower:
            if "noreply@snipesusa.com" in sender_lower or "no-reply@snipesusa.com" in sender_lower or "glenallagroupc@gmail.com" in sender_lower:
                if self._snipes.is_order_confirmation_email(email_data):
                    return ClassificationResult("snipes", EmailType.CONFIRMATION, "Snipes")

        # END Clothing EARLY: "Your END. order confirmation" is unique - filter END Clothing clearly
        if "end. order" in subject_lower or "your end" in subject_lower and "order confirmation" in subject_lower:
            if "info@orders.endclothing.com" in sender_lower or "glenallagroupc@gmail.com" in sender_lower:
                if self._endclothing.is_order_confirmation_email(email_data):
                    return ClassificationResult("endclothing", EmailType.CONFIRMATION, "END Clothing")

        # ShopWSS EARLY: "Order #1361825686 was received!" is unique - filter ShopWSS clearly
        if "was received" in subject_lower and "order" in subject_lower:
            if "help@shopwss.com" in sender_lower or "glenallagroupc@gmail.com" in sender_lower:
                if self._shopwss.is_order_confirmation_email(email_data):
                    return ClassificationResult("shopwss", EmailType.CONFIRMATION, "ShopWSS")

        confirmation_checks = [
            ("footlocker", "Footlocker", self._footlocker, "is_footlocker_email"),
            ("endclothing", "END Clothing", self._endclothing, "is_endclothing_email"),
            ("shopwss", "ShopWSS", self._shopwss, "is_shopwss_email"),
            ("champs", "Champs", self._champs, "is_champs_email"),
            ("dicks", "Dick's", self._dicks, "is_dicks_email"),
            ("hibbett", "Hibbett", self._hibbett, "is_hibbett_email"),
            ("shoepalace", "Shoe Palace", self._shoepalace, "is_shoepalace_email"),
            ("snipes", "Snipes", self._snipes, "is_snipes_email"),
            ("finishline", "Finish Line", self._finishline, "is_finishline_email"),
            ("shopsimon", "Shop Simon", self._shopsimon, "is_shopsimon_email"),
            ("jdsports", "JD Sports", self._jdsports, "is_jdsports_email"),
            ("revolve", "Revolve", self._revolve, "is_revolve_email"),
            ("asos", "ASOS", self._asos, "is_asos_email"),
            ("urbanoutfitters", "Urban Outfitters", self._urban, "is_urban_email"),
            ("bloomingdales", "Bloomingdale's", self._bloomingdales, "is_bloomingdales_email"),
            ("anthropologie", "Anthropologie", self._anthropologie, "is_anthropologie_email"),
            ("nike", "Nike", self._nike, "is_nike_email"),
            ("carbon38", "Carbon38", self._carbon38, "is_carbon38_email"),
            ("gazelle", "Gazelle Sports", self._gazelle, "is_gazelle_email"),
            ("netaporter", "NET-A-PORTER", self._netaporter, "is_netaporter_email"),
            ("fit2run", "Fit2Run", self._fit2run, "is_fit2run_email"),
            ("sns", "SNS", self._sns, "is_sns_email"),
            ("adidas", "Adidas", self._adidas, "is_adidas_email"),
            ("concepts", "CNCPTS", self._concepts, "is_concepts_email"),
            ("sneaker", "Sneaker Politics", self._sneaker, "is_sneaker_email"),
            ("orleans", "Orleans Shoe Co", self._orleans, "is_orleans_email"),
        ]

        for retailer_id, display_name, parser, is_from_attr in confirmation_checks:
            is_from = getattr(parser, is_from_attr, None)
            if callable(is_from) and is_from(email_data):
                if parser.is_order_confirmation_email(email_data):
                    return ClassificationResult(
                        retailer_id=retailer_id,
                        email_type=EmailType.CONFIRMATION,
                        display_name=display_name,
                    )

        return None
