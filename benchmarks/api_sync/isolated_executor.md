# Isolated candidate execution

The candidate module is untrusted code. Do not import it in the host Python interpreter. Run it only in a disposable container with network disabled, no host credentials, no Docker socket, no privileged mode, a read-only root filesystem, resource limits, and a restricted mount containing only the candidate and the tests for the current stage.

Build the image from this directory before starting a benchmark, using an available Docker-compatible runtime. The image downloads pytest and pytest-cov during setup; inference and candidate execution remain local. The container should run with `--network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 1g --cpus 2`, a writable size-limited temporary filesystem for `/tmp`, and a read-only `/work` mount. Set `COVERAGE_FILE=/tmp/.coverage`, disable cache provider and use `--cov=sync_app --cov-report=term --cov-fail-under=90` when collecting coverage. A deadline must terminate the container and preserve its logs.

For public repair rounds, mount a staging directory containing only the candidate module and public tests. Do not mount the repository root, reference implementation, or hidden tests. After the final public round, run hidden acceptance tests in a separate fresh container with only the final module and hidden tests. Capture exit status, test output, coverage, and elapsed time. Check that candidate code has no network connectivity and cannot read a sentinel file outside the staging directory before using the executor for scoring.

This document describes the required isolation properties; it is not yet an implemented or verified feedback loop. No candidate has been executed in a container.
