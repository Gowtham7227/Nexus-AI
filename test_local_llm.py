from local_llm import ask_local


context = """
NexusAI is an AI-powered document intelligence assistant.
It uses Retrieval Augmented Generation to answer questions
from uploaded documents.
"""

question = "What is NexusAI?"

answer = ask_local(
    context,
    question
)

print("=" * 60)
print("LOCAL QWEN TEST")
print("=" * 60)
print(answer)
print("=" * 60)