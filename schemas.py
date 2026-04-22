from pydantic import BaseModel, Field
from typing import List

class UserProfile(BaseModel):
    assessed_knowledge: str = Field(description="Summary of what the user already knows about the topic.")
    target_goal: str = Field(description="The final goal the user wants to achieve.")
    goal_archetype: str = Field(description="Must be exactly 'THEORETICAL' or 'PRACTICAL_PROJECT'")

class SyllabusUnit(BaseModel):
    unit_order: int
    title: str
    module_type: str = Field(description="Must be 'CONCEPT_LECTURE', 'HANDS_ON_TUTORIAL', or 'PROJECT_MILESTONE'")
    learning_objective: str = Field(description="The specific knowledge or skill the user should gain from this unit.")

class SyllabusOutline(BaseModel):
    units: List[SyllabusUnit]
    
class CriticReview(BaseModel):
    status: str = Field(description="Must be exactly 'APPROVED' or 'REJECTED'")
    feedback: str = Field(description="Specific instructions on what must be fixed if rejected. Empty if approved.")