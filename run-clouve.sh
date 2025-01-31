export CLOUVE_PATH=/home/aom/Clouve

cd $CLOUVE_PATH
venv/bin/python -m pipenv install
venv/bin/python -m pipenv run dev
