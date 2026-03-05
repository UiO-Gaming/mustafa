FROM python:3.14

WORKDIR /app

COPY requirements.txt .

RUN python3 -m pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y ffmpeg graphviz pandoc

COPY . .

VOLUME logs

CMD ["python3", "src/run.py"]
