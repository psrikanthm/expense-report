from typing import List
from .models import Transaction, CategoryEnum, CategorizedTransaction, CategorizerEnum
from .parsers import AmexParser, CibcParser, ScotiaParser
from .categorizers import Categorizer, KeywordCategorizer, LLMCategorizer
from tqdm import tqdm
import pandas as pd
import os

# Define paths
DEFAULT_BASE_DIR = "docs"

def _get_paths(base_dir: str):
    return {
        "sources": os.path.join(base_dir, "sources"),
        "intermediate": os.path.join(base_dir, "intermediate"),
        "output": os.path.join(base_dir, "output"),
        "reports": os.path.join(base_dir, "reports")
    }

def _ensure_directories(base_dir: str):
    paths = _get_paths(base_dir)
    os.makedirs(paths["intermediate"], exist_ok=True)
    os.makedirs(paths["output"], exist_ok=True)
    os.makedirs(paths["reports"], exist_ok=True)
    return paths

def run_parse(month: str, base_dir: str = DEFAULT_BASE_DIR) -> str:
    """
    Parses transactions from known source files for the given month.
    Saves to {base_dir}/intermediate/transactions_{month}.csv
    """
    paths = _ensure_directories(base_dir)
    intermediate_dir = paths["intermediate"]
    sources_dir = paths["sources"]
    
    print(f"Parsing transactions for month: {month} in {base_dir}")
    
    parsers = [
        (AmexParser(), os.path.join(sources_dir, "amex.csv")),
        (CibcParser(), os.path.join(sources_dir, "cibc.csv")),
        (ScotiaParser(), os.path.join(sources_dir, "scotia.csv"))
    ]
    
    all_transactions: List[Transaction] = []
    
    for parser, file_path in parsers:
        if os.path.exists(file_path):
            print(f"Parsing {file_path}...")
            transactions = parser.parse(file_path, month)
            print(f"Found {len(transactions)} transactions in {file_path}")
            all_transactions.extend(transactions)
        else:
            print(f"Warning: Source file {file_path} not found.")
            
    output_file = os.path.join(intermediate_dir, f"transactions_{month}.csv")
    # Convert to DataFrame for saving
    data = []
    for t in all_transactions:
        data.append({
            "date": t.date,
            "description": t.description,
            "amount": t.amount
        })
    
    df = pd.DataFrame(data)
    
    # Deduplicate transactions based on date, description, and amount
    # This ensures we don't have repeat entries if we re-parse or have partial overlaps
    original_count = len(df)
    df = df.drop_duplicates(subset=['date', 'description', 'amount'], keep='first')
    deduped_count = len(df)
    
    if original_count != deduped_count:
        print(f"Removed {original_count - deduped_count} duplicate transactions (from {original_count} to {deduped_count})")
    
    df.to_csv(output_file, index=False)
    print(f"Saved {deduped_count} transactions to {output_file}")
    return output_file

def run_categorize(month: str, base_dir: str = DEFAULT_BASE_DIR) -> str:
    """
    Reads {base_dir}/intermediate/transactions_{month}.csv, categorizes them, and saves to {base_dir}/intermediate/categorized_{month}.csv
    """
    paths = _ensure_directories(base_dir)
    intermediate_dir = paths["intermediate"]
    
    input_file = os.path.join(intermediate_dir, f"transactions_{month}.csv")
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file {input_file} not found. Run parse first.")
        
    print(f"Categorizing transactions from {input_file}...")
    df = pd.read_csv(input_file)
    
    # Reconstruct Transactions
    transactions = []
    for _, row in df.iterrows():
        transactions.append(Transaction(
            date=pd.to_datetime(row['date']).date(),
            description=row['description'],
            amount=row['amount']
        ))
        
    kw_categorizer: Categorizer = KeywordCategorizer()
    llm_categorizer: Categorizer = LLMCategorizer()
    
    categorized_transactions = []
    for t in tqdm(transactions):
        # Apply Keyword Categorizer first
        categorized_t = kw_categorizer.categorize(t)
        
        # If uncategorized, use LLM
        if categorized_t.category == CategoryEnum.UNCATEGORIZED:
             categorized_t = llm_categorizer.categorize(t)
             
        categorized_transactions.append(categorized_t)
        
    print(f"Categorized {len(categorized_transactions)} transactions")
    print(f"Google Maps MCP was called {llm_categorizer.get_nr_maps_calls()} times")

    output_file = os.path.join(intermediate_dir, f"categorized_{month}.csv")
    df_out = pd.DataFrame([t.to_dict() for t in categorized_transactions])
    df_out.to_csv(output_file, index=False)
    print(f"Saved categorized transactions to {output_file}")
    return output_file

