import argparse
from dotenv import load_dotenv
from .jobs import run_parse, run_categorize, run_report, run_email, run_monthly_workflow

# Load environment variables from .env file
load_dotenv()

def main():
    parser = argparse.ArgumentParser(prog='insights', 
                                     description='Personal Finance CLI Tool')
    
    subparsers = parser.add_subparsers(dest='command', help='Subcommands')
    
    # Common arguments
    def add_common_args(p):
        p.add_argument('-m', '--month', required=True, help='Month to process (YYYY-MM)')
    
    # 1. Parse
    parser_parse = subparsers.add_parser('parse', help='Parse raw transactions from docs/sources/')
    add_common_args(parser_parse)
    
    # 2. Categorize
    parser_cat = subparsers.add_parser('categorize', help='Categorize parsed transactions')
    add_common_args(parser_cat)
    
    # 3. Report
    parser_rep = subparsers.add_parser('generate-report', help='Generate PDF report')
    add_common_args(parser_rep)
    
    # 4. Email
    parser_email = subparsers.add_parser('send-email', help='Send report via email')
    add_common_args(parser_email)
    parser_email.add_argument('--dryrun', action='store_true', help='Simulate email sending')
    
    # 5. Monthly Report (Full Workflow)
    parser_full = subparsers.add_parser('monthly-report', help='Run full monthly workflow')
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
        elif args.command == 'generate-report':
            run_report(args.month)
        elif args.command == 'send-email':
            run_email(args.month, dryrun=args.dryrun)
        elif args.command == 'monthly-report':
            run_monthly_workflow(args.month, dryrun=args.dryrun)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

