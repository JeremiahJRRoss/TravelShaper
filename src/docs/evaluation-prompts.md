# Evaluation Methodology

## The Problem That Evaluation Solves

There is a particular failure mode that plagues AI-powered tools, and it is worth understanding before looking at any metrics. The failure is silent. The system returns a response. The response looks reasonable. No error was thrown, no timeout occurred, no tool crashed. And yet the user walks away unsatisfied — because the answer was incomplete, or the wrong tools were called, or the tone made them feel like the system didn't understand what they asked for.

Traditional software testing cannot catch this. You can write a unit test that verifies the flight search tool returns valid JSON, and it will pass every time, and it will tell you nothing about whether the agent chose to call the flight search tool when the user asked for flights. The gap between "the system works" and "the system works well" is where evaluation lives.

TravelShaper's evaluation pipeline addresses this gap with three LLM-as-judge metrics, each designed to catch a specific category of failure that was observed repeatedly during development. The metrics run against real traces collected in Arize Phoenix and are scored by a separate LLM call (gpt-4o) that reads the user's input and the agent's output and renders a judgment. The results are logged back to Phoenix, where they appear in the Evaluations tab alongside the traces themselves.

This document explains why each metric exists, what it measures, how it produces its output, and what a Solutions Engineering leader should expect to see when reviewing the results.

## How the Pipeline Works

The evaluation runner (`evaluations/run_evals.py`) connects to Phoenix, pulls the most recent traces, and passes each one through three classification prompts using Phoenix's `llm_classify` function. Each prompt receives the user's original message and the agent's full response. The classifier returns a label and an explanation for each trace.

Results are written back to Phoenix as evaluation annotations on the original traces. This means you can open any trace in the Phoenix UI, see the agent's tool calls and response, and immediately see how all three metrics scored that interaction — without switching tools or cross-referencing spreadsheets.

Any traces flagged as frustrated are automatically collected into a `frustrated_interactions` dataset within Phoenix, creating a ready-made queue for human review.

## Metric 1: User Frustration

**The problem it catches:** The agent returns a technically correct response, but the user experience is poor. The response might be curt, or dismissive of the user's constraints, or structured in a way that forces the user to do extra work to extract the information they need. During development, early versions of the system prompt produced responses that answered the question but felt robotic — they listed flight options without explaining why one was better than another, or they ignored the user's stated preferences in their recommendations.

**Why this metric matters:** Frustration is the leading indicator that a user will not come back. A response can be factually accurate and still be a product failure if the user feels unheard. For a Solutions Engineering team evaluating this system, frustration scores are the closest proxy to customer satisfaction that an automated pipeline can provide.

**How it works:** This metric uses Phoenix's built-in `USER_FRUSTRATION_PROMPT_TEMPLATE` rather than a custom prompt. The built-in template was chosen after testing both options because it proved more consistent across edge cases — particularly for vague queries where the user's intent was ambiguous and a custom prompt tended to over-flag reasonable responses as frustrating.

The local file `evaluations/metrics/frustration.py` exports `USER_FRUSTRATION_PROMPT_CUSTOM`, a reference implementation that was used during development and is preserved in the codebase for comparison. It is not used in the production evaluation pipeline.

**Expected output:** Each trace is labeled as frustrated or not frustrated, with an explanation. A healthy run against the 11 trace queries should produce zero or one frustrated interactions. If you see three or more, something has changed in the system prompt or model behavior that warrants investigation.

**What to do with the results:** Open the `frustrated_interactions` dataset in Phoenix. Read the explanations. The classifier's reasoning often pinpoints the exact sentence or omission that triggered the flag — "the response listed hotels but did not address the user's stated dietary restriction" or "the agent used a dismissive tone when the user asked a vague question." These explanations are the fastest path to identifying which part of the system prompt needs adjustment.

## Metric 2: Tool Usage Correctness

**The problem it catches:** The agent calls the wrong tools, or fails to call the right ones. A user asks for flights and hotels, and the agent searches for flights but skips the hotel search. A user says they are already at their destination and do not need transport, and the agent searches for flights anyway, wasting time and SerpAPI quota.

This was the most common failure mode during development. The LLM has access to four tools and must decide which subset to call based on the user's natural language message. That decision is where most things go wrong — and it is invisible to the user, who sees only the final response and has no way of knowing whether the agent called one tool or four.

**Why this metric matters:** For a Solutions Engineering team, tool correctness is a direct measure of system efficiency. Every unnecessary tool call consumes API quota (SerpAPI charges per search) and adds latency (each tool call takes 2–5 seconds). Every missed tool call produces an incomplete response that the user will notice. This metric tells you whether the agent's reasoning about tool selection is sound.

