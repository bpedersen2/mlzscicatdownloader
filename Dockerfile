FROM docker.ictrl.frm2.tum.de:5443/docker_proxy/library/python:3.11

RUN mkdir /app
COPY . /app/
RUN pip install -e /app
WORKDIR /app

CMD ["--app", "scicatdownloader.wsgi",  "run",  "-h", "0.0.0.0",  "-p" ,"3000"]
ENTRYPOINT ["flask"]
