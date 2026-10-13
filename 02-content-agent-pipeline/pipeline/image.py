"""Шаг 3. Картинка к посту через ComfyUI HTTP API (локальный Stable Diffusion)."""
import json
import random
import time
import uuid
from pathlib import Path

import requests

PROMPT_PLACEHOLDER = "{{PROMPT}}"


class ImageError(RuntimeError):
    pass


def build_workflow(template_path: Path, prompt: str) -> dict:
    """Шаблон — workflow, сохранённый из ComfyUI через «Save (API Format)».
    В текстовом узле позитивного промпта стоит {{PROMPT}}."""
    raw = template_path.read_text(encoding="utf-8")
    if PROMPT_PLACEHOLDER not in raw:
        raise ImageError(f"В {template_path.name} нет плейсхолдера {PROMPT_PLACEHOLDER}")
    wf = json.loads(raw.replace(PROMPT_PLACEHOLDER, json.dumps(prompt)[1:-1]))
    for node in wf.values():                     # новый seed на каждый запуск
        if node.get("class_type") == "KSampler":
            node["inputs"]["seed"] = random.randint(0, 2**32 - 1)
    return wf


def generate(comfy_url: str, template_path: Path, prompt: str, out_dir: Path,
             timeout: int = 300) -> Path:
    wf = build_workflow(template_path, prompt)
    r = requests.post(f"{comfy_url}/prompt", json={"prompt": wf, "client_id": str(uuid.uuid4())}, timeout=30)
    if r.status_code != 200:
        raise ImageError(f"ComfyUI /prompt {r.status_code}: {r.text[:300]}")
    prompt_id = r.json()["prompt_id"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        hist = requests.get(f"{comfy_url}/history/{prompt_id}", timeout=30).json()
        if prompt_id in hist:
            for node_out in hist[prompt_id]["outputs"].values():
                for img in node_out.get("images", []):
                    data = requests.get(f"{comfy_url}/view", params={
                        "filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]},
                        timeout=60).content
                    out_dir.mkdir(parents=True, exist_ok=True)
                    path = out_dir / img["filename"]
                    path.write_bytes(data)
                    return path
            raise ImageError("ComfyUI завершил задачу, но изображений в ответе нет")
        time.sleep(2)
    raise ImageError(f"ComfyUI не ответил за {timeout} с")
