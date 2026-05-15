# syntax=docker/dockerfile:1
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

ARG TORCH_CUDA_TAG=cu124
ARG HF_HOME=/cache/huggingface
ARG TORCH_HOME=/cache/torch

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive \
    CUDA_HOME=/usr/local/cuda-12.4 \
    PATH=/usr/local/cuda-12.4/bin:$PATH \
    LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH \
    HF_HOME=${HF_HOME} \
    HUGGINGFACE_HUB_CACHE=${HF_HOME}/hub \
    HF_HUB_CACHE=${HF_HOME}/hub \
    TRANSFORMERS_CACHE=${HF_HOME}/hub \
    TORCH_HOME=${TORCH_HOME}

# Set work directory
WORKDIR /app

# Install system dependencies + Python 3.11
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       python3.11 \
       python3.11-dev \
       python3.11-distutils \
       python3-pip \
       build-essential \
       gcc \
       g++ \
       pkg-config \
       git \
       libpq-dev \
       libldap2-dev \
       libsasl2-dev \
       libsndfile1 \
       libsndfile1-dev \
       ffmpeg \
       libgl1-mesa-glx \
       libglib2.0-0 \
       curl \
    && rm -rf /var/lib/apt/lists/*

# Set python3.11 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Install Python dependencies
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install --ignore-installed blinker && \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/${TORCH_CUDA_TAG} && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=60s --timeout=60s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]


