# tot_topk.py
# Tree-of-Thoughts (ToT) controller for fixing src/topk.py using local LLM (Ollama + llama3.1)
# Generates multiple candidate patches per round, tests each, keeps the best; iterates.

import subprocess
import re
from pathlib import Path
import ollama

ROOT = Path(__file__).parent
SRC_FILE = ROOT / "src" / "topk.py"
MODEL = "llama3.1"  # istersen "phi3" de deneyebilirsin
LLM_BASE_OPTS = {"temperature": 0}  # taban (bazı dalları farklılaştıracağız)

# ToT arama parametreleri
ROUNDS = 3            # en fazla tur
BRANCHES = 3          # tur başına aday sayısı
BRANCH_TEMPS = [0.0, 0.3, 0.7]  # çeşitlilik için farklı sıcaklıklar
ASSERT_TAIL = 1800    # pytest çıktısından geri bildirim için kuyruk uzunluğu

SYSTEM_HINT = """You are a senior Python engineer using a Tree-of-Thoughts search.
Task: Implement top_k_frequent(nums: List[int], k: int) -> List[int] in src/topk.py.

Must satisfy ALL rules:
- Sort by frequency DESC
- On ties (same frequency), sort by value ASC
- If k > number of unique elements, return all unique following the rule
- Keep function name and signature, use stdlib only
- Return type: List[int]

Return ONLY the corrected FULL file wrapped in:
<file>
...python code...
</file>
"""

CANDIDATE_USER_TMPL = """
Current file:
<file_current>
{code}
</file_current>

Recent pytest tail (for guidance):
<pytest_output>
{pytest}
</pytest_output>

Now produce ONE alternative implementation that strictly follows the rules.
Vary your approach/ordering logic versus other candidates (e.g., Counter + sorted with key=(-freq, value) OR manual buckets OR most_common + tie-fix).
Return the FULL file inside <file>...</file>.
"""

def run_tests():
    """Run pytest and return (success: bool, output: str)."""
    proc = subprocess.run(
        ["pytest", "-q"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return proc.returncode == 0, proc.stdout

def parse_score(pytest_out: str) -> tuple[int, int, bool]:
    """
    Return (passed, failed, had_error).
    - If parsing fails, approximate.
    """
    passed = 0
    failed = 0
    had_error = False

    # Common patterns: "6 passed", "1 failed", "2 failed, 4 passed", etc.
    m_pass = re.search(r"(\d+)\s+passed", pytest_out)
    m_fail = re.search(r"(\d+)\s+failed", pytest_out)
    m_error = re.search(r"ERRORS?|error:", pytest_out, re.I)

    if m_pass:
        passed = int(m_pass.group(1))
    if m_fail:
        failed = int(m_fail.group(1))
    if m_error:
        had_error = True

    # If nothing matched but return code was non-zero, call it an error case
    return passed, failed, had_error

def extract_between(text: str, tag: str = "file"):
    m = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, re.S)
    return m.group(1) if m else None

def looks_like_topk_code(text: str) -> bool:
    return ("def top_k_frequent" in text) and ("Counter" in text or "from collections" in text)

def ask_llm(user: str, temperature: float) -> str:
    opts = dict(LLM_BASE_OPTS)
    opts["temperature"] = temperature
    resp = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_HINT},
            {"role": "user", "content": user},
        ],
        options=opts
    )
    return resp["message"]["content"]

def evaluate_candidate(code_text: str) -> tuple[int, int, bool, str]:
    """Write candidate, run tests, return (passed, failed, had_error, pytest_out)."""
    # Backup current
    original = SRC_FILE.read_text(encoding="utf-8")
    try:
        SRC_FILE.write_text(code_text, encoding="utf-8")
        ok, out = run_tests()
        passed, failed, had_error = parse_score(out)
        return passed, failed, had_error, out
    finally:
        # Always restore original; caller will write best later
        SRC_FILE.write_text(original, encoding="utf-8")

def tot_search():
    # First quick check
    ok0, out0 = run_tests()
    if ok0:
        print("✅ All tests already passing. Nothing to do.")
        return

    best_code = None
    best_score = (-1, 10**9, True)  # (passed DESC, failed ASC, had_error False preferred)
    best_out = out0

    for round_idx in range(1, ROUNDS + 1):
        print(f"\n================= ToT ROUND {round_idx} =================")
        code = SRC_FILE.read_text(encoding="utf-8")
        tail = best_out[-ASSERT_TAIL:]

        # Generate BRANCHES candidates
        branch_results = []
        for bi in range(BRANCHES):
            temp = BRANCH_TEMPS[bi % len(BRANCH_TEMPS)]
            print(f"\n🌿 Branch {bi+1}/{BRANCHES} — temperature={temp}")
            user_prompt = CANDIDATE_USER_TMPL.format(code=code, pytest=tail)
            content = ask_llm(user_prompt, temperature=temp)

            new_code = extract_between(content, "file")
            if not new_code and looks_like_topk_code(content):
                print("ℹ️ No <file> block, but code detected — using raw content.")
                new_code = content

            if not new_code:
                print("⚠️ Candidate missing or malformed. Skipping.\n-----\n" +
                      (content[:800] + "\n...\n" if len(content) > 800 else content))
                continue

            # Evaluate this candidate
            passed, failed, had_error, out = evaluate_candidate(new_code)
            print(f"   → score: passed={passed}, failed={failed}, error={had_error}")
            branch_results.append((passed, failed, had_error, new_code, out))

        if not branch_results:
            print("❌ No valid candidates produced this round.")
            break

        # Pick best candidate by (passed DESC, failed ASC, had_error False preferred)
        branch_results.sort(key=lambda x: (x[0], -x[1], not x[2]), reverse=True)
        top = branch_results[0]
        b_passed, b_failed, b_err, b_code, b_out = top

        # Keep global best if improved
        def better(a, b):
            # Compare tuples (passed DESC, failed ASC, had_error False preferred)
            (ap, af, ae) = a
            (bp, bf, be) = b
            if bp != ap: return bp > ap
            if bf != af: return bf < af
            return (not be) and ae  # prefer no-error over error if equal

        if better(best_score, (b_passed, b_failed, b_err)):
            best_score = (b_passed, b_failed, b_err)
            best_code = b_code
            best_out = b_out

        # If fully passed, write and stop
        if "passed" in b_out and "failed" not in b_out and "ERROR" not in b_out.upper():
            SRC_FILE.write_text(b_code, encoding="utf-8")
            print("🎉 Best candidate PASSED all tests. Written to src/topk.py")
            return

        # Otherwise continue to next round with feedback from best_out
        print(f"↻ Not all tests passed. Keeping best candidate of round {round_idx} for guidance and iterating...")

    # After all rounds, if we have any improvement, write it
    if best_code:
        SRC_FILE.write_text(best_code, encoding="utf-8")
        print("ℹ️ Wrote the best-improving candidate to src/topk.py (not fully green).")
        print("   Check pytest output and consider another run or manual tweak.")
    else:
        print("⚠️ Could not produce a usable candidate. Please try again or adjust prompts.")

if __name__ == "__main__":
    tot_search()