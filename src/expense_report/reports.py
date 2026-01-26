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

    def generate_report(self, 
                        current_aggregates: pd.DataFrame, 
                        historical_aggregates: pd.DataFrame, 
                        transaction_details: pd.DataFrame, 
                        month: str):
        """
        Generates a PDF report for the given month using pre-aggregated data.
        
        current_aggregates: DataFrame with columns ['category', 'amount'] (and potentially date/month related cols)
        historical_aggregates: DataFrame with columns ['category', 'amount', 'date'] (containing approx 12 months)
        transaction_details: DataFrame containing filtered line-item transactions for the current month.
        month: str in 'YYYY-MM' format.
        """
        
        if current_aggregates.empty:
            print(f"No aggregated data found for {month}")
            # We might still want to generate an empty report or return
            # But let's check details too
        
        if transaction_details.empty:
            print(f"No transactions found for {month}")
            return

        report_path = self.output_dir / f"report_{month}.pdf"
        
        pdf = PDFReport()
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # 1. Spend Summary
        self._add_spend_summary(pdf, current_aggregates, month)
        
        # 2. Spend by Category (Pie Chart)
        self._add_category_pie_chart(pdf, current_aggregates)
        
        # 3. Last 12 Months Spend (Bar Chart)
        # Verify historical_aggregates has date or month_str
        if 'date' in historical_aggregates.columns:
            # Ensure it works for plotting
             historical_aggregates['date'] = pd.to_datetime(historical_aggregates['date'])
        
        target_date = pd.to_datetime(f"{month}-01")
        self._add_monthly_trend_chart(pdf, historical_aggregates, target_date)
        
        # 4. Transaction Details
        self._add_transaction_table(pdf, transaction_details)
        
        pdf.output(str(report_path))
        print(f"Report generated: {report_path}")
        return report_path

    def _add_spend_summary(self, pdf: PDFReport, aggregates: pd.DataFrame, month: str):
        # aggregates has 'amount'. Sum positive amounts? 
        # Usually aggregates are already sums. If they are net sums, we just sum them.
        # If we want total "spend" we might want to ignore negative aggregates (refunds/income)?
        # For simplicity, assuming aggregates represent net spend per category.
        
        total_spend = aggregates['amount'].sum()
        
        pdf.set_font('helvetica', 'B', 12)
        pdf.cell(0, 10, f"Spend Summary for {month}", ln=True)
        
        pdf.set_font('helvetica', '', 10)
        pdf.cell(0, 8, f"Total Spend: ${total_spend:.2f}", ln=True)
        pdf.ln(10)

    def _add_category_pie_chart(self, pdf: PDFReport, aggregates: pd.DataFrame):
        pdf.set_font('helvetica', 'B', 12)
        pdf.cell(0, 10, "Spend by Category", ln=True)

        # Filter out zero or negative speds for Pie Chart to look nice
        # usage of copy() to avoid SettingWithCopyWarning if it's a view
        cat_spend = aggregates[aggregates['amount'] > 0].copy()
        
        if cat_spend.empty:
             pdf.cell(0, 10, "No positive spend to display.", ln=True)
             pass
        else:
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

    def _add_monthly_trend_chart(self, pdf: PDFReport, hist_df: pd.DataFrame, target_date: pd.Timestamp):
        pdf.add_page()
        pdf.set_font('helvetica', 'B', 12)
        pdf.cell(0, 10, "Last 12 Months Spend Trend", ln=True)

        if hist_df.empty:
             pdf.cell(0, 10, "No historical data available.", ln=True)
             return

        # hist_df should have 'date', 'category', 'amount'
        # Filter (already done in jobs.py mostly, but good to ensure range)
        end_date = target_date + pd.offsets.MonthEnd(0)
        start_date = end_date - pd.DateOffset(months=11)
        start_date = start_date.replace(day=1)
        
        trend_df = hist_df[
            (hist_df['date'] >= start_date) & 
            (hist_df['date'] <= end_date) &
            (hist_df['amount'] > 0) # Only consider positive spend
        ].copy()
        
        if trend_df.empty:
             pdf.cell(0, 10, "No positive spend trend data available.", ln=True)
             return

        # Group by month and category
        trend_df['month_str'] = trend_df['date'].dt.strftime('%Y-%m')
        
        # Calculate total spend per category for sorting
        category_totals = trend_df.groupby('category')['amount'].sum().sort_values(ascending=False)
        sorted_categories = category_totals.index.tolist()
        
        # It's already aggregated by category per month (mostly), but creating a clean DF for Plotly
        monthly_cat_spend = trend_df.groupby(['month_str', 'category'])['amount'].sum().reset_index()
        
        # Format the amount as dollar values for bar labels
        monthly_cat_spend['amount_label'] = monthly_cat_spend['amount'].apply(lambda x: f'${x:,.0f}')
        
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
            # We can't import models dynamically easily if circle dep, using resource file directly is safe
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
        
        # Ensure date is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
             df['date'] = pd.to_datetime(df['date'])
        
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


