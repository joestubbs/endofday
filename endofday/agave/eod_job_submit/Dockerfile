# Docker image that is capable of submitting a job to Agave to run an arbitrary Agave app in an
# eod work flow.
#
# image: eod_job_submit

from alpine:3.2

RUN apk add --update musl python && rm /var/cache/apk/*
RUN apk add --update musl py-pip && rm /var/cache/apk/*

RUN apk add --update bash && rm -f /var/cache/apk/*
RUN apk add --update git && rm -f /var/cache/apk/*

ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

ADD submit.py /submit.py

CMD ["python", "/submit.py"]
