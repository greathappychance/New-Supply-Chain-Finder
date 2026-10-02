# Render, Railway, Cloud Run 등 Docker 기반 호스팅용
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 호스팅 서비스가 PORT 환경변수를 주면 그 포트를 쓴다.
EXPOSE 8501
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
