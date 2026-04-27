# Usage Report

- Generated at: 2026-04-27T22:28:17.471473+00:00
- Source log: /Users/bumsookim/Downloads/DEEP LEARNING/project/AI-Curriculum-Builder/tt/logs/tool_calls.jsonl
- Model usage log: /Users/bumsookim/Downloads/DEEP LEARNING/project/AI-Curriculum-Builder/tt/logs/model_usage.jsonl
- ADK session DB: /Users/bumsookim/Downloads/DEEP LEARNING/project/AI-Curriculum-Builder/tt/.adk/session.db

## Actual Model Token Usage
- Model calls: 348
- Prompt/input tokens: 2764304
- Candidate/output tokens: 511272
- Thoughts tokens: 187946
- Cached content tokens: 451734
- Total tokens: 3465072
- Average prompt/input tokens: 7943.4
- Average candidate/output tokens: 1469.17
- Average total tokens: 9957.1
- Total cost USD estimate: None
- Average cost USD estimate: None

## Tool Log Summary
- Tool calls: 285
- Success rate: 0.9649
- Average latency ms: 1007.28
- Total input tokens estimate: 13677
- Total output tokens estimate: 10858
- Total tokens estimate: 24535
- Average input tokens estimate: 47.99
- Average output tokens estimate: 38.1
- Average total tokens estimate: 86.09
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
### curriculum_director_agent
- Calls: 24
- Prompt/input tokens: 88994
- Candidate/output tokens: 28576
- Total tokens: 137674
- Average total tokens: 5736.42
- Average cost USD estimate: None

### curriculum_writer_agent
- Calls: 26
- Prompt/input tokens: 772905
- Candidate/output tokens: 221089
- Total tokens: 1093418
- Average total tokens: 42054.54
- Average cost USD estimate: None

### interview_transcript_agent
- Calls: 18
- Prompt/input tokens: 56762
- Candidate/output tokens: 1467
- Total tokens: 61189
- Average total tokens: 3399.39
- Average cost USD estimate: None

### interviewer_agent
- Calls: 114
- Prompt/input tokens: 408276
- Candidate/output tokens: 4591
- Total tokens: 422193
- Average total tokens: 3703.45
- Average cost USD estimate: None

### module_critic_agent
- Calls: 18
- Prompt/input tokens: 517611
- Candidate/output tokens: 11267
- Total tokens: 544454
- Average total tokens: 30247.44
- Average cost USD estimate: None

### profile_extractor_agent
- Calls: 25
- Prompt/input tokens: 63325
- Candidate/output tokens: 13216
- Total tokens: 81159
- Average total tokens: 3246.36
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
- Calls: 20
- Prompt/input tokens: 148551
- Candidate/output tokens: 206964
- Total tokens: 378427
- Average total tokens: 18921.35
- Average cost USD estimate: None

### root_agent
- Calls: 85
- Prompt/input tokens: 159889
- Candidate/output tokens: 18550
- Total tokens: 192456
- Average total tokens: 2264.19
- Average cost USD estimate: None

### usage_report_agent
- Calls: 15
- Prompt/input tokens: 377080
- Candidate/output tokens: 216
- Total tokens: 377669
- Average total tokens: 25177.93
- Average cost USD estimate: None


## By Tool
### auto_report_smoke_test
- Calls: 1
- Successes: 1
- Failures: 0
- Average latency ms: 2.5
- Average total tokens estimate: 9.0
- Average cost USD estimate: None

### file_io.load_curriculum_units_for_quiz
- Calls: 6
- Successes: 6
- Failures: 0
- Average latency ms: 2.46
- Average total tokens estimate: 43.0
- Average cost USD estimate: None

### file_io.save_text_file
- Calls: 79
- Successes: 79
- Failures: 0
- Average latency ms: 0.35
- Average total tokens estimate: 64.03
- Average cost USD estimate: None

### google_search
- Calls: 10
- Successes: 8
- Failures: 2
- Average latency ms: 13717.57
- Average total tokens estimate: 195.8
- Average cost USD estimate: None

### guardrail_check
- Calls: 8
- Successes: 8
- Failures: 0
- Average latency ms: None
- Average total tokens estimate: 61.62
- Average cost USD estimate: None

### logger_smoke_test
- Calls: 1
- Successes: 1
- Failures: 0
- Average latency ms: 1.23
- Average total tokens estimate: 8.0
- Average cost USD estimate: None

### source_integrity_check
- Calls: 6
- Successes: 3
- Failures: 3
- Average latency ms: None
- Average total tokens estimate: 602.83
- Average cost USD estimate: None

### usage_report.refresh
- Calls: 7
- Successes: 7
- Failures: 0
- Average latency ms: 8.55
- Average total tokens estimate: 58.0
- Average cost USD estimate: None

### web.url_validation
- Calls: 167
- Successes: 162
- Failures: 5
- Average latency ms: 812.53
- Average total tokens estimate: 76.22
- Average cost USD estimate: None
