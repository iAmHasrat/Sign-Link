from collections import deque
from langchain_core.messages import HumanMessage, AIMessage

class ChatMemory:

    def __init__(self, maxlen=20):
        self.history = deque(maxlen=maxlen)

    def add(self, user_input, ai_output):
        self.history.append(HumanMessage(content=user_input))
        self.history.append(AIMessage(content=ai_output))

    def get(self):
        return list(self.history)

    def clear(self):
        self.history.clear()