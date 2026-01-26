
import unittest
from unittest.mock import MagicMock, patch
from expense_report.llm_client import LLMClient
from expense_report.models import CategoryEnum

class TestLLMClient(unittest.TestCase):
    @patch.dict('os.environ', {'GOOGLE_MAPS_API_KEY': 'test_api_key'})
    @patch('expense_report.llm_client.OpenAI')
    def test_categorize_transaction(self, mock_openai):
        # Setup mock behavior
        mock_client_instance = MagicMock()
        mock_openai.return_value = mock_client_instance
        
        # Mock responses.parse return value with output_text
        mock_response = MagicMock()
        mock_response.output_text.strip.return_value = "groceries"
        mock_client_instance.responses.parse.return_value = mock_response

        # Instantiate LLMClient
        client = LLMClient()
        
        # Test data
        description = "Test Transaction"
        categories_data = [{'name': 'GROCERIES', 'description': 'Food'}]
        
        # Call method
        result = client.categorize_transaction_with_mcp(description, categories_data)
        
        # Assertions
        self.assertEqual(result, CategoryEnum.GROCERIES)
        
        # Verify call arguments
        mock_client_instance.responses.parse.assert_called_once()
        call_args = mock_client_instance.responses.parse.call_args
        self.assertEqual(call_args.kwargs['model'], "local-model")
        self.assertTrue("Identify the category" in call_args.kwargs['input'][1]['content'])
        self.assertTrue(len(call_args.kwargs['tools']) > 0)

    @patch('expense_report.llm_client.OpenAI')
    def test_categorize_without_api_key(self, mock_openai):
        """Test that categorization works without Google Maps API key"""
        # Setup mock behavior
        mock_client_instance = MagicMock()
        mock_openai.return_value = mock_client_instance
        
        # Mock responses.parse return value with output_text
        mock_response = MagicMock()
        mock_response.output_text.strip.return_value = "groceries"
        mock_client_instance.responses.parse.return_value = mock_response

        # Instantiate LLMClient without API key in env
        client = LLMClient()
        
        # Test data
        description = "Test Transaction"
        categories_data = [{'name': 'GROCERIES', 'description': 'Food'}]
        
        # Call method
        result = client.categorize_transaction_with_mcp(description, categories_data)
        
        # Assertions - should still work
        self.assertEqual(result, CategoryEnum.GROCERIES)
        
        # Verify tools is NOT included when API key is missing
        call_args = mock_client_instance.responses.parse.call_args
        self.assertNotIn('tools', call_args.kwargs)

if __name__ == '__main__':
    unittest.main()
