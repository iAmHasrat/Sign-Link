from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from dotenv import load_dotenv

load_dotenv()

from models import SignOutput
from prompts import system_template

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0
).with_structured_output(SignOutput)

chat_template = ChatPromptTemplate.from_messages([
    ("system", system_template),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{user_query}")
])

chain = chat_template | llm

