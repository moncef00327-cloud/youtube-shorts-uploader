import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

from pipeline import PipelineError, build_workflow, generate_scene, render_video, video_artifacts


class PipelineTests(unittest.TestCase):
    def test_build_workflow_updates_prompt_seed_and_size(self):
        workflow = {
            "1": {"inputs": {"text": "old prompt"}},
            "2": {"inputs": {"seed": 1, "width": 512, "height": 512}},
            "9": {"inputs": {"filename_prefix": "video"}},
        }
        config = {
            "nodes": {
                "prompt": {"id": "1", "input": "text"},
                "seed": {"id": "2", "input": "seed"},
                "width": {"id": "2", "input": "width"},
                "height": {"id": "2", "input": "height"},
                "output": {"id": "9"},
            },
            "generation": {"width": 480, "height": 832},
        }
        result, output_id = build_workflow(
            workflow, config, {"prompt": "new prompt"}, seed=42
        )
        self.assertEqual(result["1"]["inputs"]["text"], "new prompt")
        self.assertEqual(result["2"]["inputs"], {"seed": 42, "width": 480, "height": 832})
        self.assertEqual(workflow["1"]["inputs"]["text"], "old prompt")
        self.assertEqual(output_id, "9")

    def test_video_artifacts_ignore_images(self):
        output = {
            "images": [{"filename": "preview.png"}],
            "videos": [{"filename": "clip.mp4", "subfolder": "shorts"}],
        }
        self.assertEqual(
            list(video_artifacts(output)),
            [{"filename": "clip.mp4", "subfolder": "shorts", "type": "output"}],
        )

    @patch("pipeline.subprocess.run")
    def test_render_video_formats_vertical_mp4(self, run_process):
        run_process.side_effect = [
            SimpleNamespace(returncode=0, stdout="16.0\n", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
        ]
        settings = {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "duration_seconds": 15,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.mp4"
            destination = Path(temp_dir) / "final.mp4"
            render_video("ffmpeg", "ffprobe", source, destination, settings)

        command = run_process.call_args_list[1].args[0]
        self.assertIn("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30", command)
        self.assertEqual(command[command.index("-t") + 1], "15.0")
        self.assertIn("libx264", command)

    @patch("pipeline.subprocess.run")
    def test_render_video_rejects_short_source(self, run_process):
        run_process.return_value = SimpleNamespace(returncode=0, stdout="5.0\n", stderr="")
        settings = {"width": 1080, "height": 1920, "fps": 30, "duration_seconds": 15}
        with self.assertRaises(PipelineError):
            render_video("ffmpeg", "ffprobe", Path("source.mp4"), Path("final.mp4"), settings)
        self.assertEqual(run_process.call_count, 1)

    def test_generate_scene_queues_polls_and_downloads_video(self):
        state = {"workflow": None}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                state["workflow"] = json.loads(body)["prompt"]
                response = json.dumps({"prompt_id": "job-1"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def do_GET(self):
                if urlparse(self.path).path == "/history/job-1":
                    body = json.dumps(
                        {
                            "job-1": {
                                "status": {"completed": True, "status_str": "success"},
                                "outputs": {
                                    "9": {"gifs": [{"filename": "clip.mp4", "type": "output"}]}
                                },
                            }
                        }
                    ).encode()
                    content_type = "application/json"
                else:
                    body = b"fake mp4 bytes"
                    content_type = "video/mp4"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            workflow = {
                "1": {"inputs": {"text": "template"}},
                "9": {"inputs": {"filename_prefix": "video"}},
            }
            config = {
                "nodes": {
                    "prompt": {"id": "1", "input": "text"},
                    "output": {"id": "9"},
                }
            }
            scene = {"id": "test", "file": "test.mp4", "prompt": "test prompt"}
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path, prompt_id = generate_scene(
                    f"http://127.0.0.1:{server.server_port}",
                    workflow,
                    config,
                    scene,
                    7,
                    Path(temp_dir),
                    timeout=2,
                    poll_interval=0.01,
                )
                self.assertEqual(prompt_id, "job-1")
                self.assertEqual(output_path.read_bytes(), b"fake mp4 bytes")
            self.assertEqual(state["workflow"]["1"]["inputs"]["text"], "test prompt")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()