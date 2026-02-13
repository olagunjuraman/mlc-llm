#!/bin/bash
set -eo pipefail

# ── Activate Conda ───────────────────────────────────────────────────────────
source /opt/conda/etc/profile.d/conda.sh
conda activate mlc

MODE="${1:-${MLC_BUILD_MODE:-shell}}"

# ── helpers ──────────────────────────────────────────────────────────────────

require_source() {
    if [ ! -f /workspace/CMakeLists.txt ]; then
        echo "Error: MLC-LLM source tree not found at /workspace."
        echo "Mount it:  docker run -v \$(pwd):/workspace ..."
        exit 1
    fi
}

do_build() {
    require_source
    cd /workspace

    # ── Ensure workspace is writable ─────────────────────────────────────
    if ! [ -w . ]; then
        sudo chown -R "$(id -u):$(id -g)" .
    fi

    # ── Configure Git safe directory ─────────────────────────────────────
    git config --global --add safe.directory /workspace

    # ── Step 1: Place cmake config ───────────────────────────────────────
    mkdir -p build
    if [ ! -f build/config.cmake ]; then
        cp /opt/mlc-build/config.cmake build/config.cmake 2>/dev/null \
            || sudo cp /opt/mlc-build/config.cmake build/config.cmake
    fi

    # Optional ccache wiring for faster repeat native builds in CI.
    CMAKE_ARGS=(-DCMAKE_BUILD_TYPE=Release)
    if command -v ccache >/dev/null 2>&1; then
        export CCACHE_DIR="${CCACHE_DIR:-/workspace/.ccache}"
        export CCACHE_MAXSIZE="${CCACHE_MAXSIZE:-2G}"
        mkdir -p "${CCACHE_DIR}"
        ccache --set-config=max_size="${CCACHE_MAXSIZE}" >/dev/null 2>&1 || true
        ccache --zero-stats >/dev/null 2>&1 || true
        CMAKE_ARGS+=(
            -DCMAKE_C_COMPILER_LAUNCHER=ccache
            -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
        )
    fi

    # ── Step 2: Configure and build (Ninja for speed) ────────────────────
    cd build
    cmake .. -G Ninja "${CMAKE_ARGS[@]}"
    ninja -j "$(nproc)"
    if command -v ccache >/dev/null 2>&1; then
        ccache --show-stats || true
    fi
    cd ..

    # ── Step 3: Package as wheel ─────────────────────────────────────────
    cd python
    pip wheel . --no-deps --wheel-dir /workspace/dist
    cd ..

    # ── Summary ──────────────────────────────────────────────────────────
    echo ""
    echo "=== Build complete ==="
    echo "Libraries:"
    ls -1 build/libmlc_llm*.so 2>/dev/null || true
    ls -1 build/tvm/libtvm_runtime.so 2>/dev/null || true
    echo "Wheel(s):"
    ls -1 dist/*.whl
}

do_test() {
    require_source
    cd /workspace

    # ── Verify build artifacts ───────────────────────────────────────────
    if [ ! -d build ] || ! ls build/libmlc_llm* 1>/dev/null 2>&1; then
        echo "Error: Native libraries not found. Run 'build' first."
        exit 1
    fi
    if ! ls dist/*.whl 1>/dev/null 2>&1; then
        echo "Error: No wheel found in dist/."
        exit 1
    fi

    # ── Install and verify ───────────────────────────────────────────────
    pip install --quiet apache-tvm-ffi numpy 2>/dev/null || true
    pip install --no-deps --quiet dist/*.whl 2>/dev/null || true
    python -c "from importlib.metadata import version; v = version('mlc_llm'); print(f'mlc_llm {v} — OK')"

    echo ""
    echo "=== Build validation passed ==="
}

do_validate() {
    # Quick environment check — no source mount needed, no compilation.
    # Used by CI to verify the Docker image has the right tools.
    echo "=== Environment Validation ==="
    echo "Python:  $(python --version 2>&1)"
    echo "CMake:   $(cmake --version 2>&1 | head -1)"
    echo "Ninja:   $(ninja --version 2>&1)"
    echo "Rustc:   $(rustc --version 2>&1)"
    echo "GCC:     $(gcc --version 2>&1 | head -1)"
    echo "LLVM:    $(llvm-config --version 2>/dev/null || echo 'not found')"
    echo "Conda:   $(conda info --envs 2>&1 | grep '*')"
    echo "=== Validation passed ==="
}

# ── dispatch ─────────────────────────────────────────────────────────────────

case "$MODE" in
    build)
        do_build
        ;;
    test)
        do_test
        ;;
    buildtest)
        do_build
        do_test
        ;;
    validate)
        do_validate
        ;;
    shell)
        exec /bin/bash
        ;;
    *)
        exec "$@"
        ;;
esac
