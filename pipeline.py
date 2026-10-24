#!/usr/bin/env python3
"""Generate configured Shorts through ComfyUI and optionally upload them."""

import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv"}


class PipelineError(Exception):
    pass


def load_json(path):
    try:
        with path.open("r", encoding="utf-8") as source:
            return json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"Cannot read JSON file {path}: {exc}") from exc


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def set_workflow_input(workflow, node_config, value, label):
    if not node_config:
        return
    node_id = str(node_config.get("id", ""))
    input_name = node_config.get("input")
    node = workflow.get(node_id)
    if not node or not isinstance(node.get("inputs"), dict):
        raise PipelineError(f"{label} node {node_id!r} was not found in the API workflow.")
    if input_name not in node["inputs"]:
        raise PipelineError(
            f"Input {input_name!r} was not found on {label} node {node_id!r}."
        )
    node["inputs"][input_name] = value


def build_workflow(template, config, scene, seed):
    workflow = copy.deepcopy(template)
    nodes = config.get("nodes", {})
    if not nodes.get("prompt"):
        raise PipelineError("Set nodes.prompt to the text input in the API workflow.")
    set_workflow_input(workflow, nodes["prompt"], scene["prompt"], "prompt")

    if nodes.get("seed"):
        set_workflow_input(workflow, nodes["seed"], seed, "seed")

    generation = config.get("generation", {})
    for name in ("width", "height", "frames"):
        if nodes.get(name) and name in generation:
            set_workflow_input(workflow, nodes[name], generation[name], name)

    output_node = nodes.get("output", {})
    output_id = str(output_node.get("id", ""))
    if not output_id or output_id not in workflow:
        raise PipelineError("Set nodes.output.id to a valid video output node in the API workflow.")
    return workflow, output_id


