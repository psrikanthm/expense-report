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
        "output": os.path.join(base_dir, "output")
    }

def _ensure_directories(base_dir: str):
    paths = _get_paths(base_dir)
    os.makedirs(paths["intermediate"], exist_ok=True)
    os.makedirs(paths["output"], exist_ok=True)
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
    df.to_csv(output_file, index=False)
    print(f"Saved {len(all_transactions)} transactions to {output_file}")
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

def run_report(month: str, base_dir: str = DEFAULT_BASE_DIR) -> str:
    """
    Reads categorized_{month}.csv and generates reports/report_{month}.pdf
    Also loads past 11 months of data if available for trend analysis.
    """
    paths = _ensure_directories(base_dir)
    intermediate_dir = paths["intermediate"]
    output_dir = paths["output"]
    
    input_file = os.path.join(intermediate_dir, f"categorized_{month}.csv")
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file {input_file} not found. Run categorize first.")
        
    print(f"Generating report from {input_file} for month {month}...")
    
    # Load current month transactions
    all_transactions = _load_categorized_transactions(input_file)
    
    # Load previous 11 months
    target_date = pd.to_datetime(f"{month}-01")
    for i in range(1, 12):
        prev_date = target_date - pd.DateOffset(months=i)
        prev_month_str = prev_date.strftime("%Y-%m")
        prev_file = os.path.join(intermediate_dir, f"categorized_{prev_month_str}.csv")
        
        if os.path.exists(prev_file):
            print(f"Loading historical data from {prev_file}")
            hist_transactions = _load_categorized_transactions(prev_file)
            all_transactions.extend(hist_transactions)

    from .reports import ReportGenerator
    generator = ReportGenerator(output_dir=output_dir)
    report_path = generator.generate_report(all_transactions, month)
    if not report_path:
        report_path = os.path.join(output_dir, f"report_{month}.pdf")
    
    print(f"Report generated at {report_path}")
    return report_path

def run_email(month: str, dryrun: bool = False, base_dir: str = DEFAULT_BASE_DIR):
    """
    Sends the report email.
    """
    paths = _get_paths(base_dir)
    output_dir = paths["output"]
    
    report_path = os.path.join(output_dir, f"report_{month}.pdf")
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

def run_monthly_workflow(month: str, dryrun: bool = False, base_dir: str = DEFAULT_BASE_DIR):
    """
    Orchestrates the full monthly workflow.
    """
    print(f"Starting monthly workflow for {month} in {base_dir}...")
    run_parse(month, base_dir=base_dir)
    run_categorize(month, base_dir=base_dir)
    run_report(month, base_dir=base_dir)
    run_email(month, dryrun=dryrun, base_dir=base_dir)
    print("Monthly workflow completed successfully.")
