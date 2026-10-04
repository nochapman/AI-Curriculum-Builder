# Usage Report

- Generated at: 2026-04-29T22:58:22.779986+00:00
- Source log: /Users/bumsookim/Downloads/DEEP LEARNING/project/AI-Curriculum-Builder/tt/logs/tool_calls.jsonl
- Model usage log: /Users/bumsookim/Downloads/DEEP LEARNING/project/AI-Curriculum-Builder/tt/logs/model_usage.jsonl
- ADK session DB: /Users/bumsookim/Downloads/DEEP LEARNING/project/AI-Curriculum-Builder/tt/.adk/session.db

## Actual Model Token Usage
- Model calls: 812
- Prompt/input tokens: 6718713
- Candidate/output tokens: 1000177
- Thoughts tokens: 353704
- Cached content tokens: 845505
- Total tokens: 8087053
- Average prompt/input tokens: 8274.28
- Average candidate/output tokens: 1231.75
- Average total tokens: 9959.42
- Total cost USD estimate: None
- Average cost USD estimate: None

## Tool Log Summary
- Tool calls: 667
- Success rate: 0.9745
- Average latency ms: 1035.85
- Total input tokens estimate: 28735
- Total output tokens estimate: 22115
- Total tokens estimate: 50850
- Average input tokens estimate: 43.08
- Average output tokens estimate: 33.16
- Average total tokens estimate: 76.24
- Total cost USD estimate: None
- Average cost USD estimate: None
- Cost note: Cost is estimated only when CURRICULUM_INPUT_COST_PER_1M_TOKENS and CURRICULUM_OUTPUT_COST_PER_1M_TOKENS are set.

## Error Categories
- TimeoutError: 1
- file_io_error: 1
- http_error: 7
- no_grounding_metadata: 3
- soft_404: 2
- unverified_url: 3

## Actual Model Usage By Agent
### course_page_generator_agent
- Calls: 12
- Prompt/input tokens: 109314
- Candidate/output tokens: 4292
- Total tokens: 116416
- Average total tokens: 9701.33
- Average cost USD estimate: None

### course_page_report_agent
- Calls: 7
- Prompt/input tokens: 83572
- Candidate/output tokens: 404
- Total tokens: 85224
- Average total tokens: 12174.86
- Average cost USD estimate: None

### curriculum_director_agent
- Calls: 55
- Prompt/input tokens: 118208
- Candidate/output tokens: 44791
- Total tokens: 199317
- Average total tokens: 3623.95
- Average cost USD estimate: None

### curriculum_reviewer_agent
- Calls: 6
- Prompt/input tokens: 137772
- Candidate/output tokens: 52482
- Total tokens: 198612
- Average total tokens: 33102.0
- Average cost USD estimate: None

### curriculum_writer_agent
- Calls: 51
- Prompt/input tokens: 1161871
- Candidate/output tokens: 387070
- Total tokens: 1704010
- Average total tokens: 33411.96
- Average cost USD estimate: None

### dashboard_manager_agent
- Calls: 22
- Prompt/input tokens: 26521
- Candidate/output tokens: 520
- Total tokens: 28298
- Average total tokens: 1286.27
- Average cost USD estimate: None

### interview_transcript_agent
- Calls: 26
- Prompt/input tokens: 63514
- Candidate/output tokens: 2257
- Total tokens: 69725
- Average total tokens: 2681.73
- Average cost USD estimate: None

### interviewer_agent
- Calls: 303
- Prompt/input tokens: 1122718
- Candidate/output tokens: 13325
- Total tokens: 1162956
- Average total tokens: 3838.14
- Average cost USD estimate: None

### module_critic_agent
- Calls: 35
- Prompt/input tokens: 821108
- Candidate/output tokens: 19800
- Total tokens: 862106
- Average total tokens: 24631.6
- Average cost USD estimate: None

### pipeline_course_page_generator_agent
- Calls: 10
- Prompt/input tokens: 337516
- Candidate/output tokens: 2306
- Total tokens: 344128
- Average total tokens: 34412.8
- Average cost USD estimate: None

