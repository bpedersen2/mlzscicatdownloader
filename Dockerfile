FROM docker.ictrl.frm2.tum.de:5443/docker_proxy/library/python:3.11

RUN mkdir /app
COPY *.py /app/
RUN pip install flask uwsgi
WORKDIR /app

ENTRYPOINT flask
CMD ['run', '-h', '0.0.0.0:3000']
