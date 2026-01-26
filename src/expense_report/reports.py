import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
from pathlib import Path
from typing import List, Optional
import tempfile
import os
import json
from .models import CategorizedTransaction, CategoryEnum

# Categories to exclude from the report
EXCLUDED_CATEGORIES = [
    CategoryEnum.TRANSFER,
]

class PDFReport(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 15)
        self.cell(0, 10, 'Monthly Spending Report', border=False, align='C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')

class ReportGenerator:
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(self, transactions: List[CategorizedTransaction], month: str):
        """
        Generates a PDF report for the given month.
        month: str in 'YYYY-MM' format.
        """
        # Convert transactions to DataFrame for easier manipulation
        df = pd.DataFrame([t.to_dict() for t in transactions])
        df['date'] = pd.to_datetime(df['date'])
        
        # De-duplicate transactions based on (date, description, amount)
        original_count = len(df)
        df = df.drop_duplicates(subset=['date', 'description', 'amount'], keep='first')
        deduped_count = len(df)
        if original_count != deduped_count:
            print(f"Removed {original_count - deduped_count} duplicate transactions")
        
        # Filter out excluded categories defined in EXCLUDED_CATEGORIES
        if EXCLUDED_CATEGORIES:
            exclude_values = {c.value.lower() for c in EXCLUDED_CATEGORIES}
            df = df[~df['category'].apply(lambda x: str(x).lower() in exclude_values)]
        
        # Filter for the target month
        # Assuming input month is 'YYYY-MM'
        target_date = pd.to_datetime(f"{month}-01")
        current_month_df = df[
            (df['date'].dt.year == target_date.year) & 
            (df['date'].dt.month == target_date.month)
        ]
        
        if current_month_df.empty:
            print(f"No transactions found for {month}")
            return

        report_path = self.output_dir / f"report_{month}.pdf"
        
        pdf = PDFReport()
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # 1. Spend Summary
        self._add_spend_summary(pdf, current_month_df, month)
        
        # 2. Spend by Category (Pie Chart)
        self._add_category_pie_chart(pdf, current_month_df)
        
        # 3. Last 12 Months Spend (Bar Chart)
        self._add_monthly_trend_chart(pdf, df, target_date)
        
        # 4. Transaction Details
        self._add_transaction_table(pdf, current_month_df)
        
        pdf.output(str(report_path))
        print(f"Report generated: {report_path}")

    def _add_spend_summary(self, pdf: PDFReport, df: pd.DataFrame, month: str):
        total_spend = df[df['amount'] > 0]['amount'].sum()

        pdf.set_font('helvetica', 'B', 12)
        pdf.cell(0, 10, f"Spend Summary for {month}", ln=True)
        
        pdf.set_font('helvetica', '', 10)
        pdf.cell(0, 8, f"Total Spend: ${total_spend:.2f}", ln=True)
        pdf.ln(10)

    def _add_category_pie_chart(self, pdf: PDFReport, df: pd.DataFrame):
        pdf.set_font('helvetica', 'B', 12)
        pdf.cell(0, 10, "Spend by Category", ln=True)

        # Aggregate by category
        cat_spend = df[df['amount'] > 0].groupby('category')['amount'].sum().reset_index()
        cat_spend['percentage'] = cat_spend['amount'] / cat_spend['amount'].sum() * 100
        
        # Create Pie Chart
        fig = px.pie(cat_spend, values='amount', names='category', 
                     title='Spend by Category',
                     hover_data=['percentage'], 
                     labels={'amount':'Amount'})
        fig.update_traces(textposition='inside', texttemplate='%{label}<br>$%{value:.2f}<br>%{percent}')
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            fig.write_image(tmp.name, scale=4)
            pdf.image(tmp.name, w=180)
            os.unlink(tmp.name)
        
        pdf.ln(10)

    def _add_monthly_trend_chart(self, pdf: PDFReport, full_df: pd.DataFrame, target_date: pd.Timestamp):
        pdf.add_page()
        pdf.set_font('helvetica', 'B', 12)
        pdf.cell(0, 10, "Last 12 Months Spend Trend", ln=True)

        # Filter last 12 months
        end_date = target_date + pd.offsets.MonthEnd(0)
        start_date = end_date - pd.DateOffset(months=11)
        start_date = start_date.replace(day=1)
        
        trend_df = full_df[
            (full_df['date'] >= start_date) & 
            (full_df['date'] <= end_date) &
            (full_df['amount'] > 0) # Only consider positive spend
        ].copy()
        
        # Group by month and category
        # Using string format for month to make plotting easier
        trend_df['month_str'] = trend_df['date'].dt.strftime('%Y-%m')
        
        # Calculate total spend per category for sorting
        category_totals = trend_df.groupby('category')['amount'].sum().sort_values(ascending=False)
        sorted_categories = category_totals.index.tolist()
        
        monthly_cat_spend = trend_df.groupby(['month_str', 'category'])['amount'].sum().reset_index()
        
        # Format the amount as dollar values for bar labels
        monthly_cat_spend['amount_label'] = monthly_cat_spend['amount'].apply(lambda x: f'${x:,.0f}')
        
        # Sort the dataframe so that the legend order matches the stack order (roughly)
        # Plotly Express stacks from bottom up based on the order in category_orders if provided.
        # We want High Spend -> Bottom. So first in list = Bottom.
        
        fig = px.bar(monthly_cat_spend, x='month_str', y='amount', color='category', 
                     text='amount_label',
                     title='Monthly Spend by Category (Last 12 Months)',
                     labels={'amount': 'Spend ($)', 'month_str': 'Month'},
                     category_orders={'category': sorted_categories})
        
        # Position text inside bars and style it
        fig.update_traces(textposition='inside', textfont_size=8)
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            fig.write_image(tmp.name, scale=4)
            pdf.image(tmp.name, w=190)
            os.unlink(tmp.name)
            
        pdf.ln(10)

        # Add Category Descriptions
        pdf.set_font('helvetica', 'B', 10)
        pdf.cell(0, 8, "Category Descriptions:", ln=True)
        pdf.set_font('helvetica', '', 9)
        
        try:
            categories_path = Path(__file__).parent / "resources/categories.json"
            with open(categories_path, 'r') as f:
                categories_data = json.load(f)
            
            for cat in categories_data:
                name = cat.get('name', '').title()
                desc = cat.get('description', 'No description available.')
                # Use multi_cell for wrapping text
                pdf.set_font('helvetica', 'B', 9)
                pdf.write(5, f"{name}: ")
                pdf.set_font('helvetica', '', 9)
                pdf.write(5, f"{desc}\n")
                pdf.ln(2)
                
        except Exception as e:
            print(f"Error loading category descriptions: {e}")
            pdf.cell(0, 5, "Could not load category descriptions.", ln=True)

        pdf.ln(10)

    def _add_transaction_table(self, pdf: PDFReport, df: pd.DataFrame):
        pdf.add_page()
        pdf.set_font('helvetica', 'B', 12)
        pdf.cell(0, 10, "Transaction Details", ln=True)
        pdf.ln(5)
        
        # Table Header
        pdf.set_font('helvetica', 'B', 8)
        col_widths = [25, 100, 25, 30] # Date, Description, Amount, Category
        headers = ['Date', 'Description', 'Amount', 'Category']
        
        for width, header in zip(col_widths, headers):
            pdf.cell(width, 7, header, border=1)
        pdf.ln()
        
        # Table Rows
        pdf.set_font('helvetica', '', 7)
        
        # Sort by category then date
        sorted_df = df.sort_values(by=['category', 'date'])
        
        for _, row in sorted_df.iterrows():
            if row['amount'] < 0:
                continue
            date_str = row['date'].strftime('%Y-%m-%d')
            desc = str(row['description'])[:60] # Truncate long descriptions
            amount_str = f"${row['amount']:.2f}"
            category = str(row['category'])
            
            pdf.cell(col_widths[0], 6, date_str, border=1)
            pdf.cell(col_widths[1], 6, desc, border=1)
            pdf.cell(col_widths[2], 6, amount_str, border=1, align='R')
            pdf.cell(col_widths[3], 6, category, border=1)
            pdf.ln()

