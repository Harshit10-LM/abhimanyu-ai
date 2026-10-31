# Hacktoberfest Hack Day

## Team Details

- **Team Name:** KALKI
- **Team Members:**
  - Aaryan Sharma — [GitHub](https://github.com/aaryangif)
  - Harshit Raut — [GitHub](https://github.com/Harshit10-LM)
  - Amrit Raj — [GitHub](https://github.com/Amrit42-am)

## Selected Problem Statement

**Problem 8 — Gemma Track:** Build anything, with Gemma running on your laptop.

## Project Overview

We are building an entirely offline, privacy-first AI coding assistant. It helps developers generate code, understand code, and get explanations without relying on an internet connection during in-app use.

## Model Used and Why

- **Model:** Gemma 2, running locally through Ollama.
- **Why we chose it:** Gemma is an open-weight model that can be downloaded and run on local hardware. Running it locally lets our application process prompts on the user's machine instead of sending code or prompts to a cloud AI API. We chose this approach to prioritize privacy and make the assistant usable without an internet connection after the model has been downloaded and set up.

## AI Usage (Rule 4)

- **In the application:** Gemma 2, served locally through Ollama, is the core AI model used for code generation and code explanations. The intended in-app workflow does not depend on cloud AI APIs.
- **During development:** We used coding assistants such as GitHub Copilot and Cursor for help with boilerplate and development tasks. The team reviewed, adapted, and worked to understand the project's core implementation.
