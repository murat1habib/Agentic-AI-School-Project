# reflective_fix_topk.py  (Ollama + Llama 3.1, robust parsing)
import subprocess
import re
from pathlib import Path
import ollama

ROOT = Path(__file__).parent
SRC_FILE = ROOT / "src" / "topk.py"

SYSTEM_HINT = """You are a senior Python engineer.
You will receive the current code and pytest failures.
Goal: Implement top_k_frequent(nums: List[int], k: int) -> List[int] with rules:
- Sort by frequency descending.
- On frequency ties, sort by value ascending.
- If k > number of unique elements, just return all unique following the rule.
- Keep return type: List[int]. No external packages beyond stdlib.
Return ONLY the corrected file between <file> ... </file>.
"""

USER_TEMPLATE = """
Current file:
<file_current>
{code}
</file_current>

Pytest output (tail):
<pytest_output>
{pytest}
</pytest_output>

Return corrected code wrapped as:

<file>
...python code...
</file>
"""

def run_tests():
    proc = subprocess.run(
        ["pytest", "-q"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return proc.returncode == 0, proc.stdout

def extract_between(text: str, tag: str = "file"):
    m = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, re.S)
    return m.group(1) if m else None

def looks_like_full_python(text: str) -> bool:
    return ("def top_k_frequent" in text) and ("from collections" in text)

def ask_model(prompt: str, model: str = "llama3.1") -> str:
    resp = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_HINT},
            {"role": "user",  "content": prompt}
        ],
        options={"temperature": 0}
    )
    return resp["message"]["content"]

def reflective_fix(rounds=3, model="llama3.1"):
    for r in range(1, rounds + 1):
        print(f"\n=== Round {r} ===")
        ok, out = run_tests()
        if ok:
            print("✅ All tests already passing.")
            return

        print("❌ Tests failing — sending to model...")
        code = SRC_FILE.read_text(encoding="utf-8")
        tail = out[-4000:]
        prompt = USER_TEMPLATE.format(code=code, pytest=tail)

        content = ask_model(prompt, model=model)
        new_code = extract_between(content, "file")

        if not new_code:
            if looks_like_full_python(content):
                print("ℹ️ No <file> block, but code detected — using content as file.")
                new_code = content
            else:
                print("↻ Asking model to resend within <file> tags...")
                content2 = ask_model(
                    "You forgot the <file> block. Resend exactly the same corrected file, "
                    "with no commentary, wrapped in:\n<file>\n...code...\n</file>",
                    model=model
                )
                new_code = extract_between(content2, "file")
                if not new_code and looks_like_full_python(content2):
                    print("ℹ️ Still no tags, using detected code.")
                    new_code = content2

        if not new_code:
            print("❌ Model still didn't provide usable code. Here is what it sent:\n---\n")
            print((content[:1000] + "\n...\n") if len(content) > 1000 else content)
            return

        SRC_FILE.write_text(new_code, encoding="utf-8")
        print("💾 Patched src/topk.py. Re-testing...")

        ok2, _ = run_tests()
        if ok2:
            print("🎉 Fixed! All tests passed.")
            return
        else:
            print("Still failing; continuing...")

    print("⚠️ Max rounds reached — check the last patch & tests manually.")

if __name__ == "__main__":
    reflective_fix()