### pipeline_course_page_report_agent
- Calls: 6
- Prompt/input tokens: 192574
- Candidate/output tokens: 378
- Total tokens: 193558
- Average total tokens: 32259.67
- Average cost USD estimate: None

### pipeline_quiz_generator_agent
- Calls: 10
- Prompt/input tokens: 439890
- Candidate/output tokens: 18516
- Total tokens: 460738
- Average total tokens: 46073.8
- Average cost USD estimate: None

### pipeline_quiz_report_agent
- Calls: 6
- Prompt/input tokens: 262652
- Candidate/output tokens: 392
- Total tokens: 264028
- Average total tokens: 44004.67
- Average cost USD estimate: None

### profile_extractor_agent
- Calls: 33
- Prompt/input tokens: 72112
- Candidate/output tokens: 13770
- Total tokens: 91816
- Average total tokens: 2782.3
- Average cost USD estimate: None

### quiz_generator_agent
- Calls: 14
- Prompt/input tokens: 232747
- Candidate/output tokens: 28933
- Total tokens: 273328
- Average total tokens: 19523.43
- Average cost USD estimate: None

### quiz_report_agent
- Calls: 4
- Prompt/input tokens: 120819
- Candidate/output tokens: 247
- Total tokens: 121198
- Average total tokens: 30299.5
- Average cost USD estimate: None

### research_agent
- Calls: 50
- Prompt/input tokens: 217866
- Candidate/output tokens: 390115
- Total tokens: 670806
- Average total tokens: 13416.12
- Average cost USD estimate: None

### root_agent
- Calls: 135
- Prompt/input tokens: 266652
- Candidate/output tokens: 20180
- Total tokens: 307220
- Average total tokens: 2275.7
- Average cost USD estimate: None

### test_logger
- Calls: 1
- Prompt/input tokens: 1
- Candidate/output tokens: 1
- Total tokens: 0
- Average total tokens: 0.0
- Average cost USD estimate: None

### usage_report_agent
- Calls: 26
- Prompt/input tokens: 931286
- Candidate/output tokens: 398
- Total tokens: 933569
- Average total tokens: 35906.5
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
- Calls: 6
- Successes: 6
- Failures: 0
- Average latency ms: 1.77
- Average total tokens estimate: 39.0
- Average cost USD estimate: None

### file_io.load_curriculum_units_for_quiz
- Calls: 14
- Successes: 13
- Failures: 1
- Average latency ms: 1.82
- Average total tokens estimate: 48.79
- Average cost USD estimate: None

### file_io.refresh_canvas_dashboard
- Calls: 41
- Successes: 41
- Failures: 0
- Average latency ms: 42.64
- Average total tokens estimate: 22.0
- Average cost USD estimate: None

### file_io.save_text_file
- Calls: 172
- Successes: 172
- Failures: 0
- Average latency ms: 0.43
- Average total tokens estimate: 63.78
- Average cost USD estimate: None

### google_search
- Calls: 17
- Successes: 14
- Failures: 3
- Average latency ms: 19249.85
- Average total tokens estimate: 199.65
- Average cost USD estimate: None

### guardrail_check
- Calls: 27
- Successes: 27
- Failures: 0
- Average latency ms: None
- Average total tokens estimate: 44.96
- Average cost USD estimate: None

### logger_smoke_test
- Calls: 1
- Successes: 1
- Failures: 0
- Average latency ms: 1.23
- Average total tokens estimate: 8.0
- Average cost USD estimate: None

### source_integrity_check
- Calls: 14
- Successes: 11
- Failures: 3
- Average latency ms: None
- Average total tokens estimate: 387.79
- Average cost USD estimate: None

### state.store_learner_profile
- Calls: 11
- Successes: 11
- Failures: 0
- Average latency ms: 0.03
- Average total tokens estimate: 45.27
- Average cost USD estimate: None

### usage_report.refresh
- Calls: 9
- Successes: 9
- Failures: 0
- Average latency ms: 27.2
- Average total tokens estimate: 58.0
- Average cost USD estimate: None

### web.url_validation
- Calls: 354
- Successes: 344
- Failures: 10
- Average latency ms: 901.37
- Average total tokens estimate: 76.23
- Average cost USD estimate: None
