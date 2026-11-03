# KindMind AI

*Let Kindness Open Doors to Education.*

KindMind AI is a hackathon project for the PayPal AI Hackathon 2026. It aims to help people discover educational causes, understand what they need, and ask questions before supporting them.

> **Status: work in progress.** This README is updated as each part is built and tested.

## What works right now (Stage 1)

- Homepage, causes list, and project detail pages
- Clearly labelled **sample/demo** projects (not real initiatives, no real donations)

## Not connected yet

- AI assistant (planned: Claude API)
- Donation checkout using the Braintree (PayPal) sandbox

These will be listed as working here only after they are implemented and tested.

## Important honesty notes

- All projects are sample content written for the hackathon.
- No real donations are collected. Payments will be sandbox test payments only.
- Mujeeba Foundation for Learning and Development is a vision still in development and is not a registered organization.
- The AI assistant will provide information only and does not verify organizations.

## Tech stack

Python, FastAPI, Jinja2 templates, plain CSS.

## Run locally

Install the requirements with: pip install -r requirements.txt

Start the app with: uvicorn main:app --reload

Then open http://127.0.0.1:8000

## Deploy (Render)

- Build command: pip install -r requirements.txt
- Start command: uvicorn main:app --host 0.0.0.0 --port $PORT

## License

MIT. See the LICENSE file.
