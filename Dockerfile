# One container = API + built frontend, for free hosting (Hugging Face Spaces listens on 7860)
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt fastapi uvicorn pillow pyproj
COPY api/ api/
COPY pipeline/ pipeline/
COPY planner/ planner/
COPY config/ config/
COPY assets/ assets/
# only the small prepared map layers are needed at run time (not the raw height maps)
COPY data/jezero/layers.npz data/jezero/layers.npz
COPY data/moon/layers.npz data/moon/layers.npz
COPY data/jezero/minerals.npz data/jezero/minerals.npz
COPY data/jezero/photo.npz data/jezero/photo.npz
COPY --from=web /web/dist frontend/dist
ENV PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
