import os

from .compat import patch_aiohttp_connector_dns_error

patch_aiohttp_connector_dns_error()

from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.tools import AgentTool, google_search
from google.genai import types

from .callbacks import (
    log_model_usage_callback,
    save_course_page_bundle_callback,
    save_curriculum_bundle_callback,
    save_quiz_bundle_callback,
)
from .prompts import (
    CONTENT_GENERATOR_INSTRUCTION,
    COURSE_PAGE_GENERATOR_INSTRUCTION,
    COURSE_PAGE_REPORT_INSTRUCTION,
    CURRICULUM_DIRECTOR_INSTRUCTION,
    CURRICULUM_WRITER_INSTRUCTION,
    DASHBOARD_MANAGER_INSTRUCTION,
    INTERVIEWER_INSTRUCTION,
    MODULE_CRITIC_INSTRUCTION,
    QUIZ_GENERATOR_INSTRUCTION,
    QUIZ_REPORT_INSTRUCTION,
    ROOT_AGENT_INSTRUCTION,
    USAGE_REPORT_INSTRUCTION,
)
from .schemas import CoursePageBundle, CurriculumBundle, QuizBundle
from .tools import (
    load_curriculum_units_for_course_page,
    load_curriculum_units_for_quiz,
    refresh_canvas_dashboard_tool,
    refresh_usage_report_tool,
    store_learner_profile,
)

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


module_critic_agent = LlmAgent(
    name="module_critic_agent",
    model=MODEL,
    description="Reviews the generated curriculum packet for coverage, safety, and clarity.",
    instruction=MODULE_CRITIC_INSTRUCTION,
    tools=[AgentTool(quiz_generator_agent)],
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


course_page_generator_agent = LlmAgent(
    name="course_page_generator_agent",
    model=MODEL,
    description="Reads saved unit lessons and creates a structured course page bundle.",
    instruction=COURSE_PAGE_GENERATOR_INSTRUCTION,
    tools=[load_curriculum_units_for_course_page],
    output_schema=CoursePageBundle,
    output_key="course_page_bundle",
    after_model_callback=log_model_usage_callback,
    after_agent_callback=save_course_page_bundle_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


course_page_report_agent = LlmAgent(
    name="course_page_report_agent",
    model=MODEL,
    description="Reports where the generated HTML course page was saved.",
    instruction=COURSE_PAGE_REPORT_INSTRUCTION,
    tools=[AgentTool(quiz_generator_agent)],
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


course_page_agent = SequentialAgent(
    name="course_page_agent",
    description="Generates a Canvas-style HTML course page and linked quiz from saved unit lesson files.",
    sub_agents=[
        course_page_generator_agent,
        course_page_report_agent,
    ],
)


dashboard_manager_agent = LlmAgent(
    name="dashboard_manager_agent",
    model=MODEL,
    description="Maintains the Canvas-style dashboard that links all saved courses.",
    instruction=DASHBOARD_MANAGER_INSTRUCTION,
    tools=[refresh_canvas_dashboard_tool],
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
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
        curriculum_director_agent,
        content_generator_agent,
        curriculum_writer_agent,
        module_critic_agent,
    ],
)


interviewer_agent = Agent(
    name="interviewer_agent",
    model=MODEL,
    description="Interviews the learner, stores the learner profile, then hands off to curriculum generation.",
    instruction=INTERVIEWER_INSTRUCTION,
    tools=[store_learner_profile],
    sub_agents=[curriculum_generation_agent],
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)


root_agent = Agent(
    name="root_agent",
    model=MODEL,
    description="Routes learners into the intake interview and curriculum workflow.",
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[
        dashboard_manager_agent,
        course_page_agent,
        usage_report_agent,
        quiz_agent,
        interviewer_agent,
    ],
    after_model_callback=log_model_usage_callback,
    generate_content_config=RETRY_GENERATE_CONTENT_CONFIG,
)
