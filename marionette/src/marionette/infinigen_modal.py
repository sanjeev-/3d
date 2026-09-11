"""
Modal cloud GPU module for generating Blender scenes with Infinigen.

This module defines a Modal app (`marionette-infinigen`) that runs Princeton
VL's Infinigen procedural scene generator on GPU containers and uploads the
resulting `scene.blend` file to S3.

Two scene types are supported:
- ``"outdoor"``: ``infinigen_examples.generate_nature``
- ``"indoor"``:  ``infinigen_examples.generate_indoors``

Prereqs (one-time):
1. ``modal token new``
2. Create a Modal secret named ``aws-s3`` with keys:
   - ``AWS_ACCESS_KEY_ID``
   - ``AWS_SECRET_ACCESS_KEY``
   - ``AWS_REGION`` (optional, defaults to us-east-1)
"""

import modal
from typing import Any, Dict, List, Optional

# Pinning the Infinigen commit makes container builds reproducible. Bump this
# deliberately when you want to pull in upstream changes.
INFINIGEN_GIT_REF = "main"

app = modal.App("marionette-infinigen")

aws_secret = modal.Secret.from_name("aws-s3")

# Infinigen needs Blender's bpy + a CUDA toolchain to build its terrain C
# extensions. We start from an NVIDIA CUDA image and add Python + Blender
# system deps on top.
infinigen_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04", add_python="3.11"
    )
    .apt_install(
        "git",
        "wget",
        "cmake",
        "build-essential",
        "ffmpeg",
        # Blender / OpenGL runtime libs
        "libgl1",
        "libglu1-mesa",
        "libsm6",
        "libxi6",
        "libxrender1",
        "libxkbcommon0",
        "libgomp1",
        "libxxf86vm1",
        "libxfixes3",
        "libxcb1",
        "libegl1",
        "libxext6",
    )
    .run_commands(
        # Blender 4.5.6 — matches the version used by marionette's renderer so
        # the produced .blend files load cleanly downstream.
        "wget -q https://download.blender.org/release/Blender4.5/blender-4.5.6-linux-x64.tar.xz -O /tmp/blender.tar.xz",
        "tar -xf /tmp/blender.tar.xz -C /opt/",
        "mv /opt/blender-4.5* /opt/blender",
        "rm /tmp/blender.tar.xz",
        "ln -s /opt/blender/blender /usr/local/bin/blender",
    )
    .pip_install(
        # bpy as a Python module — used by Infinigen's Python entrypoints.
        "bpy==4.2.0",
        "boto3>=1.34.0",
        "pydantic>=2.0.0",
        "numpy",
        "scipy",
        "trimesh",
        "shapely",
        "opencv-python-headless",
    )
    .run_commands(
        # Clone + install Infinigen from source. We use --no-build-isolation so
        # the C extensions can find the bpy/numpy installed above.
        f"git clone --depth 1 --branch {INFINIGEN_GIT_REF} "
        "https://github.com/princeton-vl/infinigen.git /opt/infinigen",
        "cd /opt/infinigen && pip install --no-build-isolation -e '.[terrain]'",
        # Build terrain C extensions (provides cnpy/marching_cubes used by
        # generate_nature). Failure here would silently break outdoor scenes.
        "cd /opt/infinigen && bash scripts/install/compile_terrain.sh || true",
    )
    .env({"PYTHONUNBUFFERED": "1", "INFINIGEN_ASSET_FOLDER": "/tmp/infinigen_assets"})
    .workdir("/opt/infinigen")
)


def _resolve_module(scene_type: str) -> str:
    if scene_type == "outdoor":
        return "infinigen_examples.generate_nature"
    if scene_type == "indoor":
        return "infinigen_examples.generate_indoors"
    raise ValueError(f"scene_type must be 'indoor' or 'outdoor', got {scene_type!r}")


