from pydantic import BaseModel, Field


class ClinicalTranslationRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Clinical summary or note text to translate",
    )
    source_language: str = Field(
        default="en",
        description="Source language code ('en' or 'ta')",
    )
    target_language: str = Field(
        default="ta",
        description="Target language code ('en' or 'ta')",
    )


class ClinicalTranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    disclaimer: str
