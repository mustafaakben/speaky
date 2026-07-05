"""speaky: speak text out loud to the user through their speakers.

Two modes:
  * premium  - Gemini TTS (expressive: honors emotion tags like [hesitant]
               and fillers such as "hmm"/"umm"). Requires GEMINI_API_KEY.
  * native   - the operating system's built-in terminal speech synthesizer
               (macOS `say`, Windows System.Speech, Linux `spd-say`/`espeak`).
               No API key, no network. Emotion tags are stripped first.
  * auto     - premium if GEMINI_API_KEY is set, otherwise native (default).

Cross-platform: Windows, macOS, and Linux. If premium fails for any reason
(no key, network, quota), it falls back to native so the user always hears
*something*.

Usage:
    python speak.py "Text to say out loud"
    python speak.py "Text" --mode native
    python speak.py "Text" --style "calm, slow, late-night radio"
    python speak.py "Text" --voice Enceladus --no-beep
    python speak.py "Text" --no-play          # generate WAV only (premium)
"""

import argparse
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

DEFAULT_MODEL = "gemini-3.1-flash-tts-preview"
DEFAULT_VOICE = os.environ.get("SPEAKY_VOICE", "Enceladus")
DEFAULT_STYLE = os.environ.get(
    "SPEAKY_STYLE",
    'The "Vocal Smile": soft palate raised to keep the tone bright, sunny, '
    "and inviting. Warm North Carolina flavor - friendly, enthusiastic, "
    "direct. Fast, energetic pace, no dead air.",
)

# The 30 Gemini prebuilt voices (astronomical names).
ALL_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]

# Friendly aliases so you don't have to memorize astronomical names.
# Pass e.g. `--voice warm`; unknown values fall through to Gemini as-is.
VOICE_ALIASES = {
    "warm": "Sulafat",
    "deep": "Charon",
    "energetic": "Fenrir",
    "bright": "Zephyr",
    "upbeat": "Puck",
    "friendly": "Achird",
    "gentle": "Vindemiatrix",
    "firm": "Kore",
    "smooth": "Algieba",
    "default": "Enceladus",
}

# Model aliases. 2.5-flash has a free tier; 3.1-flash is the most expressive.
MODEL_ALIASES = {
    "flash": "gemini-3.1-flash-tts-preview",
    "3.1": "gemini-3.1-flash-tts-preview",
    "free": "gemini-2.5-flash-preview-tts",
    "2.5-flash": "gemini-2.5-flash-preview-tts",
    "pro": "gemini-2.5-pro-preview-tts",
}


def resolve_voice(value: str) -> str:
    return VOICE_ALIASES.get(value.lower(), value)


def resolve_model(value: str) -> str:
    return MODEL_ALIASES.get(value.lower(), value)


PROMPT_TEMPLATE = """Read the following transcript based on the director's note.

# Director's note
Style: {style}

## Scene:
coding agent talking to its human teammate

## Transcript:
{text}"""

SYSTEM = platform.system()  # "Windows", "Darwin", "Linux"

# Emotion tags like [hesitant] / [excited] are premium-only cues for Gemini.
# In native mode they'd be read aloud literally, so we strip them first.
_EMOTION_TAG = re.compile(r"\[[^\]\n]{0,40}\]")


def strip_expressive(text: str) -> str:
    """Remove bracketed emotion tags so native TTS never reads them aloud."""
    return re.sub(r"\s{2,}", " ", _EMOTION_TAG.sub("", text)).strip()


