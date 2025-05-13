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

pip install --upgrade eventlet
pip install gevent

pyinstaller --onefile app.py
chmod +x ./dist/app

pyinstaller --onefile --add-data "templates:templates" --add-data "static:static" --hidden-import flask app.py
./dist/app

pyinstaller --onefile --hidden-import flask_socketio --hidden-import eventlet --hidden-import gevent app.py
pip install flask-socketio eventlet gevent gevent-websocket

pyinstaller --onefile --hidden-import flask_socketio --hidden-import eventlet --hidden-import gevent --hidden-import gevent-websocket --add-data "templates:templates" --add-data "static:static" app.py

git rm -r --cached **pycache**
find . -type d -name '**pycache**' -exec rm -r {} +
git rm --cached .DS_Store

sudo chown -R $(whoami):$(whoami) /home/kpca/sites/hrs-management-web-app/venv/
pip install --force-reinstall MarkupSafe

sudo chmod 777 /home/kpca/sites/hrs-management-web-app/database
ls -l /home/kpca/sites/hrs-management-web-app/database
sudo chmod 777 /home/kpca/sites/hrs-management-web-app/database

# Only once per language

pybabel init -i messages.pot -d translations -l km

# Then translate in: translations/km/LC_MESSAGES/messages.po

# Then compile:

pybabel compile -d translations

# Init

pybabel extract -F babel.cfg -o messages.pot .
pybabel init -i messages.pot -d translations -l en
pybabel init -i messages.pot -d translations -l km

# View installed packages

pipdeptree

# Check for vulnerabilities

pip install pip-audit
pip-audit
