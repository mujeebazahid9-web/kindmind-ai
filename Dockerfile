FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

RUN mkdir -p /home/user/app
WORKDIR /home/user/app

RUN git clone --depth 1 https://github.com/mujeebazahid9-web/kindmind-ai.git .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
