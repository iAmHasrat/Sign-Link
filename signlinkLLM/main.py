
from llm import chain
from memory import ChatMemory



memory = ChatMemory()

while True:

    user_input = input("input: ")

    if user_input.lower() == "exit":
        break

    # Invoke LLM
    result = chain.invoke({
        "chat_history": memory.get(),
        "user_query": user_input
    })

    # Store conversation
    memory.add(
        user_input,
        result.corrected_sentence
    )

    print("\nCorrected:", result.corrected_sentence)
    print("Confidence:", result.confidence)