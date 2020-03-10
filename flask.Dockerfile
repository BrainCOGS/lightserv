#FROM python:3.7-alpine
FROM tiangolo/uwsgi-nginx-flask:python3.6
COPY flask_requirements.txt /app/flask_requirements.txt
WORKDIR /app
RUN pip install -r flask_requirements.txt
COPY . /app

CMD python run.py