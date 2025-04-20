FROM python:3.13-slim

LABEL "com.github.actions.name"="GitHub Actions Version Updater"
LABEL "com.github.actions.description"="GitHub Actions Version Updater updates GitHub Action versions in a repository and creates a pull request with the changes."
LABEL "com.github.actions.icon"="upload-cloud"
LABEL "com.github.actions.color"="green"

LABEL "repository"="https://github.com/saadmk11/github-actions-version-updater"
LABEL "homepage"="https://github.com/saadmk11/github-actions-version-updater"
LABEL "maintainer"="saadmk11"

RUN apt-get update \
    && apt-get install \
    -y \
    --no-install-recommends \
    --no-install-suggests \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src /app/src/
RUN touch /app/src/__init__.py

ENV PYTHONPATH "/app"

CMD ["python", "/app/src/main.py"]
