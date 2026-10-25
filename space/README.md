---
title: Fynn Lab API
sdk: docker
app_port: 7860
pinned: false
short_description: Backend for the Fynn Lab demo (Before vs After credit-coach bots)
---

# Fynn Lab API

The backend for the live demo at [youngsukhwang.github.io/fynn-lab](https://youngsukhwang.github.io/fynn-lab/): both bots of [Fynn Lab](https://github.com/YoungsukHwang/fynn-lab), a study of skill-based routing for a credit-coach chatbot. It is not affiliated with Kikoff, and the members and products are fictional.

This Space is deployed from the GitHub repo by `.github/workflows/space.yml`; edit the code there, not here.

- `POST /chat`, `GET /personas`, `GET /architecture`, `GET /health`.
- Limits: 20 chat requests per visitor per hour and 400 a day in all (one question to both bots is two requests).
- Settings: `ANTHROPIC_API_KEY` is a Space secret; `FYNN_CHAT_LIMIT_PER_VISITOR_PER_HOUR`, `FYNN_CHAT_LIMIT_PER_DAY` and `FYNN_CORS_ORIGINS` can be overridden as Space variables.
