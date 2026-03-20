# Contributing to AEO Skills

Thanks for your interest in improving the AEO Skills suite.

## Adding a New Skill

1. Create a directory: `aeo-your-skill-name/`
2. Add a `SKILL.md` with YAML frontmatter (name + description)
3. Add `scripts/` directory if the skill has a Python script
4. Add `references/` directory for supporting docs

### SKILL.md Requirements
- YAML frontmatter with `name` and `description`
- Link back to the repo and suite
- Requirements section
- Defaults section (model + samples)
- Usage with CLI examples
- Options list
- Output format description
- Tips section

### Script Requirements
- Python 3.9+ stdlib only (no pip dependencies)
- Use `shared/gemini_client.py` for all Gemini API calls
- argparse with `--help`
- Support `--output text|json`
- Retry logic with exponential backoff (use shared client)
- Default to `gemini-3-flash-preview` and 20 runs

## Code Standards
- No third-party dependencies (stdlib only)
- All scripts must pass `py_compile`
- Use type hints where practical
- Follow existing code style (see any script in `*/scripts/`)

## Testing
- Run `python3 -m py_compile your_script.py` to verify syntax
- Test with `--help` flag
- Test with a real Gemini API key if possible
- Test both `--output text` and `--output json`

## Submitting Changes
1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Verify all scripts compile: `find . -name "*.py" -exec python3 -m py_compile {} \;`
5. Open a pull request with a clear description

## Reporting Issues
Open an issue with:
- Which skill/script is affected
- What you expected vs what happened
- Your Python version and OS
