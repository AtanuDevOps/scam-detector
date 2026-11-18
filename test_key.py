import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(api_version="v1beta"),
)
r = client.models.generate_content(
    model=os.getenv("GEMINI_MODEL"),
    contents="একটি বাক্যে বাংলায় বলো: হ্যালো!",
)
print(r.text)