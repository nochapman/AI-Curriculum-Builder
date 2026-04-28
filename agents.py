import os
from google import genai
from google.genai import types
import time
from google.genai import errors

# Import all our strict data models from schemas.py
from schemas import UserProfile, SyllabusOutline, CriticReview

# Initialize the standard Google GenAI client
# Ensure your GEMINI_API_KEY environment variable is set
from dotenv import load_dotenv, dotenv_values
load_dotenv()

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI")
location = os.getenv("GOOGLE_CLOUD_LOCATION")

client = genai.Client(
    vertexai=use_vertex,
    project=project_id, # Put your actual project ID here
    location=location     # Or whichever region your project uses
)

# ==========================================
# Tool Definition (File I/O for Long-Term Memory)
# ==========================================
def save_module_to_disk(filename: str, content: str) -> str:
    """Saves the finalized educational module to the local file system."""
    os.makedirs("long_term_memory", exist_ok=True)
    filepath = os.path.join("long_term_memory", filename)
    with open(filepath, "w") as f:
        f.write(content)
    return f"Successfully saved to {filepath}"


# ==========================================
# Agent Definitions
# ==========================================

def run_interviewer_chat() -> str:
    """Runs the interactive terminal chat and returns the full transcript."""
    
    system_instruction = """
    You are the Intake Interviewer for an AI tutoring system. 
    Your goal is to figure out exactly what the user wants to learn and what their current skill level is.
    Ask one question at a time. Keep it brief.
    
    CRITICAL GUARDRAIL: You must refuse to help with any harmful, illegal, or dangerous goals. If a user asks for this, inform them the system cannot support their request.
    
    When you feel you have enough information to design a curriculum, tell the user type 'DONE'.
    """
    
    chat = client.chats.create(
        model="gemini-2.5-flash", 
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7
        )
    )

    print("Interviewer: Hello! What are you hoping to learn or build today?")
    transcript = "Interviewer: Hello! What are you hoping to learn or build today?\n"
    
    while True:
        user_input = input("You: ")
        transcript += f"User: {user_input}\n"
        
        if user_input.strip().upper() == 'DONE':
            print("Interviewer: Great, wrapping up your profile now...")
            break
            
        response = chat.send_message(user_input)
        print(f"Interviewer: {response.text}")
        transcript += f"Interviewer: {response.text}\n"
        
    return transcript

def extract_user_profile(transcript: str) -> UserProfile:
    """Takes the chat transcript and forces the LLM to output the strict JSON schema."""
    
    extraction_prompt = f"""
    Analyze the following interview transcript and extract the user's profile.
    Pay close attention to the goal_archetype:
    - Use 'THEORETICAL' if they want to learn an academic concept (e.g., calculus, history).
    - Use 'PRACTICAL_PROJECT' if they want to build, configure, or repair something physical or digital.
    
    Transcript:
    {transcript}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents=extraction_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=UserProfile,
            temperature=0.1 
        ),
    )
    
    return UserProfile.model_validate_json(response.text)


def run_curriculum_director(user_profile: UserProfile) -> SyllabusOutline:
    """PLANNER: Decomposes the user's goal into discrete units."""
    
    prompt = f"""
    Analyze this User Profile:
    Goal: {user_profile.target_goal}
    Current Knowledge: {user_profile.assessed_knowledge}
    Archetype: {user_profile.goal_archetype}
    
    Create a logical, step-by-step syllabus. 
    If the archetype is PRACTICAL_PROJECT (e.g., flashing DFU firmware, building a physical circuit), prioritize HANDS_ON_TUTORIALs and actionable PROJECT_MILESTONEs. 
    If THEORETICAL, rely on CONCEPT_LECTUREs.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SyllabusOutline,
            temperature=0.2
        ),
    )
    return SyllabusOutline.model_validate_json(response.text)


def run_researcher(learning_objective: str) -> str:
    """WORKER 1: Gathers real-world context using the Web Search Tool."""
    
    prompt = f"""
    Research the following educational objective: "{learning_objective}"
    You MUST use the Google Search tool to find accurate information. 
    Return a dense summary of the concepts.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}], 
            temperature=0.1
        )
    )
    return response.text


def run_content_generator(unit_title: str, objective: str, research: str, previous_feedback: str = "") -> str:
    """WORKER 2: Drafts the content and uses File I/O to save if approved."""
    
    prompt = f"""
    Write a comprehensive educational module for the topic: {unit_title}.
    Objective: {objective}
    Source Material: {research}
    
    Critique to address (if any): {previous_feedback}
    
    Format the output in clean Markdown. Do not include any URLs or web links in the module content.
    """
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[save_module_to_disk],
                    temperature=0.4
                )
            )
            return response.text
            
        except errors.ServerError as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10  # Waits 10s, then 20s
                print(f"\n  [System] API busy (503). Retrying in {wait_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                print("\n  [System] API failed after 3 retries.")
                raise e # If it fails 3 times, let it crash so you can investigate


def run_module_critic(draft_content: str, objective: str) -> CriticReview:
    """VERIFIER: Checks constraints and triggers retries."""
    
    prompt = f"""
    Review this educational module draft.
    Objective it must meet: {objective}
    
    Draft Content:
    {draft_content}
    
    Does this clearly and safely teach the objective? 
    If yes, output APPROVED.
    If no, output REJECTED and provide specific instructions on what the Content Generator must fix.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CriticReview,
            temperature=0.1
        ),
    )
    return CriticReview.model_validate_json(response.text)