def _load_categorized_transactions(file_path: str) -> List[CategorizedTransaction]:
    if not os.path.exists(file_path):
        return []
    
    df = pd.read_csv(file_path)
    transactions = []
    for _, row in df.iterrows():
        try:
            category_enum = CategoryEnum[row['category'].upper()]
        except (KeyError, ValueError):
            category_enum = CategoryEnum.UNCATEGORIZED
            
        try:
            categorizer_enum = CategorizerEnum(row['categorizer'])
        except (ValueError, TypeError):
            categorizer_enum = CategorizerEnum.KEYWORD 

        t = CategorizedTransaction(
            date=pd.to_datetime(row['date']).date(),
            description=row['description'],
            amount=row['amount'],
            category=category_enum,
            categorizer=categorizer_enum
        )
        transactions.append(t)
    return transactions

def run_aggregate(month: str, base_dir: str = DEFAULT_BASE_DIR) -> str:
    """
    Reads categorized transactions, filters excluded categories, aggregates spend by category,
    and saves to {base_dir}/output/monthly_{month}.csv.
    """
    paths = _ensure_directories(base_dir)
    intermediate_dir = paths["intermediate"]
    # Ensure output directory exists (previously gold)
    output_dir = paths["output"]
    os.makedirs(output_dir, exist_ok=True)
    
    input_file = os.path.join(intermediate_dir, f"categorized_{month}.csv")
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file {input_file} not found. Run categorize first.")
        
    print(f"Generating monthly report data from {input_file}...")
    
    # Load excluded categories config
    from .models import _load_categories
    categories_data = _load_categories()
    excluded_categories = {
        cat['name'].upper() 
        for cat in categories_data 
        if cat.get('report_excluded', False)
    }
    
    df = pd.read_csv(input_file)
    original_count = len(df)
    
    # Safety Check: Deduplicate again just in case intermediate file has issues
    df = df.drop_duplicates(subset=['date', 'description', 'amount'], keep='first')
    deduped_count = len(df)
    
    if original_count != deduped_count:
        print(f"Safety Check: Removed {original_count - deduped_count} duplicate transactions in monthly-data step")

    # Filter excluded categories
    # Normalize category column to uppercase for comparison
    df['category_upper'] = df['category'].str.upper()
    df_filtered = df[~df['category_upper'].isin(excluded_categories)].copy()
    filtered_count = len(df_filtered)
    
    # Filter out -ve amounts    
    df_filtered = df_filtered[df_filtered['amount'] > 0]
    filtered_count = len(df_filtered)

    if original_count != filtered_count:
        print(f"Filtered out {original_count - filtered_count} transactions from excluded categories: {excluded_categories}")
    
    # Aggregate by category
    # Group by category (using original casing from first occurrence or consistently upper/title)
    # We'll stick to the category column value
    aggregates = df_filtered.groupby('category')['amount'].sum().reset_index()
    
    output_file = os.path.join(output_dir, f"monthly_{month}.csv")
    aggregates.to_csv(output_file, index=False)
    
    print(f"Saved monthly aggregates to {output_file}")
    return output_file

