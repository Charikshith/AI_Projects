import os
import tempfile
import wave
from typing import Any, Generator , Tuple

import numpy as np

def process_tts(tts_reponse:Any, ) -> Generator[Tuple[int, np.ndarray], None,None]:
    """
    Process Groq TTS response into a complete audio segement.
    This function reads the entire audio file and yields it as one piece.

    Args:
        tts_reponse (Any): Groq TTS response

    Yields:
        A single tuple of (sample_rate, audio_data) for audio playback
    """

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_file_path = temp_file.name
    temp_file.close()


    try:
        tts_reponse.write_to_file(temp_file_path)
        
        with wave.open(temp_file_path, "rb") as wf:
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            audio_data = wf.readframes(n_frames)

        audio_array = np.frombuffer(audio_data, dtype=np.int16).reshape(1,-1)
        yield (sample_rate, audio_array)

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
    
