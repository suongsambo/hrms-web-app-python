python3 --version
pip3 install flask
python3 -m pip install flask
source venv/bin/activate
pip install flask
python3 -c "import flask; print(flask.**version**)"

Use a Virtual Environment (Recommended)
python3 -m venv venv
source venv/bin/activate
pip install flask
python app.py

pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
pip install uwsgi
uwsgi --http 0.0.0.0:5000 --wsgi-file app.py --callable app --processes 4 --threads 2

python3 -m pip install flask-login
python3 -m pip install flask_sqlalchemy

python -m pip install flask-wtf

File
python3 install flask werkzeug

pip install -r requirements.txt
pip install -r requirements.txt
pip freeze > requirements.txt
