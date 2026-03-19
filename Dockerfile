# Use Ubuntu 24.04 as base FROM ubuntu:24.04
FROM ubuntu:24.04

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update -y \
 && apt-get upgrade -y \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        sudo \   
        s3fs \    
        ca-certificates \
        curl \
        gdal-bin \
        git-core \
        gosu \
        python3-gdal \
        python3-lxml \
        python3-psycopg2 \
        python3-pycurl \
        python3-pip \
        python3-netcdf4 \
        texlive-fonts-recommended \
        texlive-plain-generic \
        tini \
        tzdata \
        unzip \
        wget \
        cron \
        vim-tiny


RUN curl -LsSf https://astral.sh/uv/0.8.22/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_MANAGED_PYTHON=0

ENV CS_VENV_BASE="/usr/local/share/climatestation" \
    CS_APP_BASE="/home/eouser/clms/CLMS_clip_disseminate"

COPY pyproject.toml uv.lock .python-version ${CS_VENV_BASE}/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv --system-site-packages --directory ${CS_VENV_BASE} \
 && uv sync --directory ${CS_VENV_BASE} --no-dev


ENV PATH="${CS_VENV_BASE}/.venv/bin:$PATH" \
    PYTHONPATH=${CS_APP_BASE} \
    DEFAULT_RUFFUS_HISTORY_FILE=/tmp/climatestation/ruffus_history.sqlite \
    TMPDIR="/tmp/climatestation" \
    MPLCONFIGDIR="/tmp/climatestation" \
    PYPROJ_GLOBAL_CONTEXT="ON" \
    PROJ_LIB="/usr/share/proj" \
    PROJ_DATA="/usr/share/proj" \
    GDAL_DATA="/usr/share/gdal" 

RUN mkdir -p ${TMPDIR} && \
    python3 -m compileall -q -j 2 ${CS_APP_BASE}

# 2. Configure eouser with sudo permissions
RUN useradd -m -s /bin/bash eouser && \
    usermod -aG sudo eouser && \
    # This allows eouser to run sudo without a password prompt
    echo "eouser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# # Set working directory
# WORKDIR /home/eouser/clms/CLMS_clip_disseminate

# # Copy the repository
# COPY . /home/eouser/clms/CLMS_clip_disseminate/


# # Change ownership to eouser
# RUN chown -R eouser:eouser /home/eouser

# 1. Perform SYSTEM level configs as ROOT
USER root

# 2. Allow non-root users to use the 'allow_other' mount option
RUN sed -i 's/#user_allow_other/user_allow_other/' /etc/fuse.conf

# # Setup script and mount point
# COPY entrypoint.sh /usr/local/bin/entrypoint.sh
# RUN chmod +x /usr/local/bin/entrypoint.sh
# Create mount points and set ownership
RUN mkdir -p /data /eodata /home/eouser/clms/outputs /home/eouser/clms/logs /home/eouser/clms/config && \
    chown -R root:root /data /home/eouser

# Set environment variables for credentials
ENV S3_ACCESS_KEY=your_access_key
ENV S3_SECRET_KEY=your_secret_key

# # 3. Final switch to eouser
# USER eouser
# Set working directory
WORKDIR /home/eouser/clms/CLMS_clip_disseminate

# Copy the repository
COPY . /home/eouser/clms/CLMS_clip_disseminate/
# ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# Default command
# CMD ["python3", "automation_script.py"]