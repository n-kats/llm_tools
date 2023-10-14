import os
import tempfile
from pydub import AudioSegment
import sys
import openai
import click
import arxiv
import requests
from pathlib import Path
from dotenv import load_dotenv
from llm_tools.utils.click_utils import set_completions_command

APP_NAME = "text-to-voice"


@click.group()
def main():
    pass


@main.command(name="arxiv")
@click.option("--url", type=str, required=True)
@click.option("--output", type=Path, required=True)
@click.option("--dotenv", type=Path)
def arxiv_command(url: str, output: Path | None, dotenv: Path | None):
    if dotenv is not None:
        load_dotenv(dotenv)
    openai.api_key = os.environ["OPENAI_API_KEY"]
    voicevox_url = os.environ["VOICEVOX_URL"]
    url = to_arxiv_id(url)
    search = arxiv.Search(id_list=[url])
    results = list(search.results())
    if not results:
        raise click.BadParameter(f"arxiv id {url} is not found.")
    if len(results) > 1:
        raise click.BadParameter(f"arxiv id {url} is not unique.")
    summary = results[0].summary
    print(summary)
    if Path("description.txt").exists():
        description = Path("description.txt").read_text()
        description = description[: len(description) // 2]
    else:
        description = arxiv_summary_to_description(summary)
        Path("description.txt").write_text(description)
    print(description)
    text_to_wav(description, voicevox_url, output)


@main.command()
@click.option("--input", "input_", type=click.File("r"), required=True)
@click.option("--output", type=Path, required=True)
@click.option("--dotenv", type=Path)
def summary_text(input_, output: Path | None, dotenv: Path | None):
    if dotenv is not None:
        load_dotenv(dotenv)
    openai.api_key = os.environ["OPENAI_API_KEY"]
    voicevox_url = os.environ["VOICEVOX_URL"]
    summary = input_.read()

    print(summary, file=sys.stderr)
    output.parent.mkdir(parents=True, exist_ok=True)
    description_path = Path(output.parent / (output.name + ".description.txt"))
    if description_path.exists():
        description = description_path.read_text()
    else:
        description = arxiv_summary_to_description(summary)
        description_path.write_text(description)
    print(description, file=sys.stderr)
    text_to_wav(description, voicevox_url, output)


def to_arxiv_id(url):
    id_ = [x for x in url.split("/") if x != ""][-1]
    if id_.endswith(".pdf"):
        id_ = id_[:-4]
    return id_


def arxiv_summary_to_description(summary: str):
    prompt = """
以下の事項を日本語でまとめを作成してください。ただし、術語や人名はカタカナ表記にしてください。まとめのターゲットは研究者をターゲットにしてください。フォーマットは以下の箇条書きとリンクしたものにしてください。

1. 論文の主結果（どういうテーマの研究を行ったか・何を達成できたか）
2. 先行研究との違い（どういう新規性のある研究を行ったか）
3. キーワード
4. 論文の手法の概要（説明の中にある範囲で答えてください）
5. この論文を読むためにどのような前提知識が必要か

ただし、以下の制約を守ってください。
A. 数式は含まないでください
B. 説明以外の言及はしないでください
{summary}
"""
    input_ = prompt.format(summary=summary)
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", messages=[{"role": "user", "content": input_}]
    )
    return completion.choices[0].message.content


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


set_completions_command(APP_NAME, main)

if __name__ == "__main__":
    main()
