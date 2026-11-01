import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise RuntimeError("GROQ_API_KEY is missing from .env")


llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0.2,
    api_key=api_key,
)


response = llm.invoke(
    "A family of 4 wants to visit Vaishno Devi from Bhopal "
    "for 3 days. They prefer travelling by train. "
    "Suggest a simple travel plan."
)

print("\n===== GROQ RESPONSE =====\n")
print(response.content)