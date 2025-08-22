"""
AutoLecture Notes — dual client (Azure / OpenAI-compatible) via .env

- Orchestration: LangGraph
- Tools: local subprocess (ffmpeg/ffprobe) + filesystem
- LLM (blog): Azure Chat Completions OR OpenAI-compatible Chat Completions (base_url + api_key)
- ASR (transcription): Azure Whisper OR OpenAI-compatible /audio/transcriptions (if supported)

.env (example):
  CLIENT=openai                   # or azure
  # OpenAI-compatible (e.g., Groq):
  OPENAI_API_KEY=your_key
  OPENAI_BASE_URL=https://api.groq.com/openai/v1
  OPENAI_CHAT_MODEL=llama-3.1-70b-versatile
  OPENAI_WHISPER_MODEL=whisper-large-v3     # if provider supports audio.transcriptions; else leave blank
  # Azure:
  AZURE_OPENAI_API_KEY=your_azure_key
  AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
  AZURE_OPENAI_API_VERSION=2024-12-01-preview
  AZURE_WHISPER_DEPLOYMENT=whisper
  AZURE_GPT_DEPLOYMENT=gpt-4.1
  # IO:
  INPUT_FOLDER=D:\\Path\\To\\Input\\Videos
  OUTPUT_DIR=D:\\Path\\To\\Output\\Markdown
"""

import os
import re
import math
import time
import uuid
import yaml
import warnings
import subprocess
from typing import TypedDict, List, Dict, Any, Tuple

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# LLM clients
from openai import OpenAI            # OpenAI-compatible client (works with custom base_url)
from openai import AzureOpenAI       # Azure client

# =========================
# Env & Config
# =========================

load_dotenv()  # load .env into environment

CLIENT = os.getenv("CLIENT", "openai").strip().lower()   # "azure" or "openai"

# OpenAI-compatible
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL  = os.getenv("OPENAI_BASE_URL", "")      # e.g., https://api.groq.com/openai/v1
OPENAI_CHAT_MODEL= os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_WHISPER_MODEL = os.getenv("OPENAI_WHISPER_MODEL", "")  # blank if provider doesn't support transcriptions

# Azure
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT= os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_API_VERSION    = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
AZURE_WHISPER_DEPLOYMENT = os.getenv("AZURE_WHISPER_DEPLOYMENT", "whisper")
AZURE_GPT_DEPLOYMENT     = os.getenv("AZURE_GPT_DEPLOYMENT", "gpt-4.1")

# IO
INPUT_FOLDER = os.getenv("INPUT_FOLDER", r"D:\Path\To\Input\Videos")
OUTPUT_DIR   = os.getenv("OUTPUT_DIR", r"D:\Path\To\Output\Markdown")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Basic validation
if CLIENT not in ("azure", "openai"):
    raise RuntimeError("CLIENT must be 'azure' or 'openai' in .env")

if CLIENT == "openai":
    if not OPENAI_API_KEY or not OPENAI_BASE_URL:
        raise RuntimeError("For CLIENT=openai, set OPENAI_API_KEY and OPENAI_BASE_URL in .env")
else:
    if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
        raise RuntimeError("For CLIENT=azure, set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT in .env")

# =========================
# Local ToolBus (no MCP)
# =========================

class LocalToolBus:
    """Minimal local tool adapter (no MCP)."""

    def __init__(self, fail_if_missing: bool = False):
        self._check_ffmpeg(ffmpeg_required=fail_if_missing)

    @staticmethod
    def _check_ffmpeg(ffmpeg_required: bool) -> None:
        missing = []
        for tool in ("ffmpeg", "ffprobe"):
            try:
                subprocess.run([tool, "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                missing.append(tool)
        if missing:
            msg = f"{' and '.join(missing)} not found on PATH. Install them for audio/video processing."
            if ffmpeg_required:
                raise RuntimeError(msg)
            warnings.warn(msg, RuntimeWarning)

    @staticmethod
    def run_shell(cmd: List[str]) -> Tuple[int, str, str]:
        try:
            p = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return p.returncode, p.stdout, p.stderr
        except Exception as e:
            return 1, "", f"[subprocess error] {e}"

    @staticmethod
    def write_text(path: str, text: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    @staticmethod
    def file_size(path: str) -> int:
        return os.path.getsize(path)

    @staticmethod
    def remove_file(path: str) -> None:
        if os.path.exists(path):
            os.remove(path)

toolbus = LocalToolBus(fail_if_missing=False)

# =========================
# Helpers
# =========================

def bytes_limit() -> int:
    """Typical Whisper per-file limit (~25MB). Adjust if your provider differs."""
    return 25 * 1024 * 1024

def retry(times: int = 3, delay: float = 1.2):
    def deco(fn):
        def wrap(*args, **kwargs):
            last = None
            for i in range(times):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last = e
                    time.sleep(delay * (i + 1))
            raise last
        return wrap
    return deco

def clean_think_tags(md: str) -> str:
    return re.sub(r'<think>.*?</think>', '', md, flags=re.DOTALL | re.IGNORECASE)

# =========================
# Client Factories (Azure / OpenAI-compatible)
# =========================

def get_chat_markdown(transcript: str) -> str:
    """
    Calls the chosen provider's chat completions to format the blog.
    """
    system_prompt = (
        "You are a professional blog writer and expert in Python. "
        "Convert the following video transcript into a well-structured blog post in Markdown. "
        "Use headings (##), sections, mermaid diagrams or HTML snippets where helpful. "
        "End with a 'Tips and Tricks' section. Use type hints in Python code examples."
    )

    if CLIENT == "azure":
        client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        resp = client.chat.completions.create(
            model=AZURE_GPT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript}
            ],
            temperature=0.7
        )
        return resp.choices[0].message.content

    # OpenAI-compatible
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    resp = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript}
        ],
        temperature=0.7
    )
    return resp.choices[0].message.content

