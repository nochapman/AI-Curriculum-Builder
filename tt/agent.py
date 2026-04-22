import os

from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.tools import google_search

from .callbacks import (
    collect_verified_sources_callback,
    save_curriculum_bundle_callback,
)
from .prompts import (
    CONTENT_GENERATOR_INSTRUCTION,
    CURRICULUM_DIRECTOR_INSTRUCTION,
    CURRICULUM_WRITER_INSTRUCTION,
    INTERVIEW_TRANSCRIPT_INSTRUCTION,
    INTERVIEWER_INSTRUCTION,
    MODULE_CRITIC_INSTRUCTION,
    ROOT_AGENT_INSTRUCTION,
    USER_PROFILE_EXTRACTOR_INSTRUCTION,
)
from .schemas import CurriculumBundle

MODEL = os.getenv("CURRICULUM_MODEL", os.getenv("MODEL", "gemini-2.5-flash"))

interview_transcript_agent = LlmAgent(
    name="interview_transcript_agent",
    model=MODEL,
    description="Builds a concise intake transcript from the learner interview.",
    instruction=INTERVIEW_TRANSCRIPT_INSTRUCTION,
    output_key="interview_transcript",
)


profile_extractor_agent = LlmAgent(
    name="profile_extractor_agent",
    model=MODEL,
    description="Extracts a structured learner profile from the intake transcript.",
    instruction=USER_PROFILE_EXTRACTOR_INSTRUCTION,
    output_key="user_profile_json",
)


curriculum_director_agent = LlmAgent(
    name="curriculum_director_agent",
    model=MODEL,
    description="Builds a structured syllabus from the extracted learner profile.",
    instruction=CURRICULUM_DIRECTOR_INSTRUCTION,
    output_key="syllabus_json",
)


content_generator_agent = LlmAgent(
    name="research_agent",
    model=MODEL,
    description="Researches each syllabus unit and produces a research packet.",
    instruction=CONTENT_GENERATOR_INSTRUCTION,
    tools=[google_search],
    output_key="research_packet",
    after_agent_callback=collect_verified_sources_callback,
)


curriculum_writer_agent = LlmAgent(
    name="curriculum_writer_agent",
    model=MODEL,
    description="Writes a structured curriculum bundle for Python to save to disk.",
    instruction=CURRICULUM_WRITER_INSTRUCTION,
    output_schema=CurriculumBundle,
    output_key="curriculum_bundle",
    after_agent_callback=save_curriculum_bundle_callback,
)


module_critic_agent = LlmAgent(
    name="module_critic_agent",
    model=MODEL,
    description="Reviews the generated curriculum packet for coverage, safety, and clarity.",
    instruction=MODULE_CRITIC_INSTRUCTION,
)


curriculum_generation_agent = SequentialAgent(
    name="curriculum_generation_agent",
    description="Runs the curriculum pipeline after the interview is complete.",
    sub_agents=[
        interview_transcript_agent,
        profile_extractor_agent,
        curriculum_director_agent,
        content_generator_agent,
        curriculum_writer_agent,
        module_critic_agent,
    ],
)


interviewer_agent = Agent(
    name="interviewer_agent",
    model=MODEL,
    description="Interviews the learner, then hands off to curriculum generation.",
    instruction=INTERVIEWER_INSTRUCTION,
    sub_agents=[curriculum_generation_agent],
)


root_agent = Agent(
    name="root_agent",
    model=MODEL,
    description="Routes learners into the intake interview and curriculum workflow.",
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[interviewer_agent],
)
