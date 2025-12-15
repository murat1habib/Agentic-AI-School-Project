# 🧠 Agentic AI: Reflective, Multi-Agent, and Tree-of-Thoughts on `top_k_frequent`

This project demonstrates three major **Agentic AI reasoning strategies** applied to the same algorithmic task:  
`top_k_frequent(nums, k)`.

The goal is to highlight how **Reflective Models**, **Multi-Agent Systems**, and **Tree-of-Thoughts (ToT)** behave differently when solving the same deterministic problem — and how agentic patterns improve reasoning, reliability, and autonomy when powered by **local LLMs** using **Ollama**.

---

## 🚀 Overview

### ✔ Reflective Model  
An iterative “self-improvement” loop where the model:  
1. Generates a solution  
2. Runs tests  
3. Reviews the failure output  
4. Rewrites its own code  
5. Repeats until tests pass  

This mirrors how human developers debug code.

---

### ✔ Multi-Agent Model  
A coordinated multi-role system including:  
- **Planner** – designs a strategy  
- **Coder** – writes full patched code  
- **Tester** – executes pytest  
- **Reviewer** – critiques and inspects errors  
- **Supervisor** – decides SHIP / ITERATE  

This simulates a real engineering team.

---

### ✔ Tree-of-Thoughts (ToT)  
A search-based method where the model:  
- Generates multiple candidate solutions per round  
- Tests each candidate  
- Scores them  
- Selects the best branch  
- Expands or prunes the search tree  

Useful for reasoning tasks with many possible thought paths.

---

Together, these three methods offer a clear comparison of how different Agentic AI paradigms tackle the same problem under the same conditions.


## 🛠 Technologies Used

| Technology | Purpose |
|-----------|----------|
| **Python 3.10+** | Core implementation and scripting |
| **pytest** | Automated testing for all solutions |
| **Ollama** | Local LLM runtime (free & offline) |
| **Llama 3.1 / Phi-3** | Local LLM models used for reasoning |
| **Agentic AI Patterns** | Reflective, Multi-Agent, Tree-of-Thoughts implementations |
| **Virtual Environment (venv)** | Used to isolate project dependencies and keep the environment clean |

We use a Python **virtual environment (venv)** to ensure reproducible installations and avoid dependency conflicts.

---

## 🏁 Conclusion

This project demonstrates how different **Agentic AI** reasoning strategies behave when solving the same deterministic coding challenge: `top_k_frequent`.  

- **Reflective Models** improve through iterative self-correction.  
- **Multi-Agent Systems** coordinate specialized roles to converge on better solutions.  
- **Tree-of-Thoughts** explores diverse reasoning paths and selects the most promising one.  

Using **local, free LLMs** via Ollama shows how advanced AI reasoning can be achieved without cloud APIs or external costs. Together, these approaches highlight the future direction of intelligent, autonomous large-scale AI systems.
