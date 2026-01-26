import argparse
from dotenv import load_dotenv
from .jobs import run_parse, run_categorize, run_render_pdf, run_email, run_full_workflow

# Load environment variables from .env file
load_dotenv()

def main():
    parser = argparse.ArgumentParser(prog='insights', 
                                     description='Personal Finance CLI Tool')
    
    subparsers = parser.add_subparsers(dest='command', help='Subcommands')
    
    # Common arguments
    def add_common_args(p):
        p.add_argument('-m', '--month', required=True, help='Month to process (YYYY-MM)')
    
    # 1. Parse (normalized data - silver layer)
    parser_parse = subparsers.add_parser('parse', help='Parse raw transactions from docs/sources/ into standard format')
    add_common_args(parser_parse)
    
    # 2. Categorize (enriched data - silver layer)
    parser_cat = subparsers.add_parser('categorize', help='Categorize parsed transactions')
    add_common_args(parser_cat)

    # 3. Generate Monthly Aggregates (Gold Layer)
    parser_gold = subparsers.add_parser('aggregate', help='Generate monthly category spend summary')
    add_common_args(parser_gold)

    # 4. Report ( consumer facing)
    parser_rep = subparsers.add_parser('render-pdf', help='Generate PDF report with spend summary and charts')
    add_common_args(parser_rep)
    
    # 5. Email ( consumer facing)
    parser_email = subparsers.add_parser('send-email', help='Send report via email')
    add_common_args(parser_email)
    parser_email.add_argument('--dryrun', action='store_true', help='Simulate email sending')
    
    # 6. Monthly Report (Full Workflow)
    parser_full = subparsers.add_parser('run', help='Run full monthly workflow (parse, categorize, aggregate, render-pdf, send-email)')
    add_common_args(parser_full)
    parser_full.add_argument('--dryrun', action='store_true', help='Simulate email sending')
    
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == 'parse':
            run_parse(args.month)
        elif args.command == 'categorize':
            run_categorize(args.month)
        elif args.command == 'aggregate':
            # Import dynamically to avoid circular issues if any, or just call run_aggregate
            # Assuming run_aggregate is exported in jobs.py
            from .jobs import run_aggregate
            run_aggregate(args.month)
        elif args.command == 'render-pdf':
            run_render_pdf(args.month)
        elif args.command == 'send-email':
            run_email(args.month, dryrun=args.dryrun)
        elif args.command == 'run':
            run_full_workflow(args.month, dryrun=args.dryrun)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

