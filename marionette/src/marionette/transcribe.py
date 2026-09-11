"""Audio → text via OpenAI's Whisper API.

Reads OPENAI_API_KEY from the environment.
"""

import json
from pathlib import Path
from typing import List, NamedTuple, Optional, Union

WHISPER_MODEL = "whisper-1"

PathLike = Union[str, Path]


class Word(NamedTuple):
    text: str
    start: float  # seconds
    end: float    # seconds


def transcribe(
    audio_path: PathLike,
    model: str = WHISPER_MODEL,
    cache_path: Optional[PathLike] = None,
) -> str:
    """Transcribe an audio file with OpenAI Whisper. Returns plain text.

    Accepts any format Whisper accepts (mp3, mp4, mpeg, mpga, m4a, wav, webm).
    If cache_path is given and the file exists, its contents are returned
    verbatim; otherwise the API is called and the result written there.
    """
    if cache_path and Path(cache_path).exists():
        return Path(cache_path).read_text()

    with open(audio_path, "rb") as f:
        response = _client().audio.transcriptions.create(model=model, file=f)
    text = response.text

    if cache_path:
        Path(cache_path).write_text(text)
    return text


def transcribe_words(
    audio_path: PathLike,
    model: str = WHISPER_MODEL,
    cache_path: Optional[PathLike] = None,
) -> List[Word]:
    """Transcribe with per-word timestamps. Useful for lip-sync alignment.

    If cache_path is given and the file exists, the cached JSON is returned;
    otherwise the API is called and the result written there.
    """
    if cache_path and Path(cache_path).exists():
        data = json.loads(Path(cache_path).read_text())
        return [Word(*w) for w in data]

    with open(audio_path, "rb") as f:
        response = _client().audio.transcriptions.create(
            model=model,
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    words = [Word(w.word, w.start, w.end) for w in response.words]

    if cache_path:
        Path(cache_path).write_text(json.dumps([list(w) for w in words]))
    return words


def _client():
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "openai is required for transcription. "
            "Install with: pip install 'marionette[whisper]'"
        ) from e
    return OpenAI()
