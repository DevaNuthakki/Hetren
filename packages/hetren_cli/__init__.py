"""The ``hetren`` CLI (Milestone 4, step 4): offline diagnosis of agent runs recorded with Hetren's OpenAI
Agents SDK integration, with the validated GGUF on llama-server.

``inputs`` checks and converts a recorded run; ``models`` checks the GGUF and tokenizer against the export
manifest and fetches them; ``runtime`` starts llama-server with Amendment 2's settings; ``report`` writes the
result; ``main`` is the command line (``python -m packages.hetren_cli``).

This package is restricted: it never reaches the evaluator, the verifier or the subject environment
(enforced by the import-boundary tests). The full-episode demo, which needs the environment, lives on the
evaluator side (``sandbox_demo``), not here.
"""
