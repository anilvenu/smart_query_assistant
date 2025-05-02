import os
import time
from dotenv import load_dotenv
from app.llm.llm_service import LLMService

def run_provider_test(provider):
    """Test the LLM service with a specific provider."""
    # Store provider setting
    original_provider = os.environ.get("LLM_PROVIDER")
    
    try:
        # Set provider for testing
        os.environ["LLM_PROVIDER"] = provider
        
        print(f"\nTesting {provider}")
        try:
            service = LLMService()
            prompt = "What is the capital of France? Keep your answer to one sentence."
            start_time = time.time()
            response = service.generate_text(prompt, temperature=0)
            elapsed_time = time.time() - start_time            
            print(f"Successful call. Took {elapsed_time:.2f} seconds")
            print(f"   - Prompt: \"{prompt}\"")
            print(f"   - Response: \"{response[:100]}{'...' if len(response) > 100 else ''}\"")
            return True
        except Exception as e:
            print(f"Failed: {str(e)}")        
            return False
        
    except Exception as e:
        print(f"Unexpected error during {provider} tests: {str(e)}")
        return False
    
    finally:
        if original_provider:
            os.environ["LLM_PROVIDER"] = original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)

def run_all_tests():
    """Run tests"""
    load_dotenv()
    
    print("Testing OpenAI and Claude LLM.")
    print("Using OPENAI_API_KEY and ANTHROPIC_API_KEY in .env file.")
        
    openai_success = run_provider_test("openai")
    claude_success = run_provider_test("claude")
    
    print("\nSummary of tests:")
    print(f"OpenAI: {'Success' if openai_success else 'Failed'}")
    print(f"Claude: {'Success' if claude_success else 'Failed'}")
    
if __name__ == "__main__":
    run_all_tests()