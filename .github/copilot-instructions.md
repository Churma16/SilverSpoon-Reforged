# GitHub Copilot Commit Rules
When generating commit messages or summaries, you MUST strictly adhere to the Conventional Commits 1.0.0 specification:
1. Format: type(scope): short present-tense imperative description
2. Allowed lower-case types: `feat`, `fix`, `chore`, `build`, `refactor`, `test`, `docs`, `perf`, `style`, `ci`.
3. The description string following the colon MUST start with a lowercase letter.
4. Always use imperative present-tense verbs (e.g., use "add", not "added").
5. Do not include trailing punctuation or periods at the end of the summary line.

# EXCLUSIONS & RESTRICTIONS
- DO NOT append any "Co-authored-by:" metadata, signatures, or developer attribution lines to the description.
- Keep the commit message focused strictly on the code changes themselves without signing off.