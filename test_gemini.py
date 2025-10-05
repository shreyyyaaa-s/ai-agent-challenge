import os
from google import genai

api_key = os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)

# List all available models for your project/key
for m in client.models.list():
    print(m.name)
