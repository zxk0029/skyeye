FROM python:3.12
ENV PYTHONUNBUFFERED 1
WORKDIR /app
ADD . /app
RUN pip install -r requirements.txt
EXPOSE 8201
CMD ["gunicorn", "skyeye.wsgi:application", "--bind", "0.0.0.0:8201"]
