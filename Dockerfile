FROM python:3.12

WORKDIR /app

COPY requirements.txt .

RUN python3 -m pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y imagemagick ffmpeg libsm6 libxext6 graphviz pandoc

COPY . .

RUN mkdir -p /etc/ImageMagick-7 && mv /app/src/assets/policy.xml /etc/ImageMagick-7/policy.xml

VOLUME logs

CMD ["python3", "src/run.py"]
