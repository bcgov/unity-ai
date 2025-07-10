# unity-ai
A Unity AI endpoint used to communicate and produce AI responses

# Project Structure
main.py          ── Flask server + NL→SQL pipeline
QDECOMP_examples.json ─ Few-shot CoT examples
embedded_schema/ ── persisted Chroma vectors
recap/              └─ Angular front-end

# Quick Start
### back-end
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py g                # embed schema once
python main.py                  # starts Flask on :5000

### front-end
cd recap
npm install -g @angular/cli     # Install angular CLI once
npm install                     # Install dependencies once
ng serve