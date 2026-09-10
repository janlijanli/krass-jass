# Multi-stage: the Rust search core has to be compiled, but the runtime image should not
# carry a Rust toolchain.
#
# The builder is the *same* Python image as the runtime, with Rust added — not a Rust image
# with Python added. A wheel built against a different minor version will not install, and
# Debian's system Python is 3.11 while the runtime is 3.12.
#
# NOTE: tags here, digests before deploy. CLAUDE.md requires pinned base image digests
# (threat T6); pin them in CI, where they can be resolved and recorded.
FROM python:3.12-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo PATH=/usr/local/cargo/bin:$PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --profile minimal --default-toolchain 1.83.0

RUN pip install --no-cache-dir maturin

WORKDIR /build
COPY rust/ rust/
COPY krass_jass/ krass_jass/
COPY pyproject.toml README.md ./
RUN cd rust && maturin build --release --interpreter python3.12 --out /wheels


FROM python:3.12-slim-bookworm AS runtime

# Non-root, and it owns nothing it does not need to.
RUN useradd --create-home --uid 10001 jass

WORKDIR /app
COPY --from=builder /wheels /wheels
COPY pyproject.toml README.md ./
COPY krass_jass/ krass_jass/
COPY bot/ bot/
COPY web/ web/

RUN pip install --no-cache-dir /wheels/*.whl \
    && pip install --no-cache-dir \
        "fastapi>=0.115" "uvicorn[standard]>=0.30" "jinja2>=3.1" \
        "python-multipart>=0.0.9" "httpx>=0.27" "pydantic>=2" \
    && rm -rf /wheels \
    && python -c "import krass_jass_core, krass_jass, bot.service, web.app"

USER jass
EXPOSE 8000

# Overridden per service in compose; the bot is the default because there are three of it.
CMD ["python", "-m", "uvicorn", "bot.service:app", "--host", "0.0.0.0", "--port", "8000"]
