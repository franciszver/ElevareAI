"""
OpenAI Client Wrapper
Handles all OpenAI API interactions
"""

from typing import Any, Dict, Optional

import openai

from src.config.settings import settings


class OpenAIClient:
    """Wrapper for OpenAI API client"""

    def __init__(self):
        self.client = openai.OpenAI(
            api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url
        )
        self.model = settings.openrouter_model
        self.temperature = settings.openrouter_temperature
        self.max_tokens = settings.openrouter_max_tokens

    def chat_completion(
        self,
        messages: list[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None,
    ) -> str:
        """
        Generate chat completion

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            response_format: Optional response format (e.g., {"type": "json_object"})

        Returns:
            str: Generated text response
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                response_format=response_format,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    def chat_completion_with_metadata(
        self,
        messages: list[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Generate chat completion with full metadata

        Returns:
            dict with 'content', 'usage', 'model', etc.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                response_format=response_format,
            )
            return {
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "model": response.model,
                "finish_reason": response.choices[0].finish_reason,
            }
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")


# Global client instance
openai_client = OpenAIClient()
