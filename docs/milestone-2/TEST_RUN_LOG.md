# Test-run log

Every run of any system on a test split (tier 1 or tier 2 `test_in_distribution` or `test_held_out`, or the live test split) is logged here, including runs that failed, stopped at a cap or were aborted, before its results are used. Rules: `docs/milestone-2/EVAL_PROTOCOL.md`, "Test-split evaluation".

Each entry gives: date (UTC), system and its declared version (prompt version, checkpoint, rules version), split(s), code commit, command, output directory and its result-file hashes, outcome (completed / failed / stopped / aborted, with the reason), spend for paid runs, and who ran it.

| # | date | system | splits | commit | outcome | spend | output and hashes | notes |
|---|---|---|---|---|---|---|---|---|
