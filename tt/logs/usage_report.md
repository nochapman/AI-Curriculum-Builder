# Usage Report

- Generated at: 2026-04-28T22:52:50.863091+00:00
- Source log: C:\React\rep\AI-Curriculum-Builder\tt\logs\tool_calls.jsonl
- Model usage log: C:\React\rep\AI-Curriculum-Builder\tt\logs\model_usage.jsonl
- ADK session DB: C:\React\rep\AI-Curriculum-Builder\tt\.adk\session.db

## Actual Model Token Usage
- Model calls: 553
- Prompt/input tokens: 4187339
- Candidate/output tokens: 733097
- Thoughts tokens: 270403
- Cached content tokens: 647940
- Total tokens: 5200503
- Average prompt/input tokens: 7572.04
- Average candidate/output tokens: 1325.67
- Average total tokens: 9404.16
- Total cost USD estimate: None
- Average cost USD estimate: None

## Tool Log Summary
- Tool calls: 248
- Success rate: 0.9637
- Average latency ms: 1264.77
- Total input tokens estimate: 11827
- Total output tokens estimate: 6859
- Total tokens estimate: 18686
- Average input tokens estimate: 47.69
- Average output tokens estimate: 27.66
- Average total tokens estimate: 75.35
- Total cost USD estimate: None
- Average cost USD estimate: None
- Cost note: Cost is estimated only when CURRICULUM_INPUT_COST_PER_1M_TOKENS and CURRICULUM_OUTPUT_COST_PER_1M_TOKENS are set.

## Error Categories
- TimeoutError: 2
- http_error: 2
- no_grounding_metadata: 2
- soft_404: 3

## Actual Model Usage By Agent
### course_page_generator_agent
- Calls: 3
- Prompt/input tokens: 43206
- Candidate/output tokens: 1361
- Total tokens: 45077
- Average total tokens: 15025.67
- Average cost USD estimate: None

### course_page_report_agent
- Calls: 1
- Prompt/input tokens: 20737
- Candidate/output tokens: 89
- Total tokens: 20964
- Average total tokens: 20964.0
- Average cost USD estimate: None

### curriculum_director_agent
- Calls: 36
- Prompt/input tokens: 130920
- Candidate/output tokens: 37832
- Total tokens: 197205
- Average total tokens: 5477.92
- Average cost USD estimate: None

### curriculum_writer_agent
- Calls: 38
- Prompt/input tokens: 1095860
- Candidate/output tokens: 309366
- Total tokens: 1532907
- Average total tokens: 40339.66
- Average cost USD estimate: None

### dashboard_manager_agent
- Calls: 6
- Prompt/input tokens: 5341
- Candidate/output tokens: 158
- Total tokens: 5811
- Average total tokens: 968.5
- Average cost USD estimate: None

### interview_transcript_agent
- Calls: 30
- Prompt/input tokens: 93289
- Candidate/output tokens: 2891
- Total tokens: 101038
- Average total tokens: 3367.93
- Average cost USD estimate: None

### interviewer_agent
- Calls: 208
- Prompt/input tokens: 751027
- Candidate/output tokens: 12246
- Total tokens: 785127
- Average total tokens: 3774.65
- Average cost USD estimate: None

### module_critic_agent
- Calls: 27
- Prompt/input tokens: 703930
- Candidate/output tokens: 18104
- Total tokens: 744821
- Average total tokens: 27585.96
- Average cost USD estimate: None

### profile_extractor_agent
- Calls: 37
- Prompt/input tokens: 103480
- Candidate/output tokens: 14179
- Total tokens: 124879
- Average total tokens: 3375.11
- Average cost USD estimate: None

### quiz_generator_agent
- Calls: 6
- Prompt/input tokens: 207205
- Candidate/output tokens: 15914
- Total tokens: 224406
- Average total tokens: 37401.0
- Average cost USD estimate: None

### quiz_report_agent
- Calls: 3
- Prompt/input tokens: 131272
- Candidate/output tokens: 244
- Total tokens: 131641
- Average total tokens: 43880.33
- Average cost USD estimate: None

### research_agent
- Calls: 32
- Prompt/input tokens: 210750
- Candidate/output tokens: 299620
- Total tokens: 556590
- Average total tokens: 17393.44
- Average cost USD estimate: None

### root_agent
- Calls: 112
- Prompt/input tokens: 340828
- Candidate/output tokens: 20873
- Total tokens: 379301
- Average total tokens: 3386.62
- Average cost USD estimate: None

### usage_report_agent
- Calls: 14
- Prompt/input tokens: 349494
- Candidate/output tokens: 220
- Total tokens: 350736
- Average total tokens: 25052.57
- Average cost USD estimate: None


## By Tool
### file_io.load_curriculum_units_for_quiz
- Calls: 1
- Successes: 1
- Failures: 0
- Average latency ms: 6.21
- Average total tokens estimate: 62.0
- Average cost USD estimate: None

### file_io.refresh_canvas_dashboard
- Calls: 6
- Successes: 6
- Failures: 0
- Average latency ms: 95.08
- Average total tokens estimate: 22.0
- Average cost USD estimate: None

### file_io.save_text_file
- Calls: 76
- Successes: 76
- Failures: 0
- Average latency ms: 1.83
- Average total tokens estimate: 54.41
- Average cost USD estimate: None

### google_search
- Calls: 7
- Successes: 5
- Failures: 2
- Average latency ms: 21548.48
- Average total tokens estimate: 215.0
- Average cost USD estimate: None

### guardrail_check
- Calls: 8
- Successes: 8
- Failures: 0
- Average latency ms: None
- Average total tokens estimate: 76.5
- Average cost USD estimate: None

### source_integrity_check
- Calls: 7
- Successes: 7
- Failures: 0
- Average latency ms: None
- Average total tokens estimate: 175.14
- Average cost USD estimate: None

### web.url_validation
- Calls: 143
- Successes: 136
- Failures: 7
- Average latency ms: 1000.94
- Average total tokens estimate: 77.02
- Average cost USD estimate: None
