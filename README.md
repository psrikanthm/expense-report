# Personal Finance CLI

A command-line tool to analyze and categorize monthly credit card expenses from multiple bank statements.

## Features

- Parse transaction files from multiple banks (Amex, CIBC, Scotia)
- Categorize transactions using keyword matching and LLM-based classification
- Generate PDF reports with spending summaries and 12-month trends
- Email reports via AWS SES

## Prerequisites

- **Python 3.14+**
- **[uv](https://github.com/astral-sh/uv)** - Python package manager
- **[LM Studio](https://lmstudio.ai/)** - For running local LLM models (required for categorization)

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd expense-report

# Install dependencies
uv sync
```

## Configuration

### Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Required environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `LLM_BASE_URL` | LLM API endpoint (default: `http://localhost:1234/v1`) | Optional |
| `LLM_API_KEY` | LLM API key (default: `lm-studio`) | Optional |
| `GOOGLE_MAPS_API_KEY` | Google Maps API key for location-aware categorization | Optional |
| `SES_SMTP_USERNAME` | AWS SES SMTP username | For email only |
| `SES_SMTP_PASSWORD` | AWS SES SMTP password | For email only |
| `SES_FROM_EMAIL` | Sender email address (verified in SES) | For email only |
| `REPORT_RECIPIENTS` | Comma-separated list of recipient emails | For email only |

> **Tip**: To use OpenAI instead of LM Studio, set:
> ```bash
> LLM_BASE_URL=https://api.openai.com/v1
> LLM_API_KEY=sk-your-openai-api-key
> ```

### LM Studio Setup

1. Download and install [LM Studio](https://lmstudio.ai/)
2. Download a model (recommended: `openai/gpt-oss-20b`)
3. Start the local server:
   - Go to the **Developer** tab
   - Click **Start Server** (runs on `http://localhost:1234` by default)
4. The CLI will automatically connect to LM Studio for LLM-based categorization

> **Note**: If `GOOGLE_MAPS_API_KEY` is set, the LLM can use Google Maps MCP tools to look up merchant locations for more accurate categorization of ambiguous transactions.

## Data Files

### Directory Structure

docs/
├── sources/           # Raw transaction files from banks, append new data here (Bronze Layer)
│   ├── amex.csv
│   ├── cibc.csv
│   └── scotia.csv
├── intermediate/      # Parsed and categorized files (Silver Layer)
│   ├── transactions_YYYY-MM.csv
│   └── categorized_YYYY-MM.csv
├── output/            # Definitive monthly aggregates (Gold Layer)
│   └── monthly_YYYY-MM.csv
└── reports/           # Generated PDF reports
    └── report_YYYY-MM.pdf
```

### Adding New Transactions

After downloading transaction files from your bank accounts:

1. **Download** the CSV export from each bank's website
2. **Append** new transactions to the existing source files:

```bash
# For Amex (skip header row from new file)
tail -n +2 ~/Downloads/new_amex_export.csv >> docs/sources/amex.csv

# For CIBC
tail -n +2 ~/Downloads/new_cibc_export.csv >> docs/sources/cibc.csv

# For Scotia  
tail -n +2 ~/Downloads/new_scotia_export.csv >> docs/sources/scotia.csv
```

> **Tip**: Keep the original downloaded files as backups before appending.

## CLI Commands

All commands require a month parameter in `YYYY-MM` format:

### Parse Transactions

Extract transactions from source files for a specific month:

```bash
uv run expense-report parse -m 2026-01
```

### Categorize Transactions

Apply keyword and LLM-based categorization:

```bash
uv run expense-report categorize -m 2026-01
```

### Generate Monthly Data

Filter transactions and create definitive monthly aggregates (Gold Layer):

```bash
uv run expense-report aggregate -m 2026-01
```

### Generate Report

Create a PDF report with spending breakdown and trends:

```bash
uv run expense-report render-pdf -m 2026-01
```

### Send Email

Email the report to configured recipients:

```bash
uv run expense-report send-email -m 2026-01

# Test without sending
uv run expense-report send-email -m 2026-01 --dryrun
```
Even though we use AWS SES for sending emails, any SMTP server can be used by setting the environment variables.
### Full Monthly Workflow

Run all steps in sequence (parse → categorize → monthly-data → report → email):

```bash
uv run expense-report run -m 2026-01

# With email dry-run
uv run expense-report run -m 2026-01 --dryrun
```

## Monthly Workflow

Run this workflow at the beginning of each month for the previous month's data:

1. **Download statements** from your bank accounts (Amex, CIBC, Scotia)
2. **Append transactions** to source files (see [Adding New Transactions](#adding-new-transactions))
3. **Make sure LM Studio is running** with a loaded model
4. **Run the full workflow**:
   ```bash
   uv run expense-report run -m YYYY-MM
   ```
5. **Review the report** at `docs/reports/report_YYYY-MM.pdf`

## Customizing Categories

Edit `src/expense-report/resources/categories.json` to modify:
- Category names and descriptions
- Keyword matching rules
- Amount-based filtering for specific rules

## Testing

```bash
uv run pytest
```

## License

MIT
