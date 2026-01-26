
import unittest
from datetime import date
from expense_report.models import Transaction, CategoryEnum, CATEGORIES_DATA
from expense_report.categorizers import KeywordCategorizer

class TestRuleCategorizer(unittest.TestCase):
    def test_amount_based_rules(self):
        # Initialize categorizer
        # Note: This relies on the actual categories.json content being loaded into CATEGORIES_DATA
        categorizer = KeywordCategorizer()

        # Test Case 1: Car Insurance (Security National, max_amount=200 in json for 'car', but wait...
        # In my edit:
        # car: keywords=['security national'], max_amount=200
        # house: keywords=['security national'], min_amount=200
        
        # Transaction 1: $114.97 (Small) -> Now maps to HOUSE (max_amount=200)
        t1 = Transaction(date=date.today(), description="SECURITY NATIONAL INSU  MONTREAL", amount=114.97)
        cat_t1 = categorizer.categorize(t1)
        self.assertEqual(cat_t1.category, CategoryEnum.HOUSE, f"Expected HOUSE for amount {t1.amount}, got {cat_t1.category}")

        # Transaction 2: $395.17 (Large) -> Now maps to CAR (min_amount=200)
        t2 = Transaction(date=date.today(), description="SECURITY NATIONAL INSU  MONTREAL", amount=395.17)
        cat_t2 = categorizer.categorize(t2)
        self.assertEqual(cat_t2.category, CategoryEnum.CAR, f"Expected CAR for amount {t2.amount}, got {cat_t2.category}")

        # Transaction 3: Ambiguous amount? Not handled in rules, should fall through or match one if ranges overlap (they don't overlap here: max 200 vs min 200). 
        # But wait, what if amount is exactly 200?
        # car: max_amount 200. Logic: if amount > 200 continue. So 200 is included.
        # house: min_amount 200. Logic: if amount < 200 continue. So 200 is included.
        # First rule encountered wins. Order depends on CATEGORIES_DATA order.
        
    def test_legacy_keyword(self):
        categorizer = KeywordCategorizer()
        
        # Test Case: Simple keyword (e.g. "amazon")
        t3 = Transaction(date=date.today(), description="AMAZON.CA*123", amount=50.0)
        cat_t3 = categorizer.categorize(t3)
        self.assertEqual(cat_t3.category, CategoryEnum.AMAZON)

if __name__ == '__main__':
    unittest.main()
