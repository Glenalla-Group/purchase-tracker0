"""
Comprehensive test runner for all shipping email parsers.
Tests each parser against local email files with correct sender/subject metadata.
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.models.email import EmailData


def run_shipping_tests():
    feed_dir = backend_dir / "feed" / "order-shipping-emails"

    # (retailer, parser_class, module, files, sender, subject, parse_method)
    test_configs = [
        ("footlocker", "FootlockerEmailParser", "footlocker_parser",
         ["footlocker.txt"],
         "accountservices@em.footlocker.com", "Your order has shipped!",
         "parse_shipping_email"),
        ("champs", "ChampsEmailParser", "champs_parser",
         ["champs-shipping-order.txt"],
         "accountservices@em.champssports.com", "Your order has shipped!",
         "parse_shipping_email"),
        ("finishline", "FinishLineEmailParser", "finishline_parser",
         ["finishline1.txt", "finishline2.txt"],
         "finishline@notifications.finishline.com", "Your order has shipped!",
         "parse_shipping_email"),
        ("hibbett", "HibbettEmailParser", "hibbett_parser",
         ["hibbett-shipping-order.txt", "hibbett1.txt", "hibbett2.txt"],
         "hibbett@email.hibbett.com", "Your order has shipped!",
         "parse_shipping_email"),
        ("shoepalace", "ShoepalaceEmailParser", "shoepalace_parser",
         ["shoepalace.txt"],
         "noreply@shoepalace.com", "Your order has shipped!",
         "parse_shipping_email"),
        ("snipes", "SnipesEmailParser", "snipes_parser",
         ["snipes.txt"],
         "info@t.snipesusa.com", "Get hyped! Your order has shipped",
         "parse_shipping_email"),
        ("urban", "UrbanOutfittersEmailParser", "urban_parser",
         ["urban.txt", "urban1.txt", "urban2.txt", "urban3.txt", "urban4.txt", "urban5.txt", "urban6.txt"],
         "urbanoutfitters@st.urbanoutfitters.com", "Your order is on its way!",
         "parse_shipping_email"),
        ("revolve-full", "RevolveEmailParser", "revolve_parser",
         ["revolve-full.txt"],
         "revolve@mt.revolve.com", "Your order #341221096 has been shipped",
         "parse_shipping_email"),
        ("revolve-partial", "RevolveEmailParser", "revolve_parser",
         ["revolve-partial.txt"],
         "revolve@mt.revolve.com", "Part of order #341221096 has shipped",
         "parse_shipping_email"),
        ("shopwss", "ShopWSSEmailParser", "shopwss_parser",
         ["shopwss.txt"],
         "help@shopwss.com", "Your order has shipped",
         "parse_shipping_email"),
        ("endclothing", "ENDClothingEmailParser", "endclothing_parser",
         ["endclothing.txt"],
         "noreply@endclothing.com", "Your order has shipped",
         "parse_shipping_email"),
        ("asos", "ASOSEmailParser", "asos_parser",
         ["asos.txt"],
         "noreply@asos.com", "Your order has shipped",
         "parse_shipping_email"),
        ("dtlr", "DTLREmailParser", "dtlr_parser",
         ["dtlr.txt", "dtlr1.txt", "dtlr2.txt", "dtlr3.txt", "dtlr4.txt", "dtlr5.txt",
          "dtlr6.txt", "dtlr7.txt", "dtlr8.txt", "dtlr9.txt", "dtlr10.txt"],
         "custserv@dtlr.com", "Order 5307431 Has Been Fulfilled",
         "parse_shipping_email"),
        ("als", "AlsEmailParser", "als_parser",
         ["als.txt", "als1.txt", "als2.txt", "als4.txt"],
         "cs@als.com", "Your order has shipped!",
         "parse_shipping_email"),
        ("als-partial", "AlsEmailParser", "als_parser",
         ["als3.txt"],
         "cs@als.com", "Part of your order has shipped!",
         "parse_shipping_email"),
        ("nordstrom", "NordstromEmailParser", "nordstrom_parser",
         ["nordstrom.txt", "nordstrom1.txt", "nordstrom2.txt", "nordstrom3.txt", "nordstrom4.txt"],
         "nordstrom@eml.nordstrom.com", "Your items are on the way",
         "parse_shipping_email"),
        ("sportsbasement", "SportsBasementEmailParser", "sportsbasement_parser",
         ["sportsbasement.txt", "sportsbasement1.txt"],
         "store+7517203@t.shopifyemail.com", "Your order is on the way!",
         "parse_shipping_email"),
        ("macys", "MacysEmailParser", "macys_parser",
         ["macys.txt", "macys1.txt", "macys2.txt", "macys3.txt", "macys4.txt"],
         "CustomerService@oes.macys.com", "Part of your order has shipped, #4717809803",
         "parse_shipping_email"),
        ("sierra", "SierraEmailParser", "sierra_parser",
         ["sierra.txt"],
         "sierra@tr.tjx.com", "Your Sierra order E43759932 is on its way",
         "parse_shipping_email"),
        ("dicks", "DicksEmailParser", "dicks_parser",
         ["dicks.txt", "dicks1.txt", "dicks2.txt"],
         "notifications@delivery.dickssportinggoods.com", "Your order just shipped!",
         "parse_shipping_email"),
        ("fwrd", "FwrdEmailParser", "fwrd_parser",
         ["fwrd.txt"],
         "fwrd@mt.fwrd.com", "Your order #354215641 has shipped",
         "parse_shipping_email"),
        ("academy", "AcademyEmailParser", "academy_parser",
         ["academy1.txt", "academy2.txt"],
         "email@e.academy.com", "Your items are packed and ready to ship",
         "parse_shipping_email"),
        ("scheels", "SceelsEmailParser", "scheels_parser",
         ["scheels.txt"],
         "info@e.scheels.com", "Package Shipped from Order #4113357485",
         "parse_shipping_email"),
    ]

    passed = 0
    failed = 0
    skipped = 0
    errors = []

    print("=" * 80)
    print("SHIPPING EMAIL PARSER TESTS")
    print("=" * 80)

    for retailer, parser_class, module_name, files, sender, subject, method_name in test_configs:
        try:
            module = __import__(f"app.services.{module_name}", fromlist=[parser_class])
            ParserClass = getattr(module, parser_class)
            parser = ParserClass()
        except Exception as e:
            print(f"  ERROR importing {module_name}.{parser_class}: {e}")
            errors.append(f"{retailer}: Import error - {e}")
            failed += len(files)
            continue

        parse_method = getattr(parser, method_name, None)
        if not parse_method:
            print(f"  SKIP  {retailer} - no {method_name} method")
            skipped += len(files)
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
                    message_id="test-ship-123",
                    thread_id="test-thread-123",
                    subject=subject,
                    sender=sender,
                    html_content=html,
                )

                result = parse_method(email_data)

                if result and result.order_number and len(result.items) > 0:
                    tracking = getattr(result, "tracking_number", None)
                    tracking_str = f", tracking={tracking[:20]}..." if tracking else ""
                    print(f"  PASS  {retailer}/{fname} -> #{result.order_number}, {len(result.items)} items{tracking_str}")
                    passed += 1
                elif result and result.order_number:
                    print(f"  FAIL  {retailer}/{fname} -> No items (order #{result.order_number})")
                    errors.append(f"{retailer}/{fname}: No shipped items extracted")
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
    success = run_shipping_tests()
    sys.exit(0 if success else 1)
