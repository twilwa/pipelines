from typing import List, Union, Generator, Iterator
from pydantic import BaseModel
import os
import requests

class Pipeline:
    class Valves(BaseModel):
        OPENROUTER_API_KEY: str = ""
        SITE_URL: str = ""
        APP_NAME: str = ""

    def __init__(self):
        self.type = "manifold"
        self.name = "OpenRouter: "
        self.valves = self.Valves(
            **{
                "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
                "SITE_URL": os.getenv("SITE_URL", ""),
                "APP_NAME": os.getenv("APP_NAME", ""),
            }
        )
        self.pipelines = self.get_openrouter_models()

    def format_model_id(self, model_id: str) -> str:
        """
        Format the model ID to match OpenRouter's expected format.
        """
        # Handle pipeline prefix
        if "openrouter_manifold_pipeline." in model_id:
            # Extract just the provider/model part
            model_id = model_id.replace("openrouter_manifold_pipeline.", "")
        
        # Handle filter endpoints
        if "/filter/" in model_id:
            model_id = model_id.split("/filter/")[0]
            
        return model_id

    def get_openrouter_models(self):
        if not self.valves.OPENROUTER_API_KEY:
            return []
            
        try:
            headers = {
                "Authorization": f"Bearer {self.valves.OPENROUTER_API_KEY}",
                "HTTP-Referer": self.valves.SITE_URL,
                "X-Title": self.valves.APP_NAME,
            }
            
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers
            )
            response.raise_for_status()
            models = response.json()
            
            return [
                {
                    "id": f"{model['id']}",  # Keep the full provider/model ID
                    "name": model['name'] if 'name' in model else model['id'].split('/')[-1],
                    "context_length": model.get("context_length"),
                    "pricing": model.get("pricing", {})
                }
                for model in models.get("data", [])
            ]
        except Exception as e:
            print(f"Error fetching OpenRouter models: {e}")
            return [{
                "id": "error",
                "name": "Could not fetch models from OpenRouter. Please check your API key.",
            }]

    async def on_startup(self):
        print(f"on_startup:{__name__}")

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")

    async def on_valves_updated(self):
        print(f"on_valves_updated:{__name__}")
        self.pipelines = self.get_openrouter_models()

    def pipe(
        self, 
        user_message: str, 
        model_id: str, 
        messages: List[dict], 
        body: dict
    ) -> Union[str, Generator, Iterator]:
        print(f"pipe:{__name__}")
        print(f"Original model_id: {model_id}")
        
        # Format the model ID correctly
        formatted_model_id = self.format_model_id(model_id)
        print(f"Formatted model_id: {formatted_model_id}")
        
        headers = {
            "Authorization": f"Bearer {self.valves.OPENROUTER_API_KEY}",
            "HTTP-Referer": self.valves.SITE_URL,
            "X-Title": self.valves.APP_NAME,
            "Content-Type": "application/json"
        }

        # Clean up the payload
        payload = {
            **body,
            "model": formatted_model_id,
            "messages": messages
        }
        
        # Remove unnecessary fields
        for key in ["user", "chat_id", "title"]:
            payload.pop(key, None)

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
                stream=body.get("stream", False)
            )
            response.raise_for_status()
            
            if body.get("stream", False):
                return response.iter_lines()
            return response.json()
            
        except Exception as e:
            print(f"OpenRouter API error: {e}")
            return f"Error: {e}"