**How it works:** The `TOOL_CORRECTNESS_PROMPT` is a custom LLM-as-judge prompt defined in `evaluations/metrics/tool_correctness.py`. It receives the user's message and the agent's response, and evaluates whether the tools that were called (visible in the trace data) match what the user's request required.

The prompt is designed to understand the relationship between request content and tool applicability: a message with departure city, destination, and dates should trigger flight and hotel searches; a message that says "I am already there" should not trigger flights; a domestic U.S. trip should not trigger the cultural guide (which is designed for international travel).

**Expected output:** Each trace is labeled as correct or incorrect tool usage, with an explanation of what was expected versus what occurred. Against the 11 trace queries — which were specifically designed to cover every tool combination including single-tool, no-tool, and all-tool scenarios — a correct implementation should score 11 out of 11. A score below 10 indicates a regression in the agent's tool selection reasoning.

**What to do with the results:** If a trace is flagged as incorrect, open it in Phoenix and inspect the tool call chain. Look at what tools were called and what arguments were passed. The most common root cause is that the system prompt's tool usage instructions are too vague for a particular edge case — for example, the agent may not understand that a user who says "I don't need flights" means they should skip the flight search entirely, not search for flights and then mention they weren't needed.

## Metric 3: Answer Completeness

**The problem it catches:** The agent's response is missing information that the user asked for. The user requested flights, hotels, cultural prep, and restaurant recommendations, but the response only covers flights and hotels. Or the user asked about photography spots in Lisbon and the response talks about food instead.

This sounds like a simple problem, but it has a subtle wrinkle that makes naive completeness checks misleading: sometimes the agent is *intentionally* incomplete. If a user asks "just show me flights, I have hotels sorted," a complete response should contain only flight information. A naive completeness metric would flag that as incomplete because it lacks hotel data. This is why the metric needs scope awareness.

**Why this metric matters:** Completeness is the quality dimension that most directly affects whether the user accomplishes their goal. A frustrated user might still get what they need; an incomplete response guarantees they do not. For Solutions Engineering leaders evaluating the system for a customer-facing deployment, completeness scores answer the question: "If I hand this to a user, will they get what they asked for?"

**How it works:** The `ANSWER_COMPLETENESS_PROMPT` is a custom LLM-as-judge prompt defined in `evaluations/metrics/answer_completeness.py`. Its distinguishing feature is scope awareness. The prompt instructs the classifier to first determine what the user actually asked for — not what a "full" response would contain, but what *this particular user* requested — and then evaluate whether the response covered each requested element.

A response that covers flights, hotels, cultural prep, and dining recommendations is complete for a full-trip query. The same response would be overcomplete (but not penalized) for a flights-only query. A flights-only response is complete for a flights-only query but incomplete for a full-trip query. The metric distinguishes between these cases.

**Expected output:** Each trace is labeled as complete or incomplete, with an explanation that references the specific elements the user requested and whether each was addressed. Against the 11 trace queries, which include both full-scope and deliberately scoped requests, a correct implementation should score 11 out of 11. An incomplete flag on a scoped query (like the flights-only or cultural-guide-only test) indicates a defect in the prompt's scope detection logic.

**What to do with the results:** If a trace is flagged as incomplete, the explanation will identify which requested element was missing. Cross-reference this with the tool correctness score for the same trace. If the tools were called correctly but the response is incomplete, the problem is in the synthesis step — the agent had the data but failed to include it in the final briefing. If the tools were not called correctly, the incompleteness is downstream of a tool selection failure. The fix depends on which stage failed.

## Reading the Results Together

No single metric tells the full story. The value of running all three is in the intersections.

A trace that scores correct on tools, complete on answers, but frustrated on experience tells you the system is mechanically sound but tonally off — the system prompt needs voice tuning, not tool logic changes.

A trace that scores correct on tools but incomplete on answers tells you the LLM is gathering the right data but dropping information during synthesis — the system prompt's structural instructions (section headings, required elements) may need reinforcement.

A trace that scores incorrect on tools will almost always also score incomplete on answers, because missing tool calls produce missing data. The tool correctness flag identifies the root cause; the completeness flag shows the user-facing consequence.

For a Solutions Engineering leader reviewing evaluation results before a customer deployment, the summary view in Phoenix's Evaluations tab provides the fastest read: what percentage of interactions pass all three metrics, and for the ones that fail, which metric fails most often. That single distribution tells you where to invest your next round of prompt engineering.
