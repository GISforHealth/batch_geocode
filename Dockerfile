FROM python:3.10
COPY ./requirements.txt /geocode/requirements.txt

WORKDIR /geocode
RUN pip install -r requirements.txt

COPY . /geocode

CMD python rungeocode.py