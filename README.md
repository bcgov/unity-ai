# unity-ai
A Unity AI endpoint used to communicate and produce AI responses

# Quick Start
### back-end
python -m venv venv && source venv/bin/activate

pip install -r requirements.txt

python main.py g                # embed schema once

python main.py                  # starts Flask on :5000

### front-end
cd recap

npm install -g @angular/cli     # install angular CLI once

npm install                     # install dependencies once

ng serve                        # starts Angular on :4200
