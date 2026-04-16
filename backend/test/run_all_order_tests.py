"""
Comprehensive test runner for all order confirmation email parsers.
Tests each parser against local email files with correct sender/subject metadata.
"""

import sys
from pathlib import Path

# Add parent directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.models.email import EmailData


def run_order_confirmation_tests():
    feed_dir = backend_dir / "feed" / "order-confirmation-emails"

    # (retailer, parser_class, module, files, sender, subject)
    test_configs = [
        ("footlocker", "FootlockerEmailParser", "footlocker_parser",
         ["footlocker.txt", "footlocker1.txt"],
         "accountservices@em.footlocker.com", "Thank you for your order"),
        ("champs", "ChampsEmailParser", "champs_parser",
         ["champs.txt"],
         "accountservices@em.champssports.com", "Thank you for your order"),
        ("dicks", "DicksEmailParser", "dicks_parser",
         ["dicks.txt", "dicks1.txt"],
         "noreply@order.dickssportinggoods.com", "Order Confirmation"),
        ("hibbett", "HibbettEmailParser", "hibbett_parser",
         ["hibbett.txt", "hibbett1.txt", "hibbett2.txt"],
         "hibbett@email.hibbett.com", "Order Confirmation"),
        ("shoepalace", "ShoepalaceEmailParser", "shoepalace_parser",
         ["shoepalace.txt", "shoepalace1.txt", "shoepalace2.txt"],
         "customerservice@shoepalace.com", "Order #SP834718 confirmed"),
        ("snipes", "SnipesEmailParser", "snipes_parser",
         ["snipes.txt", "snipes1.txt"],
         "noreply@snipesusa.com", "Order Confirmation"),
        ("finishline", "FinishLineEmailParser", "finishline_parser",
         ["finishline.txt", "finishline1.txt"],
         "finishline@notifications.finishline.com", "Your Order is Official!"),
        ("shopsimon", "ShopSimonEmailParser", "shopsimon_parser",
         ["shopsimon.txt"],
         "support@shopsimon.com", "Order Confirmation"),
        ("urban", "UrbanOutfittersEmailParser", "urban_parser",
         ["urban.txt", "urban1.txt", "urban2.txt", "urban3.txt", "urban4.txt", "urban5.txt", "urban6.txt"],
         "urbanoutfitters@st.urbanoutfitters.com", "Thank you for your Urban Outfitters order!"),
        ("bloomingdales", "BloomingdalesEmailParser", "bloomingdales_parser",
         ["bloomingdale.txt"],
         "no-reply@bloomingdales.com", "Order Confirmation"),
        ("carbon38", "Carbon38EmailParser", "carbon38_parser",
         ["carbon38.txt"],
         "noreply@carbon38.com", "Order Confirmation"),
        ("gazelle", "GazelleEmailParser", "gazelle_parser",
         ["gazelle.txt"],
         "noreply@gazellesports.com", "Order Confirmation"),
        ("netaporter", "NetAPorterEmailParser", "netaporter_parser",
         ["netaporter.txt"],
         "customercare@net-a-porter.com", "Order Confirmation"),
        ("sns", "SNSEmailParser", "sns_parser",
         ["sns.txt", "sns1.txt"],
         "noreply@sneakersnstuff.com", "Order Confirmation"),
        ("adidas", "AdidasEmailParser", "adidas_parser",
         ["adidas.txt"],
         "adidas@notifications.adidas.com", "Order Confirmation"),
        ("concepts", "ConceptsEmailParser", "concepts_parser",
         ["concepts.txt"],
         "noreply@cncpts.com", "Order Confirmation"),
        ("sneaker", "SneakerPoliticsEmailParser", "sneaker_parser",
         ["sneaker.txt"],
         "noreply@sneakerpolitics.com", "Order Confirmation"),
        ("orleans", "OrleansEmailParser", "orleans_parser",
         ["orleans.txt"],
         "store+15639833@t.shopifyemail.com", "order confirmation"),
        ("nike", "NikeEmailParser", "nike_parser",
         ["nike.txt"],
         "nike@notifications.nike.com", "Order Confirmation"),
        ("asos", "ASOSEmailParser", "asos_parser",
         ["asos.txt", "asos1.txt"],
         "noreply@asos.com", "Order Confirmation"),
        ("anthropologie", "AnthropologieEmailParser", "anthropologie_parser",
         ["anthropologie.txt"],
         "anthropologie@st.anthropologie.com", "Order Confirmation"),
        ("dtlr", "DTLREmailParser", "dtlr_parser",
         ["dtlr.txt", "dtlr1.txt", "dtlr2.txt", "dtlr3.txt", "dtlr4.txt", "dtlr5.txt"],
         "custserv@dtlr.com", "Order #5307431 confirmed"),
        ("endclothing", "ENDClothingEmailParser", "endclothing_parser",
         ["endclothing.txt"],
         "noreply@endclothing.com", "Order Confirmation"),
        ("fit2run", "Fit2RunEmailParser", "fit2run_parser",
         ["fit2run.txt", "fit2run1.txt"],
         "noreply@fit2run.com", "Order Confirmation"),
        ("jdsports", "JDSportsEmailParser", "jdsports_parser",
         ["jdsports.txt"],
         "noreply@jdsports.com", "Order Confirmation"),
        ("on", "OnEmailParser", "on_parser",
         ["on.txt"],
         "noreply@on-running.com", "Order Confirmation"),
        ("revolve", "RevolveEmailParser", "revolve_parser",
         ["revolve.txt"],
         "revolve@mt.revolve.com", "Your order #341221096 has been processed"),
        ("shopwss", "ShopWSSEmailParser", "shopwss_parser",
         ["shopwss.txt"],
         "noreply@shopwss.com", "Order Confirmation"),
        ("als", "AlsEmailParser", "als_parser",
         ["als.txt", "als1.txt", "als2.txt"],
         "cs@als.com", "We received your order #10075572"),
        ("sierra", "SierraEmailParser", "sierra_parser",
         ["sierra.txt"],
         "sierra@tr.tjx.com", "Thanks for your Sierra order E43759932"),
        ("nordstrom", "NordstromEmailParser", "nordstrom_parser",
         ["nordstrom.txt", "nordstrom1.txt", "nordstrom2.txt"],
         "nordstrom@eml.nordstrom.com", "Your Nordstrom order #1020786219"),
        ("sportsbasement", "SportsBasementEmailParser", "sportsbasement_parser",
         ["sportsbasement.txt"],
         "friends@sportsbasement.com", "Your order #1409419 is confirmed"),
        ("macys", "MacysEmailParser", "macys_parser",
         ["macys.txt", "macys1.txt"],
         "CustomerService@oes.macys.com", "Thank you for your order!"),
        ("fwrd", "FwrdEmailParser", "fwrd_parser",
         ["fwrd.txt"],
         "fwrd@mt.fwrd.com", "FWRD - Order Confirmation #354215641"),
        ("academy", "AcademyEmailParser", "academy_parser",
         ["academy.txt"],
         "email@e.academy.com", "Thanks for shopping with us!"),
        ("scheels", "SceelsEmailParser", "scheels_parser",
         ["scheels.txt"],
         "info@e.scheels.com", "Your SCHEELS Order Confirmation #4113357485"),
    ]

    passed = 0
    failed = 0
    skipped = 0
    errors = []

    print("=" * 80)
    print("ORDER CONFIRMATION PARSER TESTS (with correct metadata)")
    print("=" * 80)

    for retailer, parser_class, module_name, files, sender, subject in test_configs:
        try:
            module = __import__(f"app.services.{module_name}", fromlist=[parser_class])
            ParserClass = getattr(module, parser_class)
            parser = ParserClass()
        except Exception as e:
            print(f"  ERROR importing {module_name}.{parser_class}: {e}")
            errors.append(f"{retailer}: Import error - {e}")
            failed += len(files)
            continue

        for fname in files:
            fpath = feed_dir / fname
            if not fpath.exists():
                print(f"  SKIP  {retailer}/{fname} - file not found")
                skipped += 1
                continue

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    html = f.read()

                email_data = EmailData(
                    message_id="test-123",
                    thread_id="test-thread-123",
                    subject=subject,
                    sender=sender,
                    html_content=html,
                )

                result = parser.parse_email(email_data)

                if result and result.order_number and len(result.items) > 0:
                    all_valid = True
                    item_issues = []
                    for i, item in enumerate(result.items):
                        if not item.unique_id:
                            all_valid = False
                            item_issues.append(f"item {i+1} missing unique_id")

                    if all_valid:
                        addr = getattr(result, "shipping_address", None)
                        addr_str = f", addr={addr[:30]}..." if addr else ""
                        print(f"  PASS  {retailer}/{fname} -> #{result.order_number}, {len(result.items)} items{addr_str}")
                        passed += 1
                    else:
                        print(f"  FAIL  {retailer}/{fname} -> {'; '.join(item_issues)}")
                        errors.append(f"{retailer}/{fname}: {'; '.join(item_issues)}")
                        failed += 1
                elif result and result.order_number:
                    print(f"  FAIL  {retailer}/{fname} -> No items (order #{result.order_number})")
                    errors.append(f"{retailer}/{fname}: No items extracted")
                    failed += 1
                elif result:
                    items_count = len(result.items) if hasattr(result, "items") else 0
                    print(f"  FAIL  {retailer}/{fname} -> No order number, {items_count} items")
                    errors.append(f"{retailer}/{fname}: No order number")
                    failed += 1
                else:
                    print(f"  FAIL  {retailer}/{fname} -> Parser returned None")
                    errors.append(f"{retailer}/{fname}: Parser returned None")
                    failed += 1
            except Exception as e:
                import traceback
                print(f"  ERROR {retailer}/{fname}: {e}")
                traceback.print_exc()
                errors.append(f"{retailer}/{fname}: Exception - {e}")
                failed += 1

    print()
    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped (total: {passed+failed+skipped})")
    print("=" * 80)
    if errors:
        print()
        print("FAILURES:")
        for e in errors:
            print(f"  - {e}")

    return failed == 0


if __name__ == "__main__":
    success = run_order_confirmation_tests()
    sys.exit(0 if success else 1)