@retry(times=3, delay=1.5)
def transcribe_file(audio_path: str) -> str:
    """
    Transcribe a single audio file with the selected provider.
    For OpenAI-compatible: provider must implement /audio/transcriptions.
    """
    if toolbus.file_size(audio_path) > bytes_limit():
        raise RuntimeError(f"Chunk {audio_path} exceeds typical 25MB limit.")

    if CLIENT == "azure":
        client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        with open(audio_path, "rb") as f:
            res = client.audio.transcriptions.create(
                file=f, model=AZURE_WHISPER_DEPLOYMENT
            )
        return getattr(res, "text", str(res))

    # OpenAI-compatible
    if not OPENAI_WHISPER_MODEL:
        raise RuntimeError(
            "OPENAI_WHISPER_MODEL not set or provider doesn't support /audio/transcriptions. "
            "Provide a model in .env or swap to an external ASR."
        )
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    with open(audio_path, "rb") as f:
        res = client.audio.transcriptions.create(file=f, model=OPENAI_WHISPER_MODEL)
    return getattr(res, "text", str(res))

# =========================
# Workflow State & Nodes
# =========================

class WorkflowState(TypedDict, total=False):
    video_path: str
    base_name: str
    temp_audio_path: str
    duration_sec: float
    chunks: List[str]
    transcripts: List[str]
    full_transcript: str
    blog_markdown: str
    output_markdown_path: str

def convert_video_to_audio(state: WorkflowState) -> WorkflowState:
    """Extract mp3 audio from mp4 via ffmpeg."""
    video_path = state["video_path"]
    base = os.path.splitext(os.path.basename(video_path))[0]
    out_mp3 = os.path.join(os.getcwd(), f"temp_{base}_{uuid.uuid4().hex[:8]}.mp3")

    cmd = ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "libmp3lame",
           "-ar", "44100", "-ac", "2", "-b:a", "192k", out_mp3]
    rc, _, err = toolbus.run_shell(cmd)
    if rc != 0:
        raise RuntimeError(f"ffmpeg convert failed: {err}")
    print(f"[convert] {os.path.basename(video_path)} → {os.path.basename(out_mp3)}")
    state["temp_audio_path"] = out_mp3
    return state

def probe_media(state: WorkflowState) -> WorkflowState:
    """Get audio duration via ffprobe."""
    audio = state["temp_audio_path"]
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", audio]
    rc, out, err = toolbus.run_shell(cmd)
    if rc != 0:
        raise RuntimeError(f"ffprobe failed: {err}")
    try:
        duration = float(out.strip())
    except Exception:
        duration = 0.0
    state["duration_sec"] = duration
    size_mb = toolbus.file_size(audio) / (1024 * 1024)
    print(f"[probe] duration={duration:.2f}s size={size_mb:.2f}MB")
    return state

