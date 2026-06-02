from dotenv import load_dotenv
import os
import chromadb
from openai import AzureOpenAI

load_dotenv()

API_Key = os.getenv("AZURE_OPENAI_API_KEY")

if not API_Key:
    raise RuntimeError("Missing Azure OpenAI credentials. Set AZURE_OPENAI_API_KEY in .env or environment.")

client = AzureOpenAI(
    azure_endpoint="https://api-iw.azure-api.net/sig-shared-jpeast/deployments/gpt-4o-mini/chat/completions?api-version=2025-01-01-preview",
    api_key=API_Key,
    api_version="2025-01-01-preview",
)

messages = [
        {
            "role": "user",
            "content": "Question: ‘Who are you?’"
        }
    ]

answer = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    ).choices[0].message.content

print("Question: Who are you?")
print("Answer:", answer)
