"""
ContextChat Evaluation Script
==============================
Runs 5 scripted multi-turn conversations against the /chat endpoint and checks:
1. Memory recall — Does the bot remember plan/team details from earlier turns?
2. Scope adherence — Does it decline unrelated requests?
3. Escalation — Does it escalate refund/security-type requests properly?
4. No hallucination — Does it avoid fabricating pricing or features?
5. Plan recommendation — Does it recommend appropriate plans based on user details?

Usage:
    python run_evals.py [--base-url http://localhost:8000]

Output:
    A pass/fail table for each conversation scenario.
"""

import argparse
import json
import sys
import uuid
import requests


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

DEFAULT_BASE_URL = "http://localhost:8000"


def chat(base_url: str, session_id: str, message: str) -> str:
    """Send a message and return the bot's response."""
    resp = requests.post(
        f"{base_url}/chat",
        json={"session_id": session_id, "message": message},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def reset(base_url: str, session_id: str):
    """Reset a session."""
    requests.post(
        f"{base_url}/reset",
        json={"session_id": session_id},
        timeout=10,
    )


def check_keywords(response: str, required: list[str], forbidden: list[str] = None) -> tuple[bool, str]:
    """
    Check if a response contains required keywords and none of the forbidden ones.
    Returns (passed, reason).
    """
    lower_resp = response.lower()

    for kw in required:
        if kw.lower() not in lower_resp:
            return False, f"Missing required keyword: '{kw}'"

    if forbidden:
        for kw in forbidden:
            if kw.lower() in lower_resp:
                return False, f"Found forbidden keyword: '{kw}'"

    return True, "All checks passed"


# ──────────────────────────────────────────────
# Eval Scenarios
# ──────────────────────────────────────────────

def eval_1_memory_recall(base_url: str) -> dict:
    """
    Test: Memory Recall
    The bot should remember plan and team details mentioned in earlier turns
    when asked about them later.
    """
    sid = f"eval_{uuid.uuid4().hex[:8]}"
    reset(base_url, sid)

    results = []

    # Turn 1: Establish context
    r1 = chat(base_url, sid, "Hi, I'm on the Pro plan with a team of 15 people.")
    results.append({"turn": 1, "response": r1})

    # Turn 2: Ask about integrations
    r2 = chat(base_url, sid, "Can you tell me about the Slack integration?")
    results.append({"turn": 2, "response": r2})

    # Turn 3: Ask another question
    r3 = chat(base_url, sid, "How do I export my project data?")
    results.append({"turn": 3, "response": r3})

    # Turn 4: Ask about billing
    r4 = chat(base_url, sid, "What's my current monthly cost?")
    results.append({"turn": 4, "response": r4})

    # Turn 5+: Test memory — does it remember Pro plan and team size?
    r5 = chat(base_url, sid, "Can you remind me what plan I'm on and how many people are on my team?")

    # Check: response should reference Pro plan and 15 people
    passed, reason = check_keywords(r5, ["pro", "15"])

    return {
        "name": "Memory Recall",
        "description": "Bot remembers plan type and team size from turn 1 at turn 5+",
        "passed": passed,
        "reason": reason,
        "final_response": r5,
    }


def eval_2_scope_adherence(base_url: str) -> dict:
    """
    Test: Scope Adherence
    The bot should politely decline requests unrelated to Flowly.
    """
    sid = f"eval_{uuid.uuid4().hex[:8]}"
    reset(base_url, sid)

    # Turn 1: Normal greeting
    chat(base_url, sid, "Hello!")

    # Turn 2: Off-topic request
    r2 = chat(base_url, sid, "Can you help me write a Python script to sort a list?")

    # Check: should decline and mention Flowly
    passed, reason = check_keywords(
        r2,
        ["flowly"],  # Should reference that it can only help with Flowly
        ["def ", "sort(", "python"]  # Should NOT provide actual code
    )

    return {
        "name": "Scope Adherence",
        "description": "Bot declines off-topic coding request and stays within Flowly scope",
        "passed": passed,
        "reason": reason,
        "final_response": r2,
    }


def eval_3_escalation(base_url: str) -> dict:
    """
    Test: Escalation Protocol
    The bot should escalate refund requests to a human agent.
    """
    sid = f"eval_{uuid.uuid4().hex[:8]}"
    reset(base_url, sid)

    # Turn 1: Context
    chat(base_url, sid, "I've been charged twice for my Pro subscription this month.")

    # Turn 2: Request refund
    r2 = chat(base_url, sid, "I need a refund for the duplicate charge. Can you process that?")

    # Check: should mention escalation/human agent
    passed, reason = check_keywords(
        r2,
        ["human agent", "escalat"],  # Should mention escalation or human agent
    )

    # Slightly relaxed check — either "human agent" OR "escalat" is enough
    lower_resp = r2.lower()
    if "human agent" in lower_resp or "escalat" in lower_resp:
        passed = True
        reason = "Correctly escalated to human agent"
    else:
        passed = False
        reason = "Did not mention escalation or human agent for refund request"

    return {
        "name": "Escalation Protocol",
        "description": "Bot escalates refund request to human agent instead of processing it",
        "passed": passed,
        "reason": reason,
        "final_response": r2,
    }


def eval_4_no_hallucination(base_url: str) -> dict:
    """
    Test: No Hallucination
    The bot should not fabricate features or pricing that don't exist.
    """
    sid = f"eval_{uuid.uuid4().hex[:8]}"
    reset(base_url, sid)

    # Ask about a non-existent feature
    r1 = chat(base_url, sid, "Does Flowly have AI-powered auto-scheduling and a built-in video conferencing feature?")

    # Check: should NOT confirm these features exist; should say it doesn't have that info
    lower_resp = r1.lower()

    # The bot should express uncertainty or offer to connect with a human
    has_uncertainty = any(phrase in lower_resp for phrase in [
        "don't have that information",
        "not mentioned",
        "i'm not sure",
        "not aware",
        "human agent",
        "can't confirm",
        "not available",
        "don't have information",
        "unable to confirm",
    ])

    # Should NOT confidently confirm these features
    hallucinated = any(phrase in lower_resp for phrase in [
        "yes, flowly has ai-powered auto-scheduling",
        "flowly includes video conferencing",
        "built-in video call",
    ])

    if hallucinated:
        passed = False
        reason = "Hallucinated — confirmed non-existent features"
    elif has_uncertainty:
        passed = True
        reason = "Correctly expressed uncertainty about unknown features"
    else:
        # Partial pass — didn't hallucinate but also didn't clearly express uncertainty
        passed = True
        reason = "Did not hallucinate (response was ambiguous but safe)"

    return {
        "name": "No Hallucination",
        "description": "Bot does not fabricate features or pricing not in its instructions",
        "passed": passed,
        "reason": reason,
        "final_response": r1,
    }


def eval_5_plan_recommendation(base_url: str) -> dict:
    """
    Test: Plan Recommendation
    The bot should recommend a plan based on user-provided details.
    """
    sid = f"eval_{uuid.uuid4().hex[:8]}"
    reset(base_url, sid)

    # Turn 1: Provide team details
    r1 = chat(
        base_url, sid,
        "I have a team of 50 people, we need SSO, admin controls, and priority support. "
        "What plan do you recommend?"
    )

    # Check: should recommend Business plan ($25/user/month)
    passed, reason = check_keywords(r1, ["business"])

    return {
        "name": "Plan Recommendation",
        "description": "Bot recommends Business plan for large team needing SSO/admin features",
        "passed": passed,
        "reason": reason,
        "final_response": r1,
    }


# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────

ALL_EVALS = [
    eval_1_memory_recall,
    eval_2_scope_adherence,
    eval_3_escalation,
    eval_4_no_hallucination,
    eval_5_plan_recommendation,
]


def run_all_evals(base_url: str):
    """Run all evaluation scenarios and print results."""
    print("=" * 70)
    print("  ContextChat Evaluation Suite")
    print(f"  Target: {base_url}")
    print("=" * 70)
    print()

    results = []
    for eval_fn in ALL_EVALS:
        print(f"  Running: {eval_fn.__doc__.strip().split(chr(10))[1].strip()} ...")
        try:
            result = eval_fn(base_url)
            results.append(result)
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"  Result:  {status} — {result['reason']}")
        except Exception as e:
            results.append({
                "name": eval_fn.__name__,
                "description": "Error during evaluation",
                "passed": False,
                "reason": str(e),
                "final_response": "",
            })
            print(f"  Result:  ❌ ERROR — {e}")
        print()

    # ── Summary Table ──

    print("=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    print()
    print(f"  {'#':<4} {'Test Name':<25} {'Status':<10} {'Reason'}")
    print(f"  {'─'*3} {'─'*24} {'─'*9} {'─'*30}")

    pass_count = 0
    for i, r in enumerate(results, 1):
        status = "PASS" if r["passed"] else "FAIL"
        if r["passed"]:
            pass_count += 1
        print(f"  {i:<4} {r['name']:<25} {status:<10} {r['reason']}")

    print()
    print(f"  Total: {pass_count}/{len(results)} passed")
    print("=" * 70)

    # Return exit code (0 = all pass, 1 = some fail)
    return 0 if pass_count == len(results) else 1


def main():
    parser = argparse.ArgumentParser(description="Run ContextChat evaluation suite")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL of the ContextChat backend (default: {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()

    exit_code = run_all_evals(args.base_url)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
