import os

from .compat import patch_aiohttp_connector_dns_error

patch_aiohttp_connector_dns_error()

from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.tools import google_search
from google.genai import types

from .callbacks import (
    collect_verified_sources_callback,
    log_model_usage_callback,
    save_curriculum_bundle_callback,
    save_quiz_bundle_callback,
)
from .prompts import (
    CONTENT_GENERATOR_INSTRUCTION,
    CURRICULUM_DIRECTOR_INSTRUCTION,
    CURRICULUM_WRITER_INSTRUCTION,
    INTERVIEW_TRANSCRIPT_INSTRUCTION,
    INTERVIEWER_INSTRUCTION,
    MODULE_CRITIC_INSTRUCTION,
    QUIZ_GENERATOR_INSTRUCTION,
    QUIZ_REPORT_INSTRUCTION,
    ROOT_AGENT_INSTRUCTION,
    USAGE_REPORT_INSTRUCTION,
    USER_PROFILE_EXTRACTOR_INSTRUCTION,
)
from .schemas import CurriculumBundle, QuizBundle
from .tools import load_curriculum_units_for_quiz, refresh_usage_report_tool

MODEL = os.getenv("CURRICULUM_MODEL", os.getenv("MODEL", "gemini-2.5-flash"))
RETRY_INITIAL_DELAY_SECS = int(os.getenv("CURRICULUM_RETRY_INITIAL_DELAY_SECS", "1"))
RETRY_ATTEMPTS = int(os.getenv("CURRICULUM_RETRY_ATTEMPTS", "3"))

RETRY_GENERATE_CONTENT_CONFIG = types.GenerateContentConfig(
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            initial_delay=RETRY_INITIAL_DELAY_SECS,
            attempts=RETRY_ATTEMPTS,
        )
    )
)

interview_transcript_agent = LlmAgent(
    name="interview_transcript_agent",
    model=MODEL,
    description="Builds a concise intake transcript from the learner interview.",
    instruction=INTERVIEW_TRANSCRIPT_INSTRUCTION,
    output_key="interview_transcript",
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


profile_extractor_agent = LlmAgent(
    name="profile_extractor_agent",
    model=MODEL,
    description="Extracts a structured learner profile from the intake transcript.",
    instruction=USER_PROFILE_EXTRACTOR_INSTRUCTION,
    output_key="user_profile_json",
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


curriculum_director_agent = LlmAgent(
    name="curriculum_director_agent",
    model=MODEL,
    description="Builds a structured syllabus from the extracted learner profile.",
    instruction=CURRICULUM_DIRECTOR_INSTRUCTION,
    output_key="syllabus_json",
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


content_generator_agent = LlmAgent(
    name="research_agent",
    model=MODEL,
    description="Researches each syllabus unit and produces a research packet.",
    instruction=CONTENT_GENERATOR_INSTRUCTION,
    tools=[google_search],
    output_key="research_packet",
    after_model_callback=log_model_usage_callback,
    after_agent_callback=collect_verified_sources_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


curriculum_writer_agent = LlmAgent(
    name="curriculum_writer_agent",
    model=MODEL,
    description="Writes a structured curriculum bundle for Python to save to disk.",
    instruction=CURRICULUM_WRITER_INSTRUCTION,
    output_schema=CurriculumBundle,
    output_key="curriculum_bundle",
    after_model_callback=log_model_usage_callback,
    after_agent_callback=save_curriculum_bundle_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


module_critic_agent = LlmAgent(
    name="module_critic_agent",
    model=MODEL,
    description="Reviews the generated curriculum packet for coverage, safety, and clarity.",
    instruction=MODULE_CRITIC_INSTRUCTION,
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


quiz_generator_agent = LlmAgent(
    name="quiz_generator_agent",
    model=MODEL,
    description="Reads saved unit lessons and creates a structured quiz bundle.",
    instruction=QUIZ_GENERATOR_INSTRUCTION,
    tools=[load_curriculum_units_for_quiz],
    output_schema=QuizBundle,
    output_key="quiz_bundle",
    after_model_callback=log_model_usage_callback,
    after_agent_callback=save_quiz_bundle_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


quiz_report_agent = LlmAgent(
    name="quiz_report_agent",
    model=MODEL,
    description="Reports where the generated HTML quiz was saved.",
    instruction=QUIZ_REPORT_INSTRUCTION,
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


quiz_agent = SequentialAgent(
    name="quiz_agent",
    description="Generates an interactive HTML quiz from saved unit lesson files.",
    sub_agents=[
        quiz_generator_agent,
        quiz_report_agent,
    ],
)


usage_report_agent = LlmAgent(
    name="usage_report_agent",
    model=MODEL,
    description="Refreshes usage report files from the tool-call log.",
    instruction=USAGE_REPORT_INSTRUCTION,
    tools=[refresh_usage_report_tool],
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
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
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


root_agent = Agent(
    name="root_agent",
    model=MODEL,
    description="Routes learners into the intake interview and curriculum workflow.",
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[usage_report_agent, quiz_agent, interviewer_agent],
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)
