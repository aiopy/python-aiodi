FROM docker.io/library/python:3.6.15-slim as development
#FROM docker.io/library/python:3.7-slim as development
#FROM docker.io/library/python:3.8-slim as development
#FROM docker.io/library/python:3.9-slim as development

WORKDIR /app

COPY .pre-commit-config.yaml LICENSE pyproject.toml pyscript.sh README.md requirements.txt requirements-dev.txt setup.py ./
COPY aiodi ./aiodi/
COPY tests ./tests/

RUN sh pyscript.sh install

ENTRYPOINT ["sh", "pyscript.sh"]
CMD []
