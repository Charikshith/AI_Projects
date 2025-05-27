import argparse,os,uuid
from typing import Generator, Tuple

import numpy as np
from fastrtc import AlgoOptions, ReplyOnPause, Stream,audio_to_bytes
from openai import AsyncOpenAI

from loguru import logger

from tts import process_tts
from agent import agent_config , samantha_adk_agent,chat_with_samantha ,runner

logger.remove()
logger.add( lambda msg: print(msg), colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level}</level> | <level>{message}</level>")

client = AsyncOpenAI(api_key=os.getenv("GROQ_API_KEY"),base_url="https://api.groq.com/openai/v1/models")

def response(audio:tuple[int,np.ndarray])-> Generator[Tuple[int,np.ndarray],None,None]:
    """
    Process audio input , transcibe it, generate a response and deliver TTS audio output.
    Args:
        audio: Tuple contains sample rate and audio data
    Yields:
        Tuples of ( sample_rate, audio_array) for audio playback
    """
    logger.info(" Received audio input")

    logger.debug(" Transcribing audio...")

    transcript = client.audio.transcriptions.create(
        file=("audio-file.mp3", audio_to_bytes(audio)),
        model="whisper-large-v3-turbo",response_format="text")
    
    logger.info(f'👂 Transcribed: "{transcript}"')

    logger.debug("🧠 Running agent...")

    user_1_id = "math_enthusiast_001"
    session_1_id = str(uuid.uuid4())

    logger.info(f"Created new session {session_1_id} for user {user_1_id}")
    agent_response = chat_with_samantha(query= transcript,runner_instance=runner,session_id=session_1_id,user_id=user_1_id)

    logger.info(f'💬 Response: "{agent_response}"')

    logger.debug("🔊 Generating speech...")
    tts_response = client.audio.speech.create(
        model="playai-tts",
        voice="Celeste-PlayAI",
        response_format="wav",
        input=agent_response,
    )
    yield from process_tts(tts_response)

def create_stream() -> Stream:
    """
    Create and configure a Stream instance with audio capabilities.

    Returns:
        Stream: Configured FastRTC Stream instance
    """
    return Stream(
        modality="audio",
        mode="send-receive",
        handler=ReplyOnPause(
            response,
            algo_options=AlgoOptions(
                speech_threshold=0.5,
            ),
        ),
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice Agent")
    parser.add_argument(
        "--phone",
        action="store_true",
        help="Launch with FastRTC phone interface (get a temp phone number)",
    )
    args = parser.parse_args()

    stream = create_stream()
    logger.info("🎧 Stream handler configured")

    if args.phone:
        logger.info("🌈 Launching with FastRTC phone interface...")
        stream.fastphone()
    else:
        logger.info("🌈 Launching with Gradio UI...")
        stream.ui.launch()