import os
from openai import OpenAI
from pydantic import BaseModel
import json 
from .models import CategoryEnum

class LLMClient:
    def __init__(self, base_url=None, api_key=None):
        # Read from environment with LM Studio defaults
        self.base_url = base_url or os.getenv('LLM_BASE_URL', 'http://localhost:1234/v1')
        self.api_key = api_key or os.getenv('LLM_API_KEY', 'lm-studio')
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.nr_maps_calls = 0
        
        # Google Maps MCP is optional - only enabled if API key is set
        self.google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        self.mcp_enabled = bool(self.google_maps_api_key)
        if not self.mcp_enabled:
            print("Note: GOOGLE_MAPS_API_KEY not set. Location-aware categorization disabled.")

    def categorize_transaction_with_mcp(self, description: str, categories_data: list[dict]) -> CategoryEnum:
        """
        Categorizes a transaction utilizing MCP tools via the /v1/responses API.
        This is useful for transactions that require external knowledge (e.g. location data).
        """
        # Construct a detailed description of categories
        categories_text = ""
        valid_names = []
        for cat in categories_data:
            name = cat['name']
            desc = cat.get('description', '')
            categories_text += f"- {name}: {desc}\n"
            valid_names.append(name)
        
        prompt = f"""
        You are a transaction categorization agent. You process raw credit card strings into clean categories. 

        ### THE "SEARCH" RULE (Tool Use)
        You MUST use 'google_maps_search' in the following scenarios:
        - HIGH-VARIANCE BRANDS: The brand could fall into two categories. 
        (e.g., 7-ELEVEN, SHELL, or ESSO can be 'car' for gas or 'groceries' for the store. COSTCO can be 'groceries' or 'house').
        - OBSCURE/LOCAL NAMES: The merchant name is not a household brand (e.g., "JOE'S VARIETY", "ULTRAMAR", "P&M RETAIL").
        - LOCATION CONFLICT: If the transaction contains a city (e.g., "WHITBY") and you are even 1% unsure if that brand operates the same way in that specific region.
        Then return the category from the search result.

        ### CATEGORY DEFINITIONS
        {categories_text}

        ### THINKING PROCESS
        Before answering, follow this logic:
        "Are you 100% sure this brand fits into ONE category in that region? 
        -> Yes: Provide category immediately.
        -> No: Call google_maps_search to verify this specific location. Return the category from the search result."

        ### FINAL OUTPUT
        Return the category name only.
        """
        try:
            class TransactionCategory(BaseModel):
                category: CategoryEnum

            # Build tools list - only include MCP if API key is available
            tools = []
            if self.mcp_enabled:
                tools = [{
                    "type": "mcp",
                    "server_label": "Google Maps",
                    "server_url": f"https://mapstools.googleapis.com/mcp?key={self.google_maps_api_key}",
                }]

            # Build request kwargs - only include tools if non-empty
            request_kwargs = {
                "model": "local-model",
                "input": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Identify the category for the transaction '{description}."},
                ],
            }
            
            if tools:
                request_kwargs["tools"] = tools
                request_kwargs["max_tool_calls"] = 3

            response = self.client.responses.parse(**request_kwargs)
            return CategoryEnum(response.output_text.strip())

        except Exception as e:
            print(f"Error calling LLM with MCP: {e}")
            return CategoryEnum.UNCATEGORIZED

    def get_nr_maps_calls(self):
        return self.nr_maps_calls
        