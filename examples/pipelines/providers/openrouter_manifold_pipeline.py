from typing import List, Union, Generator, Iterator
from schemas import OpenAIChatMessage
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
        Removes any pipeline prefix and ensures correct provider format.
        """
        # Remove any pipeline prefix if present
        if "openrouter_manifold_pipeline." in model_id:
            model_id = model_id.replace("openrouter_manifold_pipeline.", "")
        
        # Handle filter/inlet or filter/outlet suffixes
        if "/filter/" in model_id:
            model_id = model_id.split("/filter/")[0]
            
        return model_id

    def get_openrouter_models(self):
        if self.valves.OPENROUTER_API_KEY:
            try:
                headers = {
                    "Authorization": f"Bearer {self.valves.OPENROUTER_API_KEY}",
                    "HTTP-Referer": self.valves.SITE_URL,
                    "X-Title": self.valves.APP_NAME,
                    "Content-Type": "application/json"
                }
                r = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=headers
                )
                models = r.json()
                return [
                    {
                        "id": model["id"],
                        # Store the original model name without provider prefix
                        "name": model["id"].split("/")[-1],
                        "context_length": model.get("context_length"),
                        "pricing": model.get("pricing", {})
                    }
                    for model in models.get("data", [])
                ]
            except Exception as e:
                print(f"Error: {e}")
                return [
                    {
                        "id": "error",
                        "name": "Could not fetch models from OpenRouter, please update the API Key in the valves.",
                    }
                ]
        else:
            return []

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        print(f"pipe:{__name__}")
        print(messages)
        print(user_message)

        # Format the model ID correctly
        formatted_model_id = self.format_model_id(model_id)
        
        headers = {
            "Authorization": f"Bearer {self.valves.OPENROUTER_API_KEY}",
            "HTTP-Referer": self.valves.SITE_URL,
            "X-Title": self.valves.APP_NAME,
            "Content-Type": "application/json"
        }

        # Clean up the payload
        payload = {**body, "model": formatted_model_id}
        for key in ["user", "chat_id", "title"]:
            payload.pop(key, None)

        # Process messages to handle images if present
        processed_messages = []
        for message in messages:
            if isinstance(message.get("content"), list):
                processed_content = []
                for content in message["content"]:
                    if content["type"] == "text":
                        processed_content.append({"type": "text", "text": content["text"]})
                    elif content["type"] == "image_url":
                        # Process image URL
                        if content["image_url"]["url"].startswith("data:image"):
                            mime_type, base64_data = content["image_url"]["url"].split(",", 1)
                            media_type = mime_type.split(":")[1].split(";")[0]
                            processed_content.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64_data
                                }
                            })
                        else:
                            processed_content.append({
                                "type": "image",
                                "source": {
                                    "type": "url",
                                    "url": content["image_url"]["url"]
                                }
                            })
                message["content"] = processed_content
            processed_messages.append(message)

        payload["messages"] = processed_messages
        print(payload)

        try:
            r = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
                stream=True,
            )
            r.raise_for_status()
            
            if body["stream"]:
                return r.iter_lines()
            else:
                return r.json()
        except Exception as e:
            return f"Error: {e}"
