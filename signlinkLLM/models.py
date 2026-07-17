from pydantic import BaseModel, Field

class SignOutput(BaseModel):
    corrected_sentence: str = Field(
        description="Grammatically correct English sentence"
    )

    confidence: str = Field(
        description="high, medium, or low"
    )