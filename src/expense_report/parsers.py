from abc import ABC, abstractmethod
from typing import List, Optional
import pandas as pd
from datetime import datetime
from .models import Transaction

class Parser(ABC):
    @abstractmethod
    def parse(self, file_path: str, month: Optional[str] = None) -> List[Transaction]:
        """
        Parse the file and return transactions.
        If month is provided (YYYY-MM), filter transactions for that month.
        """
        pass

    def _filter_by_month(self, transactions: List[Transaction], month: str) -> List[Transaction]:
        if not month:
            return transactions
        
        target_year, target_month = map(int, month.split('-'))
        filtered = []
        for t in transactions:
            if t.date.year == target_year and t.date.month == target_month:
                filtered.append(t)
        return filtered

class AmexParser(Parser):
    def parse(self, file_path: str, month: Optional[str] = None) -> List[Transaction]:
        # Header: Date,Date Processed,Description,Amount
        df = pd.read_csv(file_path)
        transactions = []
        for _, row in df.iterrows():
            date_str = row.get('Date')
            description = row.get('Description')
            amount = row.get('Amount')
            
            if date_str and pd.notna(amount):
                try:
                    # Amex date format: "28 Dec 2025"
                    trans_date = datetime.strptime(str(date_str), '%d %b %Y').date()
                    # Amex: Positive amount is expense

                    if amount > 0:
                        transactions.append(Transaction(
                            date=trans_date,
                            description=str(description),
                            amount=float(amount)
                        ))
                except ValueError as e:
                    print(f"Skipping invalid row in Amex: {row} - {e}")
                    continue
        
        return self._filter_by_month(transactions, month)

class CibcParser(Parser):
    def parse(self, file_path: str, month: Optional[str] = None) -> List[Transaction]:
        # Header: Date,Description,Debit,Credit,CardNum
        df = pd.read_csv(file_path)
        transactions = []
        for _, row in df.iterrows():
            date_str = row.get('Date')
            description = row.get('Description')
            debit = row.get('Debit')
            credit = row.get('Credit')
            
            if date_str:
                try:
                    # CIBC date format: "2026-01-02" (ISO)
                    trans_date = datetime.strptime(str(date_str), '%Y-%m-%d').date()
                    
                    amount = 0.0
                    if pd.notna(debit) and str(debit).strip():
                        amount = float(debit) # Debit is expense -> positive
                    elif pd.notna(credit) and str(credit).strip():
                        amount = -float(credit) # Credit is payment/refund -> negative
                    else:
                        # skipping credit rows = no expense
                        continue
                    
                    if amount > 0:
                        # Store transaction
                        transactions.append(Transaction(
                            date=trans_date,
                            description=str(description),
                            amount=amount
                        ))
                except ValueError as e:
                    print(f"Skipping invalid row in CIBC: {row} - {e}")
                    continue
        return self._filter_by_month(transactions, month)

class ScotiaParser(Parser):
    def parse(self, file_path: str, month: Optional[str] = None) -> List[Transaction]:
        # Header: Filter,Date,Description,Sub-description,Type of Transaction,Amount,Balance
        # We only care about "Debit" transactions as per requirement
        df = pd.read_csv(file_path)
        transactions = []
        for _, row in df.iterrows():
            if str(row.get('Type of Transaction')) != 'Debit':
                continue

            date_str = row.get('Date')
            description = row.get('Description')
            sub_desc = row.get('Sub-description')
            amount_val = row.get('Amount')
            
            full_desc = f"{description} {sub_desc}".strip()
            
            if date_str and pd.notna(amount_val):
                try:
                    # Scotia date format: "2026-01-06"
                    trans_date = datetime.strptime(str(date_str), '%Y-%m-%d').date()
                    
                    # Scotia: Debit is negative in CSV (e.g. -450.00).
                    # Requirement: Convert to positive for expense.
                    amount = -float(amount_val)
                    
                    if amount > 0:
                        transactions.append(Transaction(
                            date=trans_date,
                            description=full_desc,
                            amount=amount
                        ))
                except ValueError as e:
                    print(f"Skipping invalid row in Scotia: {row} - {e}")
                    continue
        
        return self._filter_by_month(transactions, month)
