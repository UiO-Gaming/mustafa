FROM python:3.14

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg graphviz pandoc

COPY pyproject.toml uv.lock .python-version ./

RUN uv sync --locked --no-dev --no-cache

RUN .venv/bin/python -m nltk.downloader -d /usr/local/share/nltk_data stopwords

COPY . .

# Let Graphviz find the bundled font for text in other scripts, like CJK
RUN mkdir -p /usr/local/share/fonts && ln -s /app/src/assets/fonts/NotoSansCJK-Bold.ttc /usr/local/share/fonts/

ENV PATH="/app/.venv/bin:$PATH"

VOLUME /app/logs

CMD ["python3", "src/run.py"]
