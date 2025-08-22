Here’s a detailed, blog‑ready walkthrough of the project. It keeps the big picture simple while diving into what actually happens under the hood.

# AutoLecture Notes — How it works (deep dive)

## 1) Configuration & Client Selection (.env → Client Factory)

* All settings come from a **`.env`** file using `python-dotenv`. You choose the provider and models without touching code.
* Key vars:

  * `CLIENT=azure` **or** `CLIENT=openai` (for OpenAI‑compatible hosts like Groq)
  * If `CLIENT=openai`: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_CHAT_MODEL`, `OPENAI_WHISPER_MODEL` (if supported)
  * If `CLIENT=azure`: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, `AZURE_GPT_DEPLOYMENT`, `AZURE_WHISPER_DEPLOYMENT`
  * IO: `INPUT_FOLDER`, `OUTPUT_DIR`
* A tiny **client factory** wires the right SDK:

  * **Azure path**: `AzureOpenAI(azure_endpoint, api_key, api_version)`
  * **OpenAI‑compatible path**: `OpenAI(base_url, api_key)`
* A **single wrapper** is used for:

  * `chat.completions.create(...)` to generate the blog
  * `audio.transcriptions.create(...)` to transcribe (if your OpenAI‑compatible host supports it)

> Why this matters: You can swap vendors (Azure ↔ Groq) by changing `.env`. The business logic stays untouched.

---

## 2) Orchestration via LangGraph (Stateful, Modular, Testable)

The pipeline is modeled as a **LangGraph** state machine with clear nodes. Each node is a pure function that:

* reads a typed state (`WorkflowState`)
* does one focused job
* returns the updated state

### Nodes (in order)

1. `convert_video_to_audio` — Extracts `.mp3` from `.mp4` using **ffmpeg**
2. `probe_media` — Reads duration using **ffprobe**
3. `split_audio` — Slices the audio into ≤ \~25MB chunks (time‑based segmentation)
4. `transcribe_chunks` — Sends each chunk to Whisper (Azure or OpenAI‑compatible)
5. `merge_transcripts` — Concatenates chunk transcripts into a single text
6. `llm_format_blog` — Uses a chat model to rewrite transcript into a clean Markdown blog
7. `write_markdown` — Saves output to `OUTPUT_DIR/<video-name>.md`
8. `cleanup` — Deletes temporary audio parts

> Why LangGraph: You get **deterministic flow**, centralized state, and easy unit testing per node.

---

## 3) Tools Layer (LocalToolBus, no MCP)

* A tiny **LocalToolBus** encapsulates system interactions:

  * `run_shell(cmd)` → wraps `subprocess.run` for `ffmpeg`/`ffprobe`
  * `write_text(path, text)` / `file_size(path)` / `remove_file(path)`
* At startup, it **warns** if `ffmpeg` or `ffprobe` are missing from PATH (can be made strict).

> Why a ToolBus: Keeps your nodes clean and makes it easy to add a remote or sandboxed implementation later without touching the graph.

---

## 4) Video → Audio Conversion (ffmpeg)

* `ffmpeg` is called to produce a standard `.mp3` with:

  * stereo channels (`-ac 2`)
  * 44.1kHz sampling (`-ar 44100`)
  * 192kbps bitrate (`-b:a 192k`)
* Output is a temp file like `temp_<basename>_<uuid>.mp3`, stored alongside the script for easy cleanup.

**Edge cases handled**

* If `ffmpeg` fails, the node raises an error (the driver prints the failure and continues to the next file).

---

## 5) Intelligent Chunking (Size‑aware, Time‑based)

* Providers often cap audio uploads around **25MB**. We:

  1. Read **total file size** and **duration (sec)**.
  2. Compute `num_chunks = ceil(total_size / limit)` (limit ≈ 25MB).
  3. Compute `chunk_duration = total_duration / num_chunks`.
  4. Use `ffmpeg` with `-ss` and `-t` to cut **time slices** that roughly match the target size.
* We **warn** if any chunk still exceeds the limit (rare, but can happen due to codec overhead).

**Why time‑based?**
It’s fast and codec‑safe (no re‑encoding) using `-acodec copy`. True size‑perfect splitting would require bitrate analysis or re‑encoding, which increases complexity and CPU cost.

---

## 6) Transcription (Whisper on Azure or OpenAI‑compatible)

* Each chunk is uploaded using the provider’s **audio transcription** endpoint.
* A small **retry** decorator handles transient errors (network hiccups / provider timeouts).
* If your OpenAI‑compatible host **doesn’t** support `/audio/transcriptions`, the code raises a clear error so you can:

  * switch `CLIENT=azure` for Whisper, or
  * plug in a local ASR (e.g., `faster-whisper`) as an alternative node.

**Result:** A list of chunk‑level transcripts that we concatenate in the next step.

---

## 7) Transcript → Polished Blog (Chat Completions)

* The merged transcript goes to a **chat model** with a system prompt that asks for:

  * **Markdown** with headings (`##`)
  * Clear sections
  * **Mermaid diagrams or HTML snippets** when helpful
  * A **“Tips and Tricks”** section at the end
  * Python samples with **type hints**
* The output is post‑processed to strip any stray `<think>...</think>` artifacts.
* We wrap it with a file header and separator for consistent formatting and save as `<video-name>.md`.

**Why chat instead of instruct?**
Chat messages (system + user) provide more control over tone and structure, and are well supported by both Azure and OpenAI‑compatible providers.

---

## 8) Cleanup & Robustness

* Temporary chunk files are removed.
* If the audio wasn’t split (single chunk), we keep it or remove based on whether it’s a generated temp file.
* Every node prints compact logs (`[convert]`, `[probe]`, `[split]`, etc.) so you can follow progress across many videos.

---

## The whole pipeline at a glance

```mermaid
flowchart LR
    A[.env (CLIENT, keys, models, IO paths)] --> B[Client Factory (Azure or OpenAI-compatible)]
    B --> C[LangGraph Workflow]
    C --> C1[convert_video_to_audio (ffmpeg)]
    C1 --> C2[probe_media (ffprobe)]
    C2 --> C3[split_audio (≤ ~25MB parts)]
    C3 --> C4[transcribe_chunks (Whisper)]
    C4 --> C5[merge_transcripts]
    C5 --> C6[llm_format_blog (Chat Completions)]
    C6 --> C7[write_markdown]
    C7 --> C8[cleanup]
```

---

## Practical tips & tunables

* **Larger files**: if you regularly hit the 25MB limit, consider:

  * lowering target bitrate in the initial `ffmpeg` extraction (smaller mp3s),
  * or re‑encoding chunks to a **CBR** bitrate to control size tightly.
* **Provider mismatch**: You can mix and match:

  * Use **Azure** for transcription (Whisper) and **OpenAI‑compatible** for blog generation by running the pipeline twice or splitting nodes—thanks to the clean node boundaries, this is straightforward.
* **Latency vs. quality**: Set `temperature=0.3–0.7` depending on how creative you want the blog to be. Lower = safer.
* **Observability**: The current logs are simple `print`s. If you want structured logs, wrap each node with a tiny logger that records timings and outcomes per video.

---

## TL;DR (one‑liner)

A **LangGraph‑orchestrated** pipeline that turns **videos into polished Markdown blogs** by extracting audio, **chunk‑safe transcribing** with Whisper, and **GPT‑formatting** the transcript—configurable via **`.env`** to run on **Azure** or **OpenAI‑compatible** providers.
