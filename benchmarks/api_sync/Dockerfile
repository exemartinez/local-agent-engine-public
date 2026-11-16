FROM python:3.12-slim
RUN python -m pip install --no-cache-dir pytest==9.2.0 pytest-cov==7.1.0 coverage==7.17.2
RUN useradd --create-home --uid 10001 benchmark
USER 10001:10001
WORKDIR /work
ENV PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
ENTRYPOINT ["python", "-m", "pytest", "-p", "pytest_cov"]
