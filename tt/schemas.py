from typing import List, Literal

from pydantic import BaseModel, Field


GoalArchetype = Literal["THEORETICAL", "PRACTICAL_PROJECT"]
ModuleType = Literal["CONCEPT_LECTURE", "HANDS_ON_TUTORIAL", "PROJECT_MILESTONE"]
ReviewStatus = Literal["APPROVED", "REJECTED"]


class UserProfile(BaseModel):
    assessed_knowledge: str = Field(
        description="Summary of what the user already knows about the topic."
    )
    target_goal: str = Field(
        description="The final goal the user wants to achieve."
    )
    goal_archetype: GoalArchetype = Field(
        description="Whether the learner needs theoretical understanding or a practical project."
    )


class SyllabusUnit(BaseModel):
    unit_order: int = Field(description="1-based unit number in teaching order.")
    title: str = Field(description="Specific unit title.")
    module_type: ModuleType = Field(
        description="The style of the unit."
    )
    learning_objective: str = Field(
        description="The concrete knowledge or skill gained in this unit."
    )


class SyllabusOutline(BaseModel):
    units: List[SyllabusUnit] = Field(
        description="Ordered list of course units."
    )


class CriticReview(BaseModel):
    status: ReviewStatus = Field(
        description="Whether the reviewed content is approved."
    )
    feedback: str = Field(
        description="Specific guidance when content needs revision."
    )


class CurriculumFile(BaseModel):
    filename: str = Field(description="Filename to save in long-term memory.")
    content: str = Field(description="Full file contents.")
    summary: str = Field(description="Short summary of what the file contains.")


class CurriculumBundle(BaseModel):
    learner_summary: str = Field(
        description="High-level summary of the learner and learning target."
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Key assumptions or caveats that affect the curriculum.",
    )
    files: List[CurriculumFile] = Field(
        description="All files that should be written to long-term memory."
    )


class QuizQuestion(BaseModel):
    question: str = Field(description="Question shown to the learner.")
    options: List[str] = Field(
        min_length=2,
        max_length=5,
        description="Answer choices shown to the learner.",
    )
    correct_option_index: int = Field(
        ge=0,
        description="Zero-based index of the correct option.",
    )
    explanation: str = Field(
        description="Brief explanation shown after the learner checks answers."
    )


class UnitQuiz(BaseModel):
    unit_title: str = Field(description="Title of the unit being assessed.")
    source_file: str = Field(description="Source markdown filename for this unit.")
    questions: List[QuizQuestion] = Field(
        min_length=3,
        description="Questions for this unit.",
    )


class QuizBundle(BaseModel):
    source_session_dir: str = Field(
        description="Curriculum session directory used to build the quiz."
    )
    quiz_title: str = Field(description="Title shown at the top of the quiz page.")
    units: List[UnitQuiz] = Field(
        min_length=1,
        description="One quiz section per selected unit.",
    )
