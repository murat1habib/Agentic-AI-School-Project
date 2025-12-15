# multi_agent_topk.py
# Multi-Agent orchestration for fixing src/topk.py using local LLM (Ollama + llama3.1)
# Roles: Planner, Coder, Tester, Reviewer, Supervisor
# No external frameworks; pure Python orchestration.

import subprocess
import re
from pathlib import Path
import ollama

ROOT = Path(__file__).parent
SRC_FILE = ROOT / "src" / "topk.py"
MODEL = "llama3.1"  # gerekirse "phi3" de denenebilir
LLM_OPTS = {"temperature": 0}

############################
# Utilities
############################

def run_tests():
    """Run pytest and return (success, output_text)."""
    proc = subprocess.run(
        ["pytest", "-q"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return proc.returncode == 0, proc.stdout

def extract_between(text: str, tag: str = "file"):
    """Extract <file> ... </file> block."""
    m = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, re.S)
    return m.group(1) if m else None

def looks_like_topk_code(text: str) -> bool:
    return ("def top_k_frequent" in text) and ("from collections" in text or "Counter" in text)

def ask_llm(system: str, user: str, model: str = MODEL) -> str:
    resp = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        options=LLM_OPTS
    )
    return resp["message"]["content"]

############################
# Role Prompts
############################

PLANNER_SYS = """You are the Planner. You write a concise technical plan.
Goal function:
top_k_frequent(nums: List[int], k: int) -> List[int]

Rules to satisfy:
- Sort by frequency DESC
- On frequency ties, sort by value ASC
- If k > number of unique elements, return all unique following that rule
- Keep return type: List[int], stdlib only

Write a numbered plan (short). No code, just steps."""
PLANNER_USER_TMPL = """Context:
We have failing tests for top_k_frequent. We'll coordinate with Coder/Tester/Reviewer.
Current file content:

<file_current>
{code}
</file_current>

Recent test output (tail):

<pytest_output>
{pytest}
</pytest_output>

Write the plan now."""

CODER_SYS = """You are the Coder. Implement the plan as a FULL Python file for src/topk.py.
Constraints:
- Keep function name and signature
- Must pass tests that enforce: frequency DESC, tie -> value ASC, handle k larger than unique count
- Use only stdlib

Return ONLY the corrected file wrapped in:
<file>
...python code...
</file>"""
CODER_USER_TMPL = """Plan:
{plan}

Current file:

<file_current>
{code}
</file_current>

Tester/Reviewer notes (if any):

<notes>
{notes}
</notes>

Implement and return the full corrected file in <file>...</file>."""

TESTER_SYS = """You are the Tester. You cannot modify files. You only run tests and summarize failures briefly."""
TESTER_USER = """Run pytest on the project. Summarize: how many failed, key assertion messages, and which inputs failed."""

REVIEWER_SYS = """You are the Reviewer (senior engineer). Given the Coder's patch and the Tester summary,
- Point out concrete issues causing failures (or potential logical gaps)
- Provide 2-4 targeted suggestions to improve
- Be concise and practical"""
REVIEWER_USER_TMPL = """Patch under review (topk.py):

<file_patch>
{patch}
</file_patch>

Tester summary:

<test_summary>
{summary}
</test_summary>

Write your review & concrete suggestions."""

SUPERVISOR_SYS = """You are the Supervisor. Decide to 'ship' or 'iterate'.
Rules:
- If tests pass -> say SHIP
- Else -> say ITERATE and list what to change next round (one paragraph)."""
SUPERVISOR_USER_TMPL = """Planner plan:

{plan}

Reviewer comments:

{review}

Latest pytest status:
- passed_all = {passed}

If not passed, we also have the raw pytest tail:

<pytest_tail>
{pytest}
</pytest_tail>

Say either SHIP or ITERATE. If ITERATE, specify what Coder should change next."""

############################
# Orchestration
############################

