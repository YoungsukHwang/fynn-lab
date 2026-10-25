# The Fynn Lab API as a Hugging Face Docker Space. .github/workflows/space.yml assembles the Space from
# this file, space/README.md, backend/, skills/ and personas/, laid out as in the repo.
FROM python:3.12-slim

WORKDIR /app
COPY backend/ backend/
# Installs the dependencies; the app itself runs from backend/ (--app-dir), so it finds skills/ and personas/.
RUN pip install --no-cache-dir ./backend
COPY skills/ skills/
COPY personas/ personas/

# Hugging Face runs the container as user 1000 and sends traffic to app_port in README.md.
RUN useradd -m -u 1000 user
USER user

# Public demo settings; Space variables override them. ANTHROPIC_API_KEY is a Space secret.
# The limits count requests, and one question to both bots is two: 10 questions per visitor per hour,
# 200 a day for everyone.
ENV FYNN_CORS_ORIGINS=https://youngsukhwang.github.io \
    FYNN_CHAT_LIMIT_PER_VISITOR_PER_HOUR=20 \
    FYNN_CHAT_LIMIT_PER_DAY=400 \
    FYNN_TRUST_FORWARDED=1

EXPOSE 7860
CMD ["uvicorn", "api.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "7860"]
