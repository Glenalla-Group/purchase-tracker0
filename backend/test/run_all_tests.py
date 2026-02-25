"""
Run all order confirmation email parser tests.

Usage:
    python -m test.run_all_tests
"""

import sys
from pathlib import Path

def run_all_tests():
    """Run all retailer order confirmation email parser tests"""
    
    test_dir = Path(__file__).parent
    feed_dir = test_dir.parent / "feed" / "order-confirmation-emails"
    
    # Map of test modules to their corresponding email files
    test_files = {
        "test_footlocker": ["footlocker.txt", "footlocker1.txt"],
        "test_champs": ["champs.txt"],
        "test_dicks": ["dicks.txt"],
        "test_hibbett": ["hibbett.txt"],
        "test_shoepalace": ["shoepalace.txt"],
        "test_snipes": ["snipes.txt"],
        "test_finishline": ["finishline.txt"],
        "test_shopsimon": ["shopsimon.txt"],
        "test_urban": ["urban.txt"],
        "test_bloomingdales": ["bloomingdale.txt"],
        "test_carbon38": ["carbon38.txt"],
        "test_gazelle": ["gazelle.txt"],
        "test_netaporter": ["netaporter.txt"],
        "test_sns": ["sns.txt", "sns1.txt"],
        "test_adidas": ["adidas.txt"],
        "test_concepts": ["concepts.txt"],
        "test_sneaker": ["sneaker.txt"],
        "test_orleans": ["orleans.txt"],
    }
    
    results = {}
    
    print("=" * 80)
    print("Running All Order Confirmation Email Parser Tests")
    print("=" * 80)
    print()
    
    for test_module, email_files in test_files.items():
        print(f"\n{'=' * 80}")
        print(f"Testing {test_module}")
        print(f"{'=' * 80}")
        
        module_results = []
        
        for email_file in email_files:
            email_path = feed_dir / email_file
            if not email_path.exists():
                print(f"⚠️  Skipping {email_file} - file not found")
                module_results.append({
                    "file": email_file,
                    "status": "skipped",
                    "reason": "file not found"
                })
                continue
            
            print(f"\n--- Testing with {email_file} ---")
            
            # Import and run the test
            try:
                module = __import__(f"test.{test_module}", fromlist=[test_module])
                test_func = getattr(module, test_module.replace("test_", "test_"))
                
                # Run the test
                result = test_func(email_file)
                
                if result:
                    module_results.append({
                        "file": email_file,
                        "status": "passed",
                        "order_number": getattr(result, "order_number", "N/A"),
                        "items_count": len(getattr(result, "items", []))
                    })
                    print(f"✅ {email_file}: PASSED")
                else:
                    module_results.append({
                        "file": email_file,
                        "status": "failed",
                        "reason": "parser returned None"
                    })
                    print(f"❌ {email_file}: FAILED")
                    
            except Exception as e:
                module_results.append({
                    "file": email_file,
                    "status": "error",
                    "error": str(e)
                })
                print(f"❌ {email_file}: ERROR - {e}")
        
        results[test_module] = module_results
    
    # Print summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    skipped_tests = 0
    
    for test_module, module_results in results.items():
        for result in module_results:
            total_tests += 1
            if result["status"] == "passed":
                passed_tests += 1
            elif result["status"] == "skipped":
                skipped_tests += 1
            else:
                failed_tests += 1
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {failed_tests}")
    print(f"⚠️  Skipped: {skipped_tests}")
    
    if failed_tests > 0:
        print("\nFailed Tests:")
        for test_module, module_results in results.items():
            for result in module_results:
                if result["status"] in ["failed", "error"]:
                    retailer = result.get('retailer', test_module)
                    print(f"  - {retailer}: {result.get('reason', result.get('error', 'Unknown error'))}")
    
    return failed_tests == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
