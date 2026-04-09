### create virtual environment
python -m venv chess_venv

### activate venv
source chess_venv/bin/activate

### install dependencies
pip install -r requirements.txt

### update dependencies
pip freeze > requirements.txt