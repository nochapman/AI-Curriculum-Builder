# Usage Report

- Generated at: 2026-04-28T21:43:55.844885+00:00
- Source log: /Users/bumsookim/Downloads/DEEP LEARNING/project/AI-Curriculum-Builder/tt/logs/tool_calls.jsonl
- Model usage log: /Users/bumsookim/Downloads/DEEP LEARNING/project/AI-Curriculum-Builder/tt/logs/model_usage.jsonl
- ADK session DB: /Users/bumsookim/Downloads/DEEP LEARNING/project/AI-Curriculum-Builder/tt/.adk/session.db

## Actual Model Token Usage
- Model calls: 417
- Prompt/input tokens: 3095120
- Candidate/output tokens: 546526
- Thoughts tokens: 208622
- Cached content tokens: 477883
- Total tokens: 3851818
- Average prompt/input tokens: 7422.35
- Average candidate/output tokens: 1310.61
- Average total tokens: 9236.97
- Total cost USD estimate: None
- Average cost USD estimate: None

## Tool Log Summary
- Tool calls: 320
- Success rate: 0.9688
- Average latency ms: 975.52
- Total input tokens estimate: 14891
- Total output tokens estimate: 12179
- Total tokens estimate: 27070
- Average input tokens estimate: 46.53
- Average output tokens estimate: 38.06
- Average total tokens estimate: 84.59
- Total cost USD estimate: None
- Average cost USD estimate: None
- Cost note: Cost is estimated only when CURRICULUM_INPUT_COST_PER_1M_TOKENS and CURRICULUM_OUTPUT_COST_PER_1M_TOKENS are set.

## Error Categories
- TimeoutError: 1
- http_error: 2
- no_grounding_metadata: 2
- soft_404: 2
- unverified_url: 3

## Actual Model Usage By Agent
### course_page_generator_agent
- Calls: 8
- Prompt/input tokens: 86412
- Candidate/output tokens: 2722
- Total tokens: 90154
- Average total tokens: 11269.25
- Average cost USD estimate: None

### course_page_report_agent
- Calls: 3
- Prompt/input tokens: 41474
- Candidate/output tokens: 178
- Total tokens: 41928
- Average total tokens: 13976.0
- Average cost USD estimate: None

### curriculum_director_agent
- Calls: 27
- Prompt/input tokens: 91888
- Candidate/output tokens: 29626
- Total tokens: 143370
- Average total tokens: 5310.0
- Average cost USD estimate: None

### curriculum_writer_agent
- Calls: 29
- Prompt/input tokens: 822293
- Candidate/output tokens: 231191
- Total tokens: 1160280
- Average total tokens: 40009.66
- Average cost USD estimate: None

### dashboard_manager_agent
- Calls: 4
- Prompt/input tokens: 3962
- Candidate/output tokens: 108
- Total tokens: 4234
- Average total tokens: 1058.5
- Average cost USD estimate: None

### interview_transcript_agent
- Calls: 21
- Prompt/input tokens: 58740
- Candidate/output tokens: 1697
- Total tokens: 63695
- Average total tokens: 3033.1
- Average cost USD estimate: None

### interviewer_agent
- Calls: 137
- Prompt/input tokens: 469354
- Candidate/output tokens: 5279
- Total tokens: 486051
- Average total tokens: 3547.82
- Average cost USD estimate: None

### module_critic_agent
- Calls: 21
- Prompt/input tokens: 552091
- Candidate/output tokens: 12945
- Total tokens: 583024
- Average total tokens: 27763.05
- Average cost USD estimate: None

### profile_extractor_agent
- Calls: 28
- Prompt/input tokens: 65893
- Candidate/output tokens: 13388
- Total tokens: 84219
- Average total tokens: 3007.82
- Average cost USD estimate: None

### quiz_generator_agent
- Calls: 2
- Prompt/input tokens: 106395
- Candidate/output tokens: 5258
- Total tokens: 111802
- Average total tokens: 55901.0
- Average cost USD estimate: None

### quiz_report_agent
- Calls: 1
- Prompt/input tokens: 64516
- Candidate/output tokens: 78
- Total tokens: 64631
- Average total tokens: 64631.0
- Average cost USD estimate: None

### research_agent
- Calls: 23
- Prompt/input tokens: 155135
- Candidate/output tokens: 225072
- Total tokens: 404571
- Average total tokens: 17590.04
- Average cost USD estimate: None

### root_agent
- Calls: 95
- Prompt/input tokens: 170371
- Candidate/output tokens: 18720
- Total tokens: 205264
- Average total tokens: 2160.67
- Average cost USD estimate: None

### usage_report_agent
- Calls: 18
- Prompt/input tokens: 406596
- Candidate/output tokens: 264
- Total tokens: 408595
- Average total tokens: 22699.72
- Average cost USD estimate: None


## By Tool
### auto_report_smoke_test
- Calls: 1
- Successes: 1
- Failures: 0
- Average latency ms: 2.5
- Average total tokens estimate: 9.0
- Average cost USD estimate: None

### file_io.load_curriculum_units_for_course_page
- Calls: 3
- Successes: 3
- Failures: 0
- Average latency ms: 1.91
- Average total tokens estimate: 39.0
- Average cost USD estimate: None

### file_io.load_curriculum_units_for_quiz
- Calls: 6
- Successes: 6
- Failures: 0
- Average latency ms: 2.46
- Average total tokens estimate: 43.0
- Average cost USD estimate: None

### file_io.refresh_canvas_dashboard
- Calls: 5
- Successes: 5
- Failures: 0
- Average latency ms: 28.69
- Average total tokens estimate: 22.0
- Average cost USD estimate: None

### file_io.save_text_file
- Calls: 89
- Successes: 89
- Failures: 0
- Average latency ms: 0.36
- Average total tokens estimate: 63.39
- Average cost USD estimate: None

### google_search
- Calls: 11
- Successes: 9
- Failures: 2
- Average latency ms: 13460.99
- Average total tokens estimate: 197.36
- Average cost USD estimate: None

### guardrail_check
- Calls: 11
- Successes: 11
- Failures: 0
- Average latency ms: None
- Average total tokens estimate: 56.27
- Average cost USD estimate: None

### logger_smoke_test
- Calls: 1
- Successes: 1
- Failures: 0
- Average latency ms: 1.23
- Average total tokens estimate: 8.0
- Average cost USD estimate: None

### source_integrity_check
- Calls: 7
- Successes: 4
- Failures: 3
- Average latency ms: None
- Average total tokens estimate: 581.86
- Average cost USD estimate: None

### usage_report.refresh
- Calls: 7
- Successes: 7
- Failures: 0
- Average latency ms: 8.55
- Average total tokens estimate: 58.0
- Average cost USD estimate: None

### web.url_validation
- Calls: 179
- Successes: 174
- Failures: 5
- Average latency ms: 817.19
- Average total tokens estimate: 76.3
- Average cost USD estimate: None
