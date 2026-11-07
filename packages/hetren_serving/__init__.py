"""CPU serving of the fine-tuned diagnosis model (Milestone 4).

``export`` turns the chosen checkpoint into GGUF files for llama.cpp
(EVAL_PROTOCOL.md, Amendment 2); ``llama_server`` is the client policy that
runs them with the declared decoding settings; ``parity`` checks that the
GGUF vocabulary matches the Hugging Face tokenizer.

This package is restricted: it never reaches the evaluator, the verifier or
the subject environment (enforced by the import-boundary tests).
"""
