from abc import ABC, abstractmethod
from .models import Transaction, CategorizedTransaction, CategoryEnum, CATEGORIES_DATA, CategorizerEnum

class Categorizer(ABC):
    @abstractmethod
    def categorize(self, transaction: Transaction) -> CategorizedTransaction:
        pass

class KeywordCategorizer(Categorizer):
    def __init__(self):
        self.rules = []
        for category_item in CATEGORIES_DATA:
            cat_enum = CategoryEnum(category_item['name'])
            
            # Support legacy simple keywords list
            if 'keywords' in category_item:
                self.rules.append({
                    'category': cat_enum,
                    'keywords': category_item['keywords'],
                    'min_amount': 0,
                    'max_amount': 1000000
                })
            
            # Support new rich rules
            if 'rules' in category_item:
                for rule in category_item['rules']:
                    self.rules.append({
                        'category': cat_enum,
                        'keywords': rule.get('keywords', []),
                        'min_amount': rule.get('min_amount', 0),
                        'max_amount': rule.get('max_amount', 1000000)
                    })

    def categorize(self, transaction: Transaction) -> CategorizedTransaction:
        description_lower = transaction.description.lower()
        amount = transaction.amount

        for rule in self.rules:
            # Check keywords
            for keyword in rule['keywords']:
                if keyword in description_lower and amount >= rule['min_amount'] and amount <= rule['max_amount']:
                    return CategorizedTransaction.from_transaction(
                        transaction=transaction,
                        category=rule['category'],
                        categorizer=CategorizerEnum.KEYWORD
                    )
        
        return CategorizedTransaction.from_transaction(
            transaction=transaction,
            category=CategoryEnum.UNCATEGORIZED,
            categorizer=CategorizerEnum.KEYWORD
        )

from .llm_client import LLMClient

class LLMCategorizer(Categorizer):
    def __init__(self):
        self.client = LLMClient()

    def categorize(self, transaction: Transaction) -> CategorizedTransaction:
        category = self.client.categorize_transaction_with_mcp(transaction.description, CATEGORIES_DATA)
                    
        return CategorizedTransaction.from_transaction(
            transaction=transaction,
            category=category,
            categorizer=CategorizerEnum.LLM 
        )

    def get_nr_maps_calls(self):
        return self.client.get_nr_maps_calls()
