# KindMind AI

*Let Kindness Open Doors to Education.*

KindMind AI is my project for the PayPal AI Hackathon 2026. It helps people discover educational causes, understand what each one needs, ask an AI assistant questions, and try a **sandbox (test) donation** that the AI proposes and the visitor approves.

**Live demo:** https://mujeeba.pythonanywhere.com (no login needed)

## How PayPal and AI are used

- **AI:** Claude by Anthropic (Claude API) powers the assistant. It answers only from the project facts on the site and has one tool, `propose_donation`.
- **PayPal:** Braintree, a PayPal service, in its **Sandbox**. It takes the test payment through Braintree's Drop-in card form, so card details never reach my server. PayPal's own developer sign-up was not available from my country (Pakistan), so I used Braintree, which the hackathon rules list as a PayPal service.

## How it works

1. **Browse** sample projects (homepage, causes list, project pages).
2. **Ask the AI assistant.** It can make mistakes and does not verify any organization.
3. **The AI proposes, the human approves.** When a visitor wants to donate, the assistant calls `propose_donation`. The server re-validates it (the project must exist, whole dollars from $1 to $100, never more than the project still needs) and signs it into a short-lived proposal token.
4. **The visitor approves** the proposal on the page and enters sandbox test card details in Braintree's secure hosted fields.
5. **The server pays only what it signed.** The checkout route accepts only a valid, unexpired, unused proposal token. The project and amount come from the token, never from the browser.
6. **Verified confirmation.** The server checks the transaction Braintree reports, records it, and the confirmation page shows only payments that exist in that record.

## Honesty notes

- All projects are sample content written for the hackathon. They are not real or verified initiatives.
- No real money is collected. Payments are **Braintree Sandbox test payments** only.
- The "amount raised" on project pages stays at $0, because no real donations exist. Sandbox payments do not change it.
- The AI cannot charge anyone. It can only propose, and the visitor must approve each payment.
- Mujeeba Foundation for Learning and Development is a vision. I have applied to register it, and the approval is still in process. It is not yet a registered organization.

## Try it as a judge

1. Open https://mujeeba.pythonanywhere.com/assistant
2. Click "Recommend a project for a $20 donation".
3. Click "Approve and pay (sandbox test)".
4. Use the test card `4111 1111 1111 1111`, any future expiry date, any 3-digit CVV.
5. You will see a confirmation page with a sandbox transaction ID.

## What has been tested

- Unit checks for the proposal rules, signing, expiry, tampering, double payment and verification logic: `python tests/test_payments.py` (runs with a fake gateway, no keys needed).
- Live sandbox payments on the hosted site, from proposal to confirmation.

## Tech stack

Python, FastAPI, Jinja2 templates, plain CSS, Anthropic Claude API, Braintree Sandbox (a PayPal service), hosted on PythonAnywhere.

## Run locally

    pip install -r requirements.txt
    uvicorn main:app --reload

Set these environment variables first (see `.env.example`, and never commit real keys):

- `ANTHROPIC_API_KEY`
- `BRAINTREE_MERCHANT_ID`, `BRAINTREE_PUBLIC_KEY`, `BRAINTREE_PRIVATE_KEY` (Braintree **Sandbox** keys)

Without the Braintree keys the site still runs, and the assistant says plainly that the payment step is not connected. Then open http://127.0.0.1:8000

## Built with help

I am a beginner programmer. I built this project with the help of an AI assistant (Claude), and I tested each part myself.

## License

MIT. See the `LICENSE` file.
