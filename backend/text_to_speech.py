from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
import os

speech_model = "eleven_turbo_v2_5"

voices = {
    "Jessica": "cgSgspJ2msm6clMCkdW9",
    "Charlie": "IKne3meq5aSn9XLyUdCD",
    "Sarah": "EXAVITQu4vr4xnSDxMaL",
    "Roger": "CwhRBWXzGAHq8TQ4Fs17",
    "Harry": "SOYHLrjzK2X1ezoPC6cr",
    "Lily": "pFZP5JQG7iQjIQuC4Bku",
    "Daniel": "onwK4e9ZLuTAKqWW03F9",
}

load_dotenv()
client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY")
)

def gen_audio(text, voice="Rachel", output_path="tmp.mp3"):
    """ Saves the given text as an audio file in static/audio/tmp.mp3 folder using the specified voice. """
    if voice not in voices:
        raise ValueError(f"Voice '{voice}' not found. Available voices: {', '.join(voices.keys())}")

    voice_id = voices[voice]
    try:
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=speech_model
        )

        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        return True
    except Exception as e:
        print(f"Error converting text to speech: {e}")
        return False

def get_all_voices():
    """ Returns a list of all available voices. """
    return list(voices.keys())