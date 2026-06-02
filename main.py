from dotenv import load_dotenv
import os
from typing import List
import chromadb
from openai import AzureOpenAI

# ====================== LOAD ENVIRONMENT ======================
load_dotenv()

API_Key = os.getenv("AZURE_OPENAI_API_KEY")

if not API_Key:
    raise RuntimeError("Missing Azure OpenAI credentials. Set AZURE_OPENAI_API_KEY in .env or environment.")


# ====================== CORE RAG FUNCTION ======================
def rag_answer(question: str) -> str:
    """
    Input: A single question (string)
    Output: A single answer (string)
    """
    
    #Implement your chatbot logic here.
    answer = ""
    return answer

# ====================== PUBLIC API FUNCTION ======================
def generate_rag_answers(questions: List[str]) -> List[str]:
    """
    Input: List of questions (strings)
    Output: zip of (question, answer) pairs
    
    Example usage:
        from rag import generate_rag_answers
        answers = generate_rag_answers([
            "What are the current SIGs in InnoWings?",
            "Tell me about recent Tech Talks in InnoAcademy."
        ])
        print(answers)
    """
    answers = []
    for question in questions:
        print(f"🤖 Answering: {question[:80]}{'...' if len(question) > 80 else ''}")
        answer = rag_answer(question)
        answers.append(answer)
    return zip(questions, answers)