# --------------------------------------------------------------------------- #
# Gemini (premium) - kept as-is                                               #
# --------------------------------------------------------------------------- #
def build_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Wrap raw PCM chunks from Gemini in a WAV header."""
    bits_per_sample, rate = 16, 24000
    for param in mime_type.split(";"):
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate = int(param.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass
    byte_rate = rate * bits_per_sample // 8
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(audio_data), b"WAVE", b"fmt ", 16, 1, 1,
        rate, byte_rate, bits_per_sample // 8, bits_per_sample,
        b"data", len(audio_data),
    )
    return header + audio_data


def generate_speech(text: str, style: str, voice: str, model: str) -> bytes:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        temperature=1,
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
    )
    pcm = bytearray()
    mime = "audio/L16;rate=24000"
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=[types.Content(
            role="user",
            parts=[types.Part.from_text(
                text=PROMPT_TEMPLATE.format(style=style, text=text)
            )],
        )],
        config=config,
    ):
        if not chunk.parts:
            continue
        part = chunk.parts[0]
        if part.inline_data and part.inline_data.data:
            pcm.extend(part.inline_data.data)
            mime = part.inline_data.mime_type or mime
    if not pcm:
        raise RuntimeError("Gemini returned no audio data")
    if "wav" in mime:
        return bytes(pcm)
    return build_wav(bytes(pcm), mime)


# --------------------------------------------------------------------------- #
# Cross-platform playback                                                      #
# --------------------------------------------------------------------------- #
def _which(*names):
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def play_wav(path: str):
    """Play a WAV file using whatever the platform provides."""
    if SYSTEM == "Windows":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME)
        return
    if SYSTEM == "Darwin":
        player = _which("afplay")
        if player:
            subprocess.run([player, path], check=False)
            return
    else:  # Linux / other
        player = _which("paplay", "aplay", "ffplay", "play")
        if player:
            args = [player, path]
            if player.endswith("ffplay"):
                args = [player, "-autoexit", "-nodisp", "-loglevel", "quiet", path]
            subprocess.run(args, check=False)
            return
    raise RuntimeError("No audio player found for WAV playback")


def _make_beep_wav(path: str):
    """Synthesize a subtle nudge: soft low tone that fades out, twice."""
    import math
    rate = 24000
    pcm = bytearray()

    def fading_tone(freq: int, ms: int, amp_max: float):
        n = int(rate * ms / 1000)
        fade_in = min(480, n // 4)
        for i in range(n):
            amp = amp_max * ((n - i) / n)
            if i < fade_in:
                amp *= i / fade_in
            val = int(amp * 32767 * math.sin(2 * math.pi * freq * i / rate))
            pcm.extend(struct.pack("<h", val))

    def silence(ms: int):
        pcm.extend(b"\x00\x00" * int(rate * ms / 1000))

    fading_tone(440, 600, 0.25)
    silence(500)
    fading_tone(440, 600, 0.20)

    with open(path, "wb") as f:
        f.write(build_wav(bytes(pcm), "audio/L16;rate=%d" % rate))


def play_beeps():
    """Attention beeps: subtle nudge - soft low tone that fades out, twice."""
    if SYSTEM == "Windows":
        try:
            import winsound
            winsound.Beep(440, 600)
            time.sleep(0.5)
            winsound.Beep(440, 600)
            return
        except Exception:
            pass
    try:
        beep_path = os.path.join(tempfile.gettempdir(), "speaky-beep.wav")
        _make_beep_wav(beep_path)
        play_wav(beep_path)
    except Exception:
        # Last resort: the terminal bell.
        sys.stdout.write("\a")
        sys.stdout.flush()


# --------------------------------------------------------------------------- #
# Native TTS (built-in OS synthesizers)                                        #
# --------------------------------------------------------------------------- #
def native_speak(text: str):
    """Speak via the OS's built-in synthesizer. No API key, no network."""
    text = strip_expressive(text)

    if SYSTEM == "Windows":
        ps = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.Volume = 100; $s.Speak($env:SPEAKY_TEXT)"
        )
        env = dict(os.environ, SPEAKY_TEXT=text)
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps], env=env, check=False
        )
        return

    if SYSTEM == "Darwin":
        say = _which("say")
        if say:
            subprocess.run([say, text], check=False)
            return
        raise RuntimeError("`say` not found on macOS")

    # Linux / other: speech-dispatcher, then espeak family.
    spd = _which("spd-say")
    if spd:
        subprocess.run([spd, "--wait", text], check=False)
        return
    espeak = _which("espeak-ng", "espeak")
    if espeak:
        subprocess.run([espeak, text], check=False)
        return
    raise RuntimeError(
        "No native speech synthesizer found. Install one of: "
        "speech-dispatcher (spd-say), espeak-ng, or espeak."
    )


# --------------------------------------------------------------------------- #
def premium_speak(text: str, style: str, voice: str, model: str, out: str,
                  play: bool) -> str:
    """Generate speech with Gemini, save the WAV, optionally play it."""
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY not set")
    wav = generate_speech(text, style, voice, model)
    with open(out, "wb") as f:
        f.write(wav)
    print(f"WAV saved: {out}")
    if play:
        play_wav(out)
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Speak text out loud (Gemini premium or native OS voice)."
    )
    parser.add_argument("text", nargs="?", help="What to say")
    parser.add_argument(
        "--mode", choices=["auto", "native", "premium"], default="auto",
        help="auto (default): premium if GEMINI_API_KEY set, else native",
    )
    parser.add_argument("--style", default=DEFAULT_STYLE, help="Director's-note style (premium)")
    parser.add_argument(
        "--voice", default=DEFAULT_VOICE,
        help="Gemini voice or alias (warm/deep/energetic/...); see --list-voices",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help="Model or alias: flash (default) / free (2.5-flash) / pro",
    )
    parser.add_argument(
        "--free", action="store_true",
        help="Shortcut for --model free (2.5-flash, has a free tier)",
    )
    parser.add_argument("--out", default=None, help="Where to save the WAV (premium)")
    parser.add_argument("--no-play", action="store_true", help="Generate only, don't play")
    parser.add_argument("--no-beep", action="store_true", help="Skip attention beeps")
    parser.add_argument(
        "--list-voices", action="store_true",
        help="Print available voices and aliases, then exit",
    )
    args = parser.parse_args()

    if args.list_voices:
        print("Aliases:")
        for alias, voice in VOICE_ALIASES.items():
            print(f"  {alias:10s} -> {voice}")
        print("\nAll voices:")
        print("  " + ", ".join(ALL_VOICES))
        return

    if not args.text:
        parser.error("the 'text' argument is required (unless --list-voices)")

    voice = resolve_voice(args.voice)
    model = resolve_model("free" if args.free else args.model)

    mode = args.mode
    if mode == "auto":
        mode = "premium" if os.environ.get("GEMINI_API_KEY") else "native"

    out = args.out or os.path.join(
        tempfile.gettempdir(), f"speaky-{time.strftime('%Y%m%d-%H%M%S')}.wav"
    )

    if not args.no_beep and not args.no_play:
        play_beeps()

    if mode == "native":
        if args.no_play:
            print("Nothing to do: native mode has no WAV to generate (--no-play).")
            return
        native_speak(args.text)
        print("Spoke via native OS synthesizer.")
        return

    # premium
    try:
        premium_speak(args.text, args.style, voice, model, out,
                      play=not args.no_play)
        print("Spoke via Gemini TTS.")
    except Exception as exc:
        print(f"Gemini TTS failed ({exc}); falling back to native voice.", file=sys.stderr)
        if not args.no_play:
            native_speak(args.text)
            print("Spoke via native OS synthesizer (fallback).")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