def request_json(url, payload=None, timeout=30):
    headers = {"Accept": "application/json"}
    body = None
    method = "GET"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PipelineError(f"ComfyUI returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PipelineError(f"ComfyUI request failed at {url}: {exc}") from exc


def video_artifacts(value):
    if isinstance(value, dict):
        filename = value.get("filename")
        if isinstance(filename, str) and Path(filename).suffix.lower() in VIDEO_EXTENSIONS:
            yield {
                "filename": filename,
                "subfolder": value.get("subfolder", ""),
                "type": value.get("type", "output"),
            }
        else:
            for child in value.values():
                yield from video_artifacts(child)
    elif isinstance(value, list):
        for child in value:
            yield from video_artifacts(child)


def wait_for_video(api_url, prompt_id, output_node_id, timeout, poll_interval):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        history = request_json(f"{api_url}/history/{urllib.parse.quote(prompt_id)}")
        entry = history.get(prompt_id)
        if entry:
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise PipelineError(f"ComfyUI workflow failed: {status.get('messages', status)}")
            outputs = entry.get("outputs", {})
            artifacts = list(video_artifacts(outputs.get(output_node_id, {})))
            if len(artifacts) == 1:
                return artifacts[0]
            if len(artifacts) > 1:
                raise PipelineError(
                    f"Output node {output_node_id} produced {len(artifacts)} videos; expected one."
                )
            if status.get("completed"):
                raise PipelineError(
                    f"Workflow completed without a supported video from output node {output_node_id}."
                )
        time.sleep(poll_interval)
    raise PipelineError(f"Timed out waiting for ComfyUI job {prompt_id}.")


def download_video(api_url, artifact, destination):
    query = urllib.parse.urlencode(artifact)
    request = urllib.request.Request(f"{api_url}/view?{query}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise PipelineError(f"ComfyUI video download failed with HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PipelineError(f"Could not download generated video: {exc}") from exc


def render_video(ffmpeg, ffprobe, source, destination, settings):
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode:
        raise PipelineError(f"ffprobe could not inspect {source}: {probe.stderr.strip()}")
    try:
        source_duration = float(probe.stdout.strip())
    except ValueError as exc:
        raise PipelineError(f"ffprobe returned an invalid duration for {source}.") from exc

    duration = float(settings["duration_seconds"])
    if source_duration < duration:
        raise PipelineError(
            f"Generated clip is {source_duration:.1f}s; workflow must generate at least {duration:.1f}s."
        )

    width = int(settings["width"])
    height = int(settings["height"])
    fps = int(settings["fps"])
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps}"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        video_filter,
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    rendered = subprocess.run(command, capture_output=True, text=True, check=False)
    if rendered.returncode:
        raise PipelineError(f"ffmpeg failed for {source}: {rendered.stderr.strip()}")


def generate_scene(api_url, template, config, scene, seed, output_dir, timeout, poll_interval):
    workflow, output_node_id = build_workflow(template, config, scene, seed)
    queued = request_json(
        f"{api_url}/prompt",
        {"prompt": workflow, "client_id": uuid.uuid4().hex},
    )
    if queued.get("node_errors"):
        raise PipelineError(f"ComfyUI rejected the workflow: {queued['node_errors']}")
    prompt_id = queued.get("prompt_id")
    if not prompt_id:
        raise PipelineError(f"ComfyUI did not return a prompt_id: {queued}")

    artifact = wait_for_video(api_url, prompt_id, output_node_id, timeout, poll_interval)
    stem = Path(scene.get("file", scene["id"])).stem
    destination = output_dir / f"{stem}{Path(artifact['filename']).suffix.lower()}"
    download_video(api_url, artifact, destination)
    return destination, prompt_id


def validate_config(config, config_path):
    scenes = config.get("videos")
    if not isinstance(scenes, list) or not scenes:
        raise PipelineError("Config must contain a non-empty 'videos' list.")
    ids = []
    for scene in scenes:
        scene_id = scene.get("id", "")
        if not re.fullmatch(r"[a-z0-9_-]+", scene_id):
            raise PipelineError(f"Invalid scene id: {scene_id!r}.")
        if not scene.get("prompt") or not scene.get("title"):
            raise PipelineError(f"Scene {scene_id!r} needs a prompt and title.")
        ids.append(scene_id)
    if len(ids) != len(set(ids)):
        raise PipelineError("Scene ids must be unique.")

    workflow_path = Path(config.get("workflow_file", ""))
    if not workflow_path.is_absolute():
        workflow_path = config_path.parent / workflow_path
    output_dir = Path(config.get("output_dir", "generated"))
    if not output_dir.is_absolute():
        output_dir = config_path.parent / output_dir
    return workflow_path, output_dir


def make_manifest(scenes, generated, privacy):
    entries = []
    for scene, video_path in zip(scenes, generated):
        entries.append(
            {
                "file": str(video_path.resolve()),
                "title": scene["title"],
                "description": scene.get("description", ""),
                "tags": scene.get("tags", []),
                "privacy": privacy,
                "made_for_kids": scene.get("made_for_kids", True),
            }
        )
    return {"videos": entries}


def run_pipeline(args):
    config_path = args.config.resolve()
    config = load_json(config_path)
    workflow_path, output_dir = validate_config(config, config_path)
    template = load_json(workflow_path)
    seed_base = int(config.get("generation", {}).get("seed", 1))
    for index, scene in enumerate(config["videos"]):
        build_workflow(template, config, scene, seed_base + index)

    if args.upload and args.privacy == "public" and not args.confirm_public:
        raise PipelineError("Public upload requires --confirm-public.")
    if args.dry_run:
        print(f"Validated {len(config['videos'])} scenes and workflow: {workflow_path}")
        return

    render_settings = config.get("render", {})
    render_enabled = render_settings.get("enabled", True) and not args.no_render
    if render_enabled:
        duration = float(render_settings.get("duration_seconds", 15))
        if not 15 <= duration <= 30:
            raise PipelineError("render.duration_seconds must be between 15 and 30 seconds.")
        ffmpeg_name = render_settings.get("ffmpeg", "ffmpeg")
        ffprobe_name = render_settings.get("ffprobe", "ffprobe")
        ffmpeg = shutil.which(ffmpeg_name)
        ffprobe = shutil.which(ffprobe_name)
        if not ffmpeg or not ffprobe:
            raise PipelineError("Rendering requires ffmpeg and ffprobe on PATH; install FFmpeg first.")

    api_url = config.get("comfyui_url", "http://127.0.0.1:8188").rstrip("/")
    timeout = args.timeout
    poll_interval = max(args.poll_interval, 0.1)
    report_path = output_dir / "pipeline_report.json"
    results = []
    generated = []
    raw_dir = output_dir / "raw" if render_enabled else output_dir

    try:
        for index, scene in enumerate(config["videos"]):
            print(f"Generating {index + 1}/{len(config['videos'])}: {scene['id']}")
            video_path, prompt_id = generate_scene(
                api_url,
                template,
                config,
                scene,
                seed_base + index,
                raw_dir,
                timeout,
                poll_interval,
            )
            if render_enabled:
                final_path = output_dir / f"{scene['id']}.mp4"
                render_video(ffmpeg, ffprobe, video_path, final_path, render_settings)
            else:
                final_path = video_path
            generated.append(final_path)
            results.append({"id": scene["id"], "status": "generated", "file": str(final_path)})
            write_json(report_path, {"status": "generating", "results": results})
            print(f"Generated {final_path} (job {prompt_id})")

        manifest_path = output_dir / "upload_config.json"
        write_json(manifest_path, make_manifest(config["videos"], generated, args.privacy))
        report = {"status": "generated", "results": results, "manifest": str(manifest_path)}

        if args.upload:
            uploader = ROOT / config.get("uploader_script", "upload_shorts.py")
            command = [
                sys.executable,
                str(uploader),
                "--config",
                str(manifest_path),
                "--privacy",
                args.privacy,
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            report["upload_output"] = completed.stdout + completed.stderr
            if completed.returncode:
                report["status"] = "upload_failed"
                write_json(report_path, report)
                raise PipelineError(
                    f"Uploader exited with code {completed.returncode}; see {report_path}."
                )
            report["status"] = "uploaded"
            report["video_urls"] = re.findall(
                r"https://www\.youtube\.com/shorts/[A-Za-z0-9_-]+",
                report["upload_output"],
            )

        write_json(report_path, report)
        print(f"Pipeline report: {report_path}")
        print(f"Upload manifest: {manifest_path}")
    except Exception as exc:
        write_json(report_path, {"status": "failed", "results": results, "error": str(exc)})
        raise


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate the configured Shorts through ComfyUI; upload only when requested."
    )
    parser.add_argument("--config", type=Path, default=ROOT / "pipeline.example.json")
    parser.add_argument("--timeout", type=int, default=1800, help="Seconds to wait per video.")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--privacy", choices=("private", "unlisted", "public"), default="unlisted")
    parser.add_argument("--upload", action="store_true", help="Upload generated files with upload_shorts.py.")
    parser.add_argument("--confirm-public", action="store_true", help="Confirm public video publishing.")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and workflow without contacting ComfyUI.")
    parser.add_argument("--no-render", action="store_true", help="Keep the ComfyUI output without FFmpeg conversion.")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        run_pipeline(args)
    except PipelineError as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())