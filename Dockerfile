FROM python:3.11-alpine

ENV PYTHONUNBUFFERED=1

WORKDIR /srv
COPY requirements.txt /srv
RUN python -m pip install -r requirements.txt

COPY . /srv
ENTRYPOINT ["python", "-m", "flask", "--app", "app.app", "run", "--host", "0.0.0.0"]
