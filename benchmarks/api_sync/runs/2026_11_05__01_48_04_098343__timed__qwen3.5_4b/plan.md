# Design and plan

Use a standard-library-only single module for a fair, bounded generation task. Separate HTTP transport, validation, transaction management, retry policy, and CLI orchestration. Fetch and validate into memory before beginning the database transaction; use parameterized SQLite statements and an explicit transaction. Test through dependency injection and mocked `urllib.request.urlopen`. Candidate code may choose its internal design while honoring the public signatures and behavior in `spec.md`.
