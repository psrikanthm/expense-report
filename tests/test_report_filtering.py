
import unittest
from datetime import date
from expense_report.models import CategorizedTransaction, CategoryEnum, CategorizerEnum
from expense_report.reports import ReportGenerator
import pandas as pd
import os
import shutil

class TestReportFiltering(unittest.TestCase):
    def setUp(self):
        self.output_dir = "tests/test_output"
        os.makedirs(self.output_dir, exist_ok=True)
        self.generator = ReportGenerator(output_dir=self.output_dir)

    def tearDown(self):
        shutil.rmtree(self.output_dir)

    def test_exclude_categories(self):
        # Create transactions
        t1 = CategorizedTransaction(
            date=date(2025, 1, 15),
            description="Grocery Store",
            amount=50.0,
            category=CategoryEnum.GROCERIES,
            categorizer=CategorizerEnum.KEYWORD
        )
        t2 = CategorizedTransaction(
            date=date(2025, 1, 16),
            description="Utility Bill",
            amount=100.0,
            category=CategoryEnum.UTILITY,
            categorizer=CategorizerEnum.KEYWORD
        )
        
        # We need to patch the EXCLUDED_CATEGORIES in reports module
        from unittest.mock import patch
        import expense_report.reports
        
        with patch.object(expense_report.reports, 'EXCLUDED_CATEGORIES', [CategoryEnum.UTILITY]):
            # Subclass to inspect DF
            class TestableGenerator(ReportGenerator):
                 def generate_report(self, transactions, month):
                    df = pd.DataFrame([t.to_dict() for t in transactions])
                    df['date'] = pd.to_datetime(df['date'])
                    
                    if expense_report.reports.EXCLUDED_CATEGORIES:
                        exclude_values = {c.value.lower() for c in expense_report.reports.EXCLUDED_CATEGORIES}
                        df = df[~df['category'].apply(lambda x: str(x).lower() in exclude_values)]
                    return df

            gen = TestableGenerator(self.output_dir)
            df_filtered = gen.generate_report([t1, t2], "2025-01")
            
            # Expect only Groceries
            self.assertEqual(len(df_filtered), 1)
            self.assertEqual(df_filtered.iloc[0]['category'], 'groceries')

if __name__ == '__main__':
    unittest.main()
