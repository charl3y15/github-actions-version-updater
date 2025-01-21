FROM python:3.10-slim-buster

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

# Set working directory
WORKDIR /app

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src /app/src/
RUN touch /app/src/__init__.py

# Set environment variables
ENV PYTHONPATH "/app"

# Add additional debug information
RUN python -c "import sys; import os; print('Python path:', sys.path); print('Contents:', os.listdir('.')); print('Src contents:', os.listdir('src'));"

# Copy Dockerfile Updater scripts
COPY dockerfile-updater-main/action /action/

# Make shell script executable
RUN chmod +x /action/run.sh

# Set entrypoint to the combined run script
CMD ["bash", "/action/run.sh"]
