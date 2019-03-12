FROM python:3.7-slim

RUN mkdir -p /app

COPY requirements.txt /app
RUN pip install -r /app/requirements.txt

COPY . /app

EXPOSE 3000

WORKDIR /app
CMD [ "python", "main.py" ]

