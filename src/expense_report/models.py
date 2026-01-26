from dataclasses import dataclass
from datetime import date
from enum import Enum

@dataclass
class Transaction:
    date: date
    description: str
    amount: float

import json
from pathlib import Path

# Load categories from JSON
_CATEGORIES_FILE = Path(__file__).parent / "resources/categories.json"

def _load_categories():
    if not _CATEGORIES_FILE.exists():
        # Fallback or error if file missing, though for this app we expect it to exist
        raise FileNotFoundError(f"Categories file not found at {_CATEGORIES_FILE}")
    with open(_CATEGORIES_FILE, 'r') as f:
        return json.load(f)

# Dynamically create CategoryEnum

CATEGORIES_DATA = _load_categories()
_enum_members = {
    item['name'].upper(): item['name'] 
    for item in CATEGORIES_DATA
}
# Add UNCATEGORIZED if not present in JSON (it usually isn't)
if 'UNCATEGORIZED' not in _enum_members:
    _enum_members['UNCATEGORIZED'] = 'uncategorized'

CategoryEnum = Enum('CategoryEnum', _enum_members)

@dataclass
class Category:
    name: CategoryEnum
    description: str


class CategorizerEnum(Enum):
    KEYWORD = 'keyword'
    LLM = 'llm'

@dataclass
class CategorizedTransaction(Transaction):
    category: CategoryEnum
    categorizer: CategorizerEnum

    @staticmethod
    def from_transaction(transaction: Transaction, category: CategoryEnum, categorizer: CategorizerEnum) -> 'CategorizedTransaction':
        return CategorizedTransaction(
            date=transaction.date,
            description=transaction.description,
            amount=transaction.amount,
            category=category,
            categorizer=categorizer
        )

    def to_dict(self):
        return {
            "date": self.date,
            "description": self.description,
            "amount": self.amount,
            "category": self.category.value,
            "categorizer": self.categorizer.value
        }