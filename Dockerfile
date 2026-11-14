# One container = API + built web app. Made for Hugging Face Spaces (Docker), which
# runs the container as user 1000 and expects the app on port 7860.
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    MPLCONFIGDIR=/tmp/matplotlib \
    PYTHONUNBUFFERED=1 \
    PORT=7860
WORKDIR $HOME/app
COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user api/ api/
COPY --chown=user pipeline/ pipeline/
COPY --chown=user planner/ planner/
COPY --chown=user config/ config/
COPY --chown=user assets/ assets/
# only the small prepared map layers are needed at run time (not the raw height maps)
COPY --chown=user data/jezero/layers.npz data/jezero/layers.npz
COPY --chown=user data/moon/layers.npz data/moon/layers.npz
COPY --chown=user data/jezero/minerals.npz data/jezero/minerals.npz
COPY --chown=user data/jezero/photo.npz data/jezero/photo.npz
COPY --chown=user --from=web /web/dist frontend/dist
EXPOSE 7860
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
