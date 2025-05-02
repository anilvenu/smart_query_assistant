import os
import json
from typing import Dict, Any, List, Optional, Union
from dotenv import load_dotenv

# Load environment variables
load = load_dotenv()
if not load:
    raise EnvironmentError("Failed to load environment variables from .env file.")

# API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

class LLMService:
    """Service for interacting with different LLM providers."""
    
    def __init__(self):
        """Initialize the appropriate LLM client based on environment config."""
        # Get configuration from environment - IMPORTANT: Read this inside __init__
        self.provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
        
        if self.provider == "openai":
            if not OPENAI_API_KEY:
                raise ValueError("OpenAI API key is not set in environment variables")
            import openai
            self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
        elif self.provider == "anthropic":
            if not ANTHROPIC_API_KEY:
                raise ValueError("Anthropic API key is not set in environment variables")
            import anthropic
            self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}. Use 'openai' or 'claude'.")
    
    def generate_text(self, 
                      prompt: str, 
                      system_prompt: Optional[str] = None,
                      temperature: float = 0.0, 
                      max_tokens: int = 2000) -> str:
        """Generate text from the configured LLM provider."""

        if self.provider == "openai":
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
            
        elif self.provider == "anthropic":
            messages = [{"role": "user", "content": prompt}]

            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt if system_prompt else "",
                messages=messages
            )
            if not response.content:
                raise ValueError("Empty response from Claude")

            return response.content[0].text
    
    def generate_structured_output(self, 
                                  prompt: str,
                                  system_prompt: Optional[str] = None,
                                  temperature: float = 0.1) -> Dict[str, Any]:
        """Generate a structured JSON response."""
        # Add instructions to return JSON
        if system_prompt:
            system_prompt += " Return your response as valid JSON."
        else:
            system_prompt = "Return your response as valid JSON."
            
        raw_response = self.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature
        )
        
        # Try to extract JSON from the response
        try:
            # First, try to parse the entire response as JSON
            return json.loads(raw_response)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from the response
            try:
                # Look for JSON-like patterns
                json_start = raw_response.find('{')
                json_end = raw_response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = raw_response[json_start:json_end]
                    return json.loads(json_str)
                else:
                    raise ValueError("No JSON object found in response")
            except (json.JSONDecodeError, ValueError):
                # If all attempts fail, return a dummy object with the raw response
                return {"error": "Failed to parse JSON", "raw_response": raw_response}