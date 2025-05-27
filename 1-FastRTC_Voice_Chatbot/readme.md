# Real-time Voice Chatbot with Math Agent

## Overview
This project implements a real-time voice-activated chatbot named "Samantha." Samantha is designed as a helpful math assistant capable of understanding spoken queries, performing basic arithmetic operations (addition and multiplication), and responding verbally.

The system leverages:
- **FastRTC**: For real-time audio communication.
- **Groq API**: For fast Speech-to-Text (STT) via Whisper and Text-to-Speech (TTS) via PlayAI.
- **Google Agent Development Kit (ADK)**: For the conversational agent logic ("Samantha").

## Features
- Real-time voice interaction.
- Speech-to-Text (STT) using Groq's Whisper model.
- Conversational AI agent ("Samantha") built with Google ADK.
- Agent equipped with tools for mathematical calculations (sum, multiply).
- Text-to-Speech (TTS) using Groq's PlayAI model.
- Supports interaction via a Gradio web UI or a FastRTC phone interface.
- Session management for maintaining conversation context.

## Core Components

*   **`src/fast_stt.py`**:
    *   The main application script.
    *   Handles real-time audio streaming using FastRTC.
    *   Performs STT by sending audio to the Groq API.
    *   Orchestrates interaction with the "Samantha" agent.
    *   Initiates TTS by sending the agent's text response to the Groq API.
    *   Provides options to launch with a Gradio UI or a phone interface.

*   **`src/agent.py`**:
    *   Defines the "Samantha" AI agent using the Google Agent Development Kit (ADK).
    *   Configures the agent with a LiteLLM model pointing to a Groq model (e.g., `groq/llama-3.1-8b-instant`).
    *   Equips the agent with tools: `sum_numbers` and `multiply_numbers`.
    *   Includes a system prompt to define Samantha's personality (warm, helpful math assistant) and instructions (use tools for math, audio-friendly output).
    *   Manages agent sessions using `InMemorySessionService`.

*   **`src/tts.py`**:
    *   A utility module for processing the TTS audio stream received from the Groq API.
    *   Saves the audio to a temporary WAV file and then reads it into a format suitable for playback (sample rate and audio data as a NumPy array).

## How it Works
1.  **Voice Input**: The user speaks. Audio is captured by the FastRTC stream.
2.  **Speech-to-Text (STT)**: The captured audio is sent to the Groq API (Whisper model) and transcribed into text.
3.  **Agent Processing**: The transcribed text (user's query) is passed to the "Samantha" agent. The ADK agent processes the query, using its LLM and tools (e.g., `sum_numbers`, `multiply_numbers`) if required, to formulate a response.
4.  **Text-to-Speech (TTS)**: The agent's textual response is sent to the Groq API (PlayAI TTS model) to generate speech.
5.  **Voice Output**: The generated audio, processed by `tts.py`, is streamed back to the user for playback.

## Setup & Prerequisites
- A Python environment.
- Required Python libraries (e.g., `fastrtc`, `openai` client for Groq, `google-adk`, `loguru`, `numpy`). You may need to install them via pip:
  ```bash
  pip install fastrtc openai google-adk loguru numpy
  ```
- **`GROQ_API_KEY`**: An environment variable must be set with your valid Groq API key.

## Running the Application
The application is launched using the `fast_stt.py` script from the `src` directory.

1.  Navigate to the project's root directory.
2.  Run the script:
    ```bash
    python src/fast_stt.py
    ```
    This will typically launch the application with a Gradio web interface.

3.  To launch with the FastRTC phone interface (which provides a temporary phone number for interaction):
    ```bash
    python src/fast_stt.py --phone
    ```