# Contributing to IRIS

Thank you for your interest in contributing to IRIS.

---

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/IRIS.git`
3. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   source .venv/bin/activate   # macOS/Linux
   pip install -r requirements.txt
   ```
4. Pull a model: `ollama pull llama3.2`
5. Run: `streamlit run ui/app.py`

---

## Contribution Guidelines

### Code style
- Python 3.11+
- PEP 8 formatting
- Type hints on all public functions
- Docstrings on all public classes and methods
- `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for constants

### Adding a new tool
1. Create `tools/your_tool.py` inheriting from `BaseTool`
2. Implement `can_handle(query: str) -> bool` and `execute(query: str) -> str`
3. Register in `tools/tool_manager.py`
4. Add a health query in `ui/components/tool_manager.py`

### Adding a new UI page
1. Create `ui/pages/your_page.py` with a `render() -> None` function
2. Add the page to `ui/components/sidebar.py` navigation
3. Add routing in `ui/app.py`

### Commit messages
Use conventional commits:
- `feat: add new capability`
- `fix: resolve bug`
- `docs: update README`
- `refactor: improve structure`
- `test: add tests`

### Pull requests
- Keep PRs focused — one feature or fix per PR
- Include a description of what changed and why
- Ensure no debug prints remain
- Run existing tests before submitting

---

## Reporting Issues

Use the [GitHub Issues](https://github.com/your-username/IRIS/issues) page.
Include:
- Steps to reproduce
- Expected vs actual behaviour
- Python version and OS
- Relevant log output from `logs/iris.log`
