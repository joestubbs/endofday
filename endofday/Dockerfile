FROM ubuntu

RUN apt-get update -y
RUN apt-get install -y openjdk-7-jre wget python-pip
RUN wget -qO- get.nextflow.io | bash
ADD nextflow.config /

RUN apt-get install -y curl
RUN curl -sSL https://get.docker.com/ubuntu/ | sudo sh

# supply a default config
ADD endofday.conf /endofday.conf

ADD core /core
RUN pip install -r /core/requirements.txt

ENV STAGING /staging
ENV STAGING_DIR /staging
# WORKDIR /staging

ENTRYPOINT ["/core/endofday.sh"]
