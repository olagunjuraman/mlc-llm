# DevOps Assessment Submission: CI/CD Pipeline & Workflow

This document details the custom CI/CD pipeline and development environment I designed and implemented for the **DevOps Engineer Assessment**.

It describes the specific workflow I defined in `.github/workflows/ci.yml`, which operates specifically to fulfill the assessment deliverables (Docker containerization, cross-platform builds, automated testing, and release automation). This pipeline runs alongside any existing project workflows but is distinct in its focus on the assessment criteria.

## 1. Development Environment (Docker)

I have created a multipurpose Docker image that serves as both a local development environment and the standardized build environment for the CI pipeline. This ensures consistency between local testing and remote builds.

**Image:** `ghcr.io/olagunjuraman/mlc-llm:latest`
**Base:** `continuumio/miniconda3` (Python 3.13, Rust, CMake, Ninja, LLVM, Vulkan)

### Interactive Shell
To start a development shell with the source code mounted:

```bash
docker run --rm -it \
  -v $(pwd):/workspace \
  ghcr.io/olagunjuraman/mlc-llm:latest
```

This drops you into the `mlc` conda environment with all dependencies pre-installed.

### Building from Source
To compile the C++ libraries and build the Python wheel without entering the shell:

```bash
docker run --rm \
  -v $(pwd):/workspace \
  ghcr.io/olagunjuraman/mlc-llm:latest build
```

**Artifacts:**
- Native libs: `build/`
- Python Wheel: `dist/mlc_llm-*.whl`

### Validation
To verify the toolchain versions inside the image:

```bash
docker run --rm ghcr.io/olagunjuraman/mlc-llm:latest validate
```

---

## 2. Assessment CI/CD Pipeline

My custom GitHub Actions workflow (`.github/workflows/ci.yml`) implements a **Test-Driven Deployment** strategy specifically for this assessment.

### Workflow Diagram

```mermaid
graph TD
    Start([Push / PR]) --> Lint[Lint & Infra Test]
    Lint --> Docker[Build/Cache Docker Image]
    Docker --> LinuxBuild[Build Wheel (Linux)]
    Lint --> WinBuild[Build Wheel (Windows)]
    
    LinuxBuild --> SmokeLin[Smoke Test Linux]
    WinBuild --> SmokeWin[Smoke Test Windows]
    
    SmokeLin --> Release{Is Tag?}
    SmokeWin --> Release
    
    Release -- Yes --> Publish[Sign & Release]
    Release -- No --> End([End])
```

### Pipeline Stages

1.  **Quality Checks (`lint`, `test`)**
    *   Validates `Dockerfile` syntax (Hadolint) and GitHub Actions config.
    *   Runs infrastructure tests (`tests/test_infra.py`) to verify project metadata.

2.  **Container Build (`docker`)**
    *   Builds the development image used by downstream Linux jobs.
    *   **Optimization:** I implemented a content-hash tag strategy (`buildenv-<hash>`). If `Dockerfile` or `config.cmake` haven't changed, the pipeline reuses the existing image from GHCR instead of rebuilding.

3.  **Cross-Platform Builds**
    *   **Linux (`wheel-linux`):** Runs inside the Docker container. Uses CMake + Ninja.
    *   **Windows (`wheel-windows`):** Runs on `windows-latest` runners. Uses MSVC.

4.  **Verification (`smoke-*`)**
    *   Installs the generated wheels in a fresh Python environment.
    *   Imports the package to ensure no missing dynamic libraries.

5.  **Release**
    *   **Trigger:** Pushing a tag (e.g., `v0.1.0`).
    *   **Signing:** Signs wheels using **Sigstore/Cosign** (keyless).
    *   **Publish:** Creates a GitHub Release with the wheels and signature files.

### Triggers
*   **Push to main:** Full build, image publish, artifact upload.
*   **Pull Request:** Full build (using cached image), no publishing.
*   **Tags (`v*`):** Triggers the Release job.
