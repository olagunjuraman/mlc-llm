FROM continuumio/miniconda3:23.10.0-1

ARG DEBIAN_FRONTEND=noninteractive


LABEL org.opencontainers.image.title="mlc-llm-dev" \
      org.opencontainers.image.description="Multipurpose dev/build image for MLC-LLM" \
      org.opencontainers.image.source="https://github.com/mlc-ai/mlc-llm" \
      org.opencontainers.image.licenses="Apache-2.0"


# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        ccache \
        curl \
        git \
        git-lfs \
        sudo \
        vim \
        htop \
        less \
        unzip \
    && rm -rf /var/lib/apt/lists/*

RUN conda create -n mlc -c conda-forge -c pytorch \
        python=3.13 \
        "cmake>=3.24" \
        "llvmdev>=15" \
        rust \
        ninja \
        # Vulkan dependencies
        "vulkan-headers" \
        "libvulkan-loader" \
        "sysroot_linux-64" \
        "spirv-tools" \
        "spirv-headers" \
        "glslang" \
        "zlib" \
        "zstd" \
        "libxml2" \
        "ncurses" \
        pytest \
        numpy \
        decorator \
        attrs \
        typing_extensions \
        psutil \
        scipy \
        tornado \
        cloudpickle \
        ml_dtypes \
        pydantic \
        requests \
        fastapi \
        uvicorn \
        pytorch-cpu \
    && conda clean -ya


ARG USER_NAME=mlc
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid ${USER_GID} ${USER_NAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} --create-home --shell /bin/bash ${USER_NAME} \
    && echo "${USER_NAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USER_NAME} \
    && chmod 0440 /etc/sudoers.d/${USER_NAME}


RUN mkdir -p /workspace && chown "${USER_UID}:${USER_GID}" /workspace
WORKDIR /workspace


COPY docker/config.cmake /opt/mlc-build/config.cmake
COPY docker/build-entrypoint.sh /usr/local/bin/build-entrypoint.sh
RUN chmod +x /usr/local/bin/build-entrypoint.sh


USER ${USER_NAME}


ENTRYPOINT ["/usr/local/bin/build-entrypoint.sh"]
CMD ["shell"]
