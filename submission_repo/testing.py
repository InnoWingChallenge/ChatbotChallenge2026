from dotenv import load_dotenv
import os
# import chromadb
from openai import AzureOpenAI

load_dotenv()

API_Key = os.getenv("AZURE_OPENAI_KEY")
API_Version = os.getenv("AZURE_OPENAI_API_VERSION")
Chat_Base = os.getenv("AZURE_CHAT_BASE")
Embed_Base = os.getenv("AZURE_EMBED_BASE")
Chat_Deployment = os.getenv("CHAT_DEPLOYMENT")
Vision_Deployment = os.getenv("VISION_DEPLOYMENT")
Embed_Deployment = os.getenv("EMBED_DEPLOYMENT")

if not API_Key:
    raise RuntimeError("Missing Azure OpenAI credentials. Set AZURE_OPENAI_KEY in .env or environment.")

client = AzureOpenAI(
    azure_endpoint=f"{Chat_Base}/deployments/{Chat_Deployment}/chat/completions?api-version={API_Version}",
    api_key=API_Key,
    api_version=API_Version,
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
