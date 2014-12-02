FROM ubuntu

RUN apt-get update -y
RUN apt-get install -y openjdk-7-jre wget python-pip
RUN wget -qO- get.nextflow.io | bash
ADD nextflow.config /

RUN apt-get update -y
RUN apt-get install -y curl
RUN curl -sSL https://get.docker.com/ubuntu/ | sudo sh

ADD endofday /endofday
RUN pip install -r /endofday/requirements.txt

ENV STAGING /staging
ENV STAGING_DIR /staging
WORKDIR /staging

ENTRYPOINT ["/endofday/endofday.sh"]
