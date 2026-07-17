from fastapi import FastAPI
from pydantic import BaseModel
from llm import chain
from memory import ChatMemory

memory = ChatMemory()

app = FastAPI()

class signReq(BaseModel):
    text : str

@app.post("/translate")
def translate(request : signReq):
    result = chain.invoke({
        "chat_history" : memory.get(),
        "user_query" : request.text
    })

    memory.add(
        request.text,
        result.corrected_sentence
    )

    return {
        "corrected_sentence": result.corrected_sentence,
        "confidence": result.confidence
    }