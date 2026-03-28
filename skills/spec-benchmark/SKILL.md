---
name: spec-benchmark
description: |
  A reusable 3-role AI benchmark architecture for evaluating AI comprehension of technical documents.
  Use this skill when building any system that needs to: (1) generate exam questions from documents/specs,
  (2) have an AI answer those questions, and (3) have another AI judge the answers and provide improvement feedback.
  Also trigger when the user mentions "benchmark testing", "spec evaluation", "AI exam system",
  "question generation from docs", or "AI grading/judging system". This pattern applies to any domain
  where you need to measure and improve an AI's understanding of reference material.
---

# Spec Benchmark Architecture Pattern

A three-role AI benchmark system for evaluating and improving AI comprehension of technical documents.

## When to Use

- Building a system to evaluate how well an AI understands a set of documents
- Creating exam/quiz generation from reference materials
- Setting up automated AI-vs-AI evaluation pipelines
- Measuring AI improvement over time against a fixed question bank

## Core Architecture: Three Roles

### 1. Examiner (Question Generator)
- Reads source documents (PDF, MD, TXT, etc.)
- Generates a question bank with reference answers
- Question types: QA (open-ended) and multiple choice
- Each question tagged with difficulty, source section, and type
- Runs separately from the exam — question bank is reusable

### 2. Examinee (Answer Provider)
- Receives questions one at a time (no access to reference answers)
- Answers based on its own knowledge/RAG context
- Can be any AI platform with a REST API

### 3. Judge (Scorer + Advisor)
- Compares examinee answer against reference answer
- Scores 0-100 per question with weighted criteria:
  - Correctness (50%): factual accuracy against spec
  - Completeness (30%): coverage of key points
  - Precision (20%): absence of incorrect/irrelevant info
- Provides per-question feedback and improvement suggestions
- Generates overall summary with actionable prompt/rule recommendations

## Data Flow

```
[Source Documents] → Examiner → [Question Bank JSON]
                                       ↓
                                  Exam Runner
                                       ↓
                              ┌────────┴────────┐
                              ↓                 ↓
                         Examinee            Judge
                        (answers)     (scores + feedback)
                              ↓                 ↓
                              └────────┬────────┘
                                       ↓
                              [Results: HTML + JSON + Suggestions]
```

## Key Design Decisions

### Separation of Flows
- **Question generation** and **exam execution** are independent flows
- Question bank is generated once and reused across multiple exam runs
- This allows tracking score improvement over time with the same questions

### Configurable Prompts
- All three role prompts stored as editable YAML files with `{{variable}}` placeholders
- Users modify prompts without touching code
- Structure: `prompts/examiner.yaml`, `prompts/examinee.yaml`, `prompts/judge.yaml`

### Output Artifacts (per exam run)
1. **Structured JSON** — machine-readable results with all scores, answers, feedback
2. **HTML Report** — self-contained single-file visual report (all CSS/JS inline)
3. **Suggestions File** — copy-pasteable improvement recommendations for the AI

### HTML Report Layout
```
┌──────────────────────────────────────────────┐
│  Header: title, date, average score          │
├──────────┬───────────────────────────────────┤
│ Question │ Question + Reference Answer       │
│ List     │ Examinee Answer                   │
│ (scores) │ Judge Feedback                    │
│          │ Improvement Suggestion            │
├──────────┴───────────────────────────────────┤
│ Overall Improvement Suggestions              │
└──────────────────────────────────────────────┘
```
- Left panel: clickable question list with color-coded scores (green/yellow/red)
- Right panel: full detail for selected question
- Bottom: aggregated improvement recommendations

### Configuration
Single YAML config file for:
- API endpoints and credentials (per role, since examiner/examinee/judge may use different models)
- Exam parameters (question count, mode: full vs random sampling)
- File paths (specs dir, question bank dir, results dir, prompts dir)

### Question Bank Schema
```json
{
  "metadata": {
    "spec_file": "source document name",
    "generated_at": "ISO timestamp",
    "total_questions": 100
  },
  "questions": [
    {
      "id": 1,
      "type": "qa | multiple_choice",
      "difficulty": "easy | medium | hard",
      "question": "...",
      "reference_answer": "...",
      "source_section": "section reference",
      "options": ["A)", "B)", "C)", "D)"],
      "correct_answer": "C",
      "explanation": "..."
    }
  ]
}
```

### Exam Results Schema
```json
{
  "exam_id": "exam_YYYYMMDD_HHMMSS",
  "timestamp": "ISO timestamp",
  "config": { "question_bank": "...", "mode": "full|random", "total_questions": 100 },
  "average_score": 72.5,
  "results": [
    {
      "question_id": 1,
      "question": "...",
      "reference_answer": "...",
      "examinee_answer": "...",
      "score": 85,
      "judge_feedback": "...",
      "improvement_suggestion": "..."
    }
  ],
  "overall_suggestion": "..."
}
```

## Adaptation Guide

When applying this pattern to a new project:

1. **Identify the source material** — what documents will be tested against?
2. **Choose AI providers** for each role — they can be different (e.g., Claude for examiner, local AI for examinee, either for judge)
3. **Customize prompt templates** — adjust scoring criteria, question types, and difficulty distribution to match your domain
4. **Define the exam lifecycle** — how often to regenerate questions vs reuse existing bank
5. **Set up the suggestions pipeline** — how improvement recommendations flow back into the AI's training/prompts
