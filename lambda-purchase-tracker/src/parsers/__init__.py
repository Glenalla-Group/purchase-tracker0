"""
Parser registry — maps retailer IDs to parser classes.
"""

from src.parsers.adidas_parser import AdidasEmailParser
from src.parsers.anthropologie_parser import AnthropologieEmailParser
from src.parsers.asos_parser import ASOSEmailParser
from src.parsers.bloomingdales_parser import BloomingdalesEmailParser
from src.parsers.carbon38_parser import Carbon38EmailParser
from src.parsers.champs_parser import ChampsEmailParser
from src.parsers.concepts_parser import ConceptsEmailParser
from src.parsers.dicks_parser import DicksEmailParser
from src.parsers.dtlr_parser import DTLREmailParser
from src.parsers.endclothing_parser import ENDClothingEmailParser
from src.parsers.finishline_parser import FinishLineEmailParser
from src.parsers.fit2run_parser import Fit2RunEmailParser
from src.parsers.footlocker_parser import FootlockerEmailParser
from src.parsers.gazelle_parser import GazelleEmailParser
from src.parsers.hibbett_parser import HibbettEmailParser
from src.parsers.jdsports_parser import JDSportsEmailParser
from src.parsers.netaporter_parser import NetAPorterEmailParser
from src.parsers.nike_parser import NikeEmailParser
from src.parsers.on_parser import OnEmailParser
from src.parsers.orleans_parser import OrleansEmailParser
from src.parsers.revolve_parser import RevolveEmailParser
from src.parsers.shoepalace_parser import ShoepalaceEmailParser
from src.parsers.shopsimon_parser import ShopSimonEmailParser
from src.parsers.shopwss_parser import ShopWSSEmailParser
from src.parsers.sneaker_parser import SneakerPoliticsEmailParser
from src.parsers.snipes_parser import SnipesEmailParser
from src.parsers.sns_parser import SNSEmailParser
from src.parsers.urban_parser import UrbanOutfittersEmailParser
from src.parsers.als_parser import AlsEmailParser
from src.parsers.sierra_parser import SierraEmailParser
from src.parsers.sportsbasement_parser import SportsBasementEmailParser
from src.parsers.macys_parser import MacysEmailParser
from src.parsers.nordstrom_parser import NordstromEmailParser
from src.parsers.fwrd_parser import FwrdEmailParser
from src.parsers.academy_parser import AcademyEmailParser
from src.parsers.scheels_parser import SceelsEmailParser

PARSER_REGISTRY = {
    "footlocker": FootlockerEmailParser,
    "kidsfootlocker": FootlockerEmailParser,
    "champs": ChampsEmailParser,
    "dicks": DicksEmailParser,
    "hibbett": HibbettEmailParser,
    "dtlr": DTLREmailParser,
    "shoepalace": ShoepalaceEmailParser,
    "snipes": SnipesEmailParser,
    "finishline": FinishLineEmailParser,
    "jdsports": JDSportsEmailParser,
    "revolve": RevolveEmailParser,
    "asos": ASOSEmailParser,
    "urban": UrbanOutfittersEmailParser,
    "urbanoutfitters": UrbanOutfittersEmailParser,  # alias: classifier uses this retailer_id for confirmations
    "bloomingdales": BloomingdalesEmailParser,
    "anthropologie": AnthropologieEmailParser,
    "nike": NikeEmailParser,
    "carbon38": Carbon38EmailParser,
    "gazelle": GazelleEmailParser,
    "netaporter": NetAPorterEmailParser,
    "fit2run": Fit2RunEmailParser,
    "sns": SNSEmailParser,
    "adidas": AdidasEmailParser,
    "concepts": ConceptsEmailParser,
    "sneakerpolitics": SneakerPoliticsEmailParser,
    "on": OnEmailParser,
    "shopsimon": ShopSimonEmailParser,
    "endclothing": ENDClothingEmailParser,
    "shopwss": ShopWSSEmailParser,
    "orleans": OrleansEmailParser,
    "als": AlsEmailParser,
    "sierra": SierraEmailParser,
    "sportsbasement": SportsBasementEmailParser,
    "macys": MacysEmailParser,
    "nordstrom": NordstromEmailParser,
    "fwrd": FwrdEmailParser,
    "academy": AcademyEmailParser,
    "scheels": SceelsEmailParser,
}


def get_all_parsers():
    """Instantiate all parsers."""
    return {key: cls() for key, cls in PARSER_REGISTRY.items()}


def get_known_sender_addresses():
    """Collect all known retailer sender email addresses for filtering."""
    addresses = set()
    parsers = get_all_parsers()
    for parser in parsers.values():
        # Get the production order sender email
        if hasattr(parser, "order_from_email"):
            addr = parser.order_from_email
            if addr:
                addresses.add(addr.lower())
        # Get shipping/cancellation sender emails if different
        if hasattr(parser, "update_from_email"):
            addr = parser.update_from_email
            if addr:
                addresses.add(addr.lower())
        # Some parsers have separate sender constants
        for attr_name in dir(parser):
            if "FROM_EMAIL" in attr_name and not attr_name.startswith("DEV_"):
                val = getattr(parser, attr_name, None)
                if isinstance(val, str) and "@" in val:
                    addresses.add(val.lower())
    return addresses