def split_audio(state: WorkflowState) -> WorkflowState:
    """Split audio into ≤ ~25MB chunks by slicing time proportionally to size."""
    audio = state["temp_audio_path"]
    total_size = toolbus.file_size(audio)
    limit = bytes_limit()
    if total_size <= limit:
        state["chunks"] = [audio]
        print("[split] single chunk (<= limit)")
        return state

    num_chunks = max(1, math.ceil(total_size / limit))
    duration = max(1.0, state.get("duration_sec", 1.0))
    chunk_duration = duration / num_chunks

    chunk_paths: List[str] = []
    for i in range(num_chunks):
        start = i * chunk_duration
        out_chunk = os.path.join(
            os.getcwd(), f"{os.path.splitext(os.path.basename(audio))[0]}_part{i}.mp3"
        )
        cmd = ["ffmpeg", "-y", "-i", audio, "-ss", str(start), "-t", str(chunk_duration),
               "-acodec", "copy", out_chunk]
        rc, _, err = toolbus.run_shell(cmd)
        if rc != 0:
            raise RuntimeError(f"ffmpeg split failed: {err}")
        if toolbus.file_size(out_chunk) > limit:
            warnings.warn(f"[split] chunk {out_chunk} still exceeds limit.")
        chunk_paths.append(out_chunk)

    state["chunks"] = chunk_paths
    print(f"[split] created {len(chunk_paths)} chunks")
    return state

def transcribe_chunks(state: WorkflowState) -> WorkflowState:
    texts: List[str] = []
    chunks = state["chunks"]
    for i, c in enumerate(chunks, 1):
        print(f"[transcribe] {i}/{len(chunks)} {os.path.basename(c)}")
        texts.append(transcribe_file(c))
    state["transcripts"] = texts
    return state

def merge_transcripts(state: WorkflowState) -> WorkflowState:
    state["full_transcript"] = " ".join(state.get("transcripts", [])).strip()
    print(f"[merge] transcript length={len(state['full_transcript'])} chars")
    return state

def llm_format_blog(state: WorkflowState) -> WorkflowState:
    md = get_chat_markdown(state["full_transcript"])
    md = clean_think_tags(md)
    state["blog_markdown"] = f"\n\n## Output for {state['base_name']}\n\n{md}\n\n---\n"
    print(f"[format] blog markdown ready ({len(state['blog_markdown'])} chars)")
    return state

def write_markdown(state: WorkflowState) -> WorkflowState:
    out_path = os.path.join(OUTPUT_DIR, f"{state['base_name']}.md")
    toolbus.write_text(out_path, state["blog_markdown"])
    state["output_markdown_path"] = out_path
    print(f"[write] saved → {out_path}")
    return state

def cleanup(state: WorkflowState) -> WorkflowState:
    audio = state.get("temp_audio_path")
    chunks = state.get("chunks", [])
    for c in chunks:
        if c != audio and os.path.exists(c):
            toolbus.remove_file(c)
    if audio and os.path.exists(audio) and (len(chunks) > 1 or (chunks and chunks[0] != audio)):
        toolbus.remove_file(audio)
    print("[cleanup] temp files removed (if any)")
    return state

# =========================
# Graph
# =========================

def build_graph():
    g = StateGraph(WorkflowState)
    g.add_node("convert_video_to_audio", convert_video_to_audio)
    g.add_node("probe_media", probe_media)
    g.add_node("split_audio", split_audio)
    g.add_node("transcribe_chunks", transcribe_chunks)
    g.add_node("merge_transcripts", merge_transcripts)
    g.add_node("llm_format_blog", llm_format_blog)
    g.add_node("write_markdown", write_markdown)
    g.add_node("cleanup", cleanup)

    g.set_entry_point("convert_video_to_audio")
    g.add_edge("convert_video_to_audio", "probe_media")
    g.add_edge("probe_media", "split_audio")
    g.add_edge("split_audio", "transcribe_chunks")
    g.add_edge("transcribe_chunks", "merge_transcripts")
    g.add_edge("merge_transcripts", "llm_format_blog")
    g.add_edge("llm_format_blog", "write_markdown")
    g.add_edge("write_markdown", "cleanup")
    g.add_edge("cleanup", END)

    return g.compile()

def process_video(video_path: str):
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    graph = build_graph()
    initial: WorkflowState = {"video_path": video_path, "base_name": base_name}
    final = graph.invoke(initial)
    return final

def main():
    if not os.path.isdir(INPUT_FOLDER):
        raise RuntimeError(f"INPUT_FOLDER not found: {INPUT_FOLDER}")

    videos = [
        os.path.join(INPUT_FOLDER, fn)
        for fn in os.listdir(INPUT_FOLDER)
        if fn.lower().endswith(".mp4")
    ]
    if not videos:
        print("No .mp4 files found.")
        return

    print(f"Found {len(videos)} videos. CLIENT={CLIENT}")
    for v in videos:
        print(f"\n=== Processing: {os.path.basename(v)} ===")
        try:
            process_video(v)
        except Exception as e:
            print(f"[error] {os.path.basename(v)}: {e}")

    print("\nAll videos processed!")

if __name__ == "__main__":
    main()
    print("DONE-123")