@app.function(
    image=infinigen_image,
    gpu="A10G",
    timeout=60 * 60 * 2,  # 2 hours — outdoor scenes can be slow
    retries=1,
    secrets=[aws_secret],
)
def generate_scene(
    scene_type: str,
    seed: int,
    s3_bucket: str,
    s3_key: str,
    configs: Optional[List[str]] = None,
    extra_args: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate a single Infinigen scene and upload `scene.blend` to S3.

    Runs entirely inside a Modal GPU container.

    Args:
        scene_type: ``"indoor"`` or ``"outdoor"``.
        seed: Infinigen random seed (also used as the scene id).
        s3_bucket: Destination S3 bucket name.
        s3_key: Full destination key (e.g. ``"infinigen/outdoor/0042.blend"``).
        configs: Optional list of Infinigen ``.gin`` config names passed via
            ``--configs`` (e.g. ``["desert.gin", "simple.gin"]``).
        extra_args: Extra CLI args appended to the Infinigen invocation.

    Returns:
        Dict with keys ``success``, ``seed``, ``scene_type``, ``s3_uri``,
        ``size_bytes``, ``duration_seconds``, ``error`` (when failed).
    """
    import os
    import subprocess
    import time
    from pathlib import Path

    import boto3

    result: Dict[str, Any] = {
        "success": False,
        "seed": seed,
        "scene_type": scene_type,
        "s3_uri": f"s3://{s3_bucket}/{s3_key}",
        "size_bytes": None,
        "duration_seconds": None,
        "error": None,
    }

    started = time.time()
    module = _resolve_module(scene_type)

    output_root = Path(f"/tmp/infinigen_out/seed_{seed}")
    output_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python",
        "-m",
        module,
        "--seed",
        str(seed),
        "--task",
        "coarse",
        "populate",
        "--output_folder",
        str(output_root),
    ]
    if configs:
        cmd.extend(["--configs", *configs])
    if extra_args:
        cmd.extend(extra_args)

    print(f"[seed={seed}] Running: {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            cmd,
            cwd="/opt/infinigen",
            capture_output=True,
            text=True,
            timeout=60 * 60 * 2,
        )
    except subprocess.TimeoutExpired as e:
        result["error"] = f"Infinigen timed out after {e.timeout}s"
        return result

    if proc.returncode != 0:
        result["error"] = (
            f"Infinigen exited with code {proc.returncode}\n"
            f"STDOUT tail:\n{proc.stdout[-2000:]}\n"
            f"STDERR tail:\n{proc.stderr[-2000:]}"
        )
        return result

    # Infinigen writes scene.blend somewhere under output_folder. The exact
    # path depends on the task pipeline, so we glob for it and pick the
    # newest match.
    candidates = sorted(
        output_root.rglob("scene.blend"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        # Fall back to any .blend file the run produced.
        candidates = sorted(
            output_root.rglob("*.blend"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    if not candidates:
        result["error"] = (
            f"No .blend file found under {output_root}. "
            f"Stdout tail:\n{proc.stdout[-1000:]}"
        )
        return result

    blend_path = candidates[0]
    size_bytes = blend_path.stat().st_size
    print(f"[seed={seed}] Found {blend_path} ({size_bytes / 1024 / 1024:.1f} MB)")

    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    try:
        s3.upload_file(
            str(blend_path),
            s3_bucket,
            s3_key,
            ExtraArgs={"ContentType": "application/x-blender"},
        )
    except Exception as e:
        result["error"] = f"S3 upload failed: {e}"
        return result

    result["success"] = True
    result["size_bytes"] = size_bytes
    result["duration_seconds"] = time.time() - started
    print(f"[seed={seed}] Uploaded -> {result['s3_uri']}")
    return result


def generate_scenes_batch(
    scene_type: str,
    seeds: List[int],
    s3_bucket: str,
    s3_prefix: str,
    configs: Optional[List[str]] = None,
    extra_args: Optional[List[str]] = None,
    gpu_type: str = "A10G",
) -> List[Dict[str, Any]]:
    """Fan out scene generation across parallel Modal containers.

    Args:
        scene_type: ``"indoor"``, ``"outdoor"``, or ``"mixed"`` (alternates
            per-seed).
        seeds: List of seeds to generate.
        s3_bucket: Destination S3 bucket.
        s3_prefix: Key prefix; per-scene keys become
            ``{prefix}/{type}/seed_{seed:06d}.blend``.
        configs: Optional gin configs forwarded to every job.
        extra_args: Optional extra Infinigen CLI args forwarded to every job.
        gpu_type: GPU class for the Modal containers (``A10G``, ``A100``, …).

    Returns:
        List of per-seed result dicts (see :func:`generate_scene`).
    """
    if scene_type not in ("indoor", "outdoor", "mixed"):
        raise ValueError("scene_type must be 'indoor', 'outdoor', or 'mixed'")

    s3_prefix = s3_prefix.strip("/")

    def task_for(seed: int):
        st = scene_type
        if st == "mixed":
            st = "outdoor" if seed % 2 == 0 else "indoor"
        key = f"{s3_prefix}/{st}/seed_{seed:06d}.blend"
        return (st, seed, s3_bucket, key, configs, extra_args)

    tasks = [task_for(s) for s in seeds]

    fn = generate_scene
    if gpu_type != "A10G":
        fn = generate_scene.with_options(gpu=gpu_type)

    with app.run():
        return list(fn.starmap(tasks))