def run_render_pdf(month: str, base_dir: str = DEFAULT_BASE_DIR) -> str:
    """
    Reads output/monthly_{month}.csv (aggregates) and intermediate/categorized_{month}.csv (details).
    Generates reports/report_{month}.pdf calling the generator.
    Also loads past 11 months of data from gold layer for trend analysis.
    """
    paths = _ensure_directories(base_dir)
    intermediate_dir = paths["intermediate"]
    output_dir = paths["output"] # contains aggregates
    reports_dir = paths["reports"] # contains PDFs

    
    # 1. Load Current Month Aggregates
    gold_file = os.path.join(output_dir, f"monthly_{month}.csv")
    if not os.path.exists(gold_file):
        raise FileNotFoundError(f"Gold file {gold_file} not found. Run aggregate first.")
    
    print(f"Loading current month aggregates from {gold_file}")
    current_aggregates = pd.read_csv(gold_file)
    current_aggregates['date'] = pd.to_datetime(f"{month}-01") # Dummy date for plotting if needed, usage depends on reports.py
    # Actually, reports might expect a 'month_str' or similar. Let's see how we adapt reports.py.
    # For now, let's keep it simple.
    
    # 2. Load Historical Aggregates
    all_aggregates = [current_aggregates]
    target_date = pd.to_datetime(f"{month}-01")
    
    for i in range(1, 12):
        prev_date = target_date - pd.DateOffset(months=i)
        prev_month_str = prev_date.strftime("%Y-%m")
        prev_gold_file = os.path.join(output_dir, f"monthly_{prev_month_str}.csv")
        
        if os.path.exists(prev_gold_file):
            # print(f"Loading historical data from {prev_gold_file}")
            hist_df = pd.read_csv(prev_gold_file)
            hist_df['date'] = prev_date # Assign the month date to these rows
            all_aggregates.append(hist_df)
            
    full_history_aggregates = pd.concat(all_aggregates, ignore_index=True)

    # 3. Load Current Month Details (Line-by-line)
    input_file = os.path.join(intermediate_dir, f"categorized_{month}.csv")
    if not os.path.exists(input_file):
         raise FileNotFoundError(f"Input file {input_file} not found. Run categorize first.")

    print(f"Loading transaction details from {input_file}...")
    # We still need to filter these details to match the gold aggregates (remove report_excluded)
    # so the table doesn't show stuff that isn't in the charts.
    
    from .models import _load_categories
    categories_data = _load_categories()
    excluded_categories = {
        cat['name'].upper() 
        for cat in categories_data 
        if cat.get('report_excluded', False)
    }
    
    details_df = pd.read_csv(input_file)
    details_df['category_upper'] = details_df['category'].str.upper()
    filtered_details_df = details_df[~details_df['category_upper'].isin(excluded_categories)].copy()
    
    # Convert filtered details back to list of objects or just pass DF if we update reports.py
    # reports.py expects List[CategorizedTransaction]. Let's adapt reports.py to take DF or we reconstruct objects.
    # Reconstructing objects for now to minimize reports.py signature changes unless we decided to change it deep.
    # The plan said: "Update generate_report signature to accept current_aggregates, historical_aggregates, and transaction_details"
    
    from .reports import ReportGenerator
    generator = ReportGenerator(output_dir=reports_dir)
    
    # converting filtered_details_df to a list of CategorizedTransaction for backward compatibility 
    # OR we follow the plan and update ReportGenerator.
    # Let's update ReportGenerator. So here we pass DFs.
    
    report_path = generator.generate_report(
        current_aggregates=current_aggregates,
        historical_aggregates=full_history_aggregates,
        transaction_details=filtered_details_df,
        month=month
    )
    
    if not report_path:
        report_path = os.path.join(reports_dir, f"report_{month}.pdf")
    
    print(f"Report generated at {report_path}")
    return report_path

def run_email(month: str, dryrun: bool = False, base_dir: str = DEFAULT_BASE_DIR):
    """
    Sends the report email.
    """
    paths = _get_paths(base_dir)
    reports_dir = paths["reports"]
    
    report_path = os.path.join(reports_dir, f"report_{month}.pdf")
    if not os.path.exists(report_path):
        raise FileNotFoundError(f"Report not found at {report_path}. Run report generation first.")
        
    print(f"Sending email for report {report_path} (dryrun={dryrun})...")
    from .notifier import SESClient
    
    # Load recipients from environment variable (comma-separated)
    recipients_env = os.getenv('REPORT_RECIPIENTS', '')
    if not recipients_env:
        raise ValueError("REPORT_RECIPIENTS environment variable not set. Set it to a comma-separated list of email addresses.")
    recipients = [r.strip() for r in recipients_env.split(',') if r.strip()]
    
    subject = f"Monthly Spending Report - {month}"
    text = f"Please find attached the monthly spending report for {month}."
    
    client = SESClient()
    client.send_email(to=recipients, subject=subject, text=text, attachment_path=report_path, dryrun=dryrun)

def run_full_workflow(month: str, dryrun: bool = False, base_dir: str = DEFAULT_BASE_DIR):
    """
    Orchestrates the full monthly workflow.
    """
    print(f"Starting monthly workflow for {month} in {base_dir}...")
    run_parse(month, base_dir=base_dir)
    run_categorize(month, base_dir=base_dir)
    run_aggregate(month, base_dir=base_dir)
    run_render_pdf(month, base_dir=base_dir)
    run_email(month, dryrun=dryrun, base_dir=base_dir)
    print("Monthly workflow completed successfully.")
