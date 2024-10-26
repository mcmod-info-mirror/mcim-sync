# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3-slim

EXPOSE 8000

# Install pip requirements
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY start.py config.py ./
COPY ./database ./database
COPY ./models ./models
COPY ./utils ./utils
COPY ./sync ./sync
COPY ./exceptions ./exceptions