def multi_agent_fix(max_rounds: int = 5):
    plan_cache = None
    notes_for_coder = ""

    for r in range(1, max_rounds + 1):
        print(f"\n================= ROUND {r} =================")

        # 0) quick check
        ok, out = run_tests()
        if ok:
            print("✅ All tests already passing. Nothing to do.")
            return

        code = SRC_FILE.read_text(encoding="utf-8")
        tail = out[-4000:]

        # 1) PLANNER (only first round, or if we want to refresh plan each round)
        if r == 1 or plan_cache is None:
            print("🧭 Planner drafting a plan...")
            plan_cache = ask_llm(
                PLANNER_SYS,
                PLANNER_USER_TMPL.format(code=code, pytest=tail)
            )
            print("---- PLAN ----")
            print(plan_cache[:800] + ("\n...\n" if len(plan_cache) > 800 else ""))

        # 2) CODER
        print("👩‍💻 Coder producing a patch...")
        coder_out = ask_llm(
            CODER_SYS,
            CODER_USER_TMPL.format(plan=plan_cache, code=code, notes=notes_for_coder)
        )
        new_code = extract_between(coder_out, "file")
        if not new_code and looks_like_topk_code(coder_out):
            print("ℹ️ No <file> block but code detected, using raw content.")
            new_code = coder_out

        if not new_code:
            print("❌ Coder did not provide a usable file. Here is what was sent:")
            print((coder_out[:1200] + "\n...\n") if len(coder_out) > 1200 else coder_out)
            print("↻ Asking Coder again with a stricter reminder.")
            stricter = (CODER_USER_TMPL + "\nIMPORTANT: Return ONLY the corrected file inside <file>...</file> with no commentary.")
            coder_out2 = ask_llm(CODER_SYS, stricter.format(plan=plan_cache, code=code, notes=notes_for_coder))
            new_code = extract_between(coder_out2, "file")
            if not new_code and looks_like_topk_code(coder_out2):
                new_code = coder_out2

        if not new_code:
            print("❌ Still no usable code from Coder. Aborting this round.")
            return

        # Write candidate patch
        SRC_FILE.write_text(new_code, encoding="utf-8")
        print("💾 Wrote candidate patch to src/topk.py")

        # 3) TESTER
        print("🧪 Running tests...")
        ok2, out2 = run_tests()
        if ok2:
            print("🎉 All tests passed after Coder patch!")
            return

        # Summarize failures with Tester LLM (optional but nice)
        print("🔎 Tester summarizing failures...")
        tester_summary = ask_llm(TESTER_SYS, TESTER_USER)
        # (Note: above Tester LLM isn't actually running pytest; we already did.
        # It's just assisting with a readable summary if you'd like.
        # For strict reproducibility, one could feed 'out2' into reviewer directly.)

        # 4) REVIEWER
        print("🧠 Reviewer analyzing patch and failures...")
        review_text = ask_llm(
            REVIEWER_SYS,
            REVIEWER_USER_TMPL.format(patch=new_code, summary=tester_summary + "\n\nRaw tail:\n" + out2[-1500:])
        )
        print("---- REVIEW ----")
        print(review_text[:1000] + ("\n...\n" if len(review_text) > 1000 else ""))

        # 5) SUPERVISOR
        print("🧑‍⚖️ Supervisor deciding next step...")
        decision = ask_llm(
            SUPERVISOR_SYS,
            SUPERVISOR_USER_TMPL.format(
                plan=plan_cache,
                review=review_text,
                passed=str(ok2),
                pytest=out2[-1200:]
            )
        )
        print("---- SUPERVISOR ----")
        print(decision)

        if "SHIP" in decision.upper():
            print("✅ Supervisor: SHIP → Done.")
            return
        else:
            # extract brief guidance for next iteration
            notes_for_coder = review_text + "\n\nSupervisor note:\n" + decision
            print("↻ ITERATE: Will incorporate Reviewer/Supervisor notes in next round.")

    print("⚠️ Max rounds reached. Check src/topk.py and test logs manually.")

if __name__ == "__main__":
    multi_agent_fix()