import os
from agents import (
    run_interviewer_chat,
    extract_user_profile,
    run_curriculum_director,
    run_researcher,
    run_content_generator,
    run_module_critic
)

def main():
    print("==================================================")
    print("        Agentic Tutor - Execution Pipeline        ")
    print("==================================================\n")

    # ---------------------------------------------------------
    # Phase 1: Interview & Assessment
    # ---------------------------------------------------------
    print("--- Initiating Phase 1: Assessment ---")
    transcript = run_interviewer_chat()
    
    print("\n--- Extracting User Profile ---")
    user_profile = extract_user_profile(transcript)
    print(f"Goal Archetype Identified: {user_profile.goal_archetype}")
    print(f"Target Goal: {user_profile.target_goal}")

    # ---------------------------------------------------------
    # Phase 2: Curriculum Planning
    # ---------------------------------------------------------
    print("\n--- Initiating Phase 2: Curriculum Planning ---")
    print("Curriculum Director is designing the syllabus...")
    syllabus = run_curriculum_director(user_profile)
    
    print(f"\nGenerated Syllabus ({len(syllabus.units)} units):")
    for unit in syllabus.units:
        print(f"  {unit.unit_order}. {unit.title} [{unit.module_type}]")

    # ---------------------------------------------------------
    # Phase 3: The Iterative Generation Loop
    # ---------------------------------------------------------
    print("\n--- Initiating Phase 3: Content Generation & Review ---")
    for unit in syllabus.units:
        print(f"\n>>> Starting Unit {unit.unit_order}: {unit.title}")
        
        # 1. Research
        print("  [Researcher] Gathering materials from the web...")
        research_data = run_researcher(unit.learning_objective)
        print("  [Researcher] Context gathered.")

        # 2. Draft & Review Loop
        feedback = ""
        max_revisions = 3
        approved = False
        final_draft = ""

        for attempt in range(max_revisions):
            print(f"  [Content Generator] Drafting module (Attempt {attempt + 1}/{max_revisions})...")
            draft = run_content_generator(
                unit_title=unit.title, 
                objective=unit.learning_objective, 
                research=research_data, 
                previous_feedback=feedback
            )
            
            # The Content Generator returns the text, but might also trigger the file save tool.
            final_draft = draft 

            print("  [Module Critic] Reviewing draft...")
            review = run_module_critic(draft_content=draft, objective=unit.learning_objective)

            if review.status == "APPROVED":
                print("  [Module Critic] Status: APPROVED!")
                approved = True
                break
            else:
                print(f"  [Module Critic] Status: REJECTED.")
                print(f"  [Module Critic] Feedback: {review.feedback}")
                feedback = review.feedback # Pass this feedback into the next loop
        
        if not approved:
            print("  [System] Warning: Max revisions reached. Proceeding with the latest draft.")

        # 3. Memory Fallback
        # The Content Generator has the tool to save to disk natively, but LLMs can occasionally forget to call tools.
        # This fallback ensures your long-term memory requirement is met 100% of the time.
        safe_title = unit.title.replace(" ", "_").replace("/", "-").lower()
        fallback_filename = f"unit_{unit.unit_order}_{safe_title}.md"
        filepath = os.path.join("long_term_memory", fallback_filename)
        
        if not os.path.exists(filepath):
            os.makedirs("long_term_memory", exist_ok=True)
            with open(filepath, "w") as f:
                f.write(final_draft)
            print(f"  [System] Module securely saved to {filepath}")

    print("\n==================================================")
    print("          Course Generation Complete!             ")
    print("==================================================")

if __name__ == "__main__":
    main()