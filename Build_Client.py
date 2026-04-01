from openai import AzureOpenAI
import os
from dotenv import load_dotenv
load_dotenv()

def build_client():
    client = AzureOpenAI(
        api_version=os.getenv("api_version"),
        azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    return client