FROM python:3.11-bullseye

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

COPY . /bdr_tools
WORKDIR /bdr_tools

CMD ["python3", "-m", "bdr_tools"]