import os
import tempfile
import sys
from pathlib import Path

import requests
import click
from pydub import AudioSegment


def split_text(text: str, max_length: int, separetors: list[str]):
    if len(text) < max_length:
        return [text]

    sub = text[:max_length]
    candidates = [
        sub.rsplit(separetor, 1)[0] + separetor
        for separetor in separetors
        if separetor in sub
    ]
    if candidates:
        pos = max([len(x) for x in candidates])
    else:
        pos = max_length

    return [text[:pos]] + split_text(text[pos:], max_length, separetors)


def text_to_wav(text: str, url: str, output: Path, max_length=300):
    texts = split_text(text, max_length, separetors=["。", "、", ". "])
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, text in enumerate(texts):
            _text_to_wav(text, url, Path(tmpdir) / f"{i}.wav")
        sound = AudioSegment.empty()
        for i, text in enumerate(texts):
            sound += AudioSegment.from_file(Path(tmpdir) / f"{i}.wav")
        sound.export(output, format=os.path.splitext(output.name)[-1][1:])

    print(f"done: {output}", file=sys.stderr)


def _text_to_wav(text: str, url: str, output: Path):
    response = requests.post(
        f"{url}/audio_query", params={"speaker": "1", "text": text}
    )

    if not response.ok:
        raise click.BadParameter(
            f"voicevox api returns {response.status_code}")

    synthesis_response = requests.post(
        f"{url}/synthesis?speaker=1",
        headers={"Context-Type": "application/json"},
        data=response.content,
    )
    if not synthesis_response.ok:
        raise click.BadParameter(
            f"voicevox api returns {synthesis_response.status_code}"
        )
    with output.open("wb") as f:
        f.write(synthesis_response.content)
