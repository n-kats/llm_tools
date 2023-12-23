import os
import sys
from pathlib import Path

import click
import openai
from dotenv import load_dotenv

from llm_tools.utils.click_utils import set_completions_command
from utils.arxiv_utils import from_arxiv_url, to_arxiv_id
from utils.cache_utils import cache_output_text
from utils.voice_utils import text_to_wav

APP_NAME = "text-to-voice"


@click.group()
def main():
    pass


@main.command(name="arxiv")
@click.option("--url", type=str, required=True)
@click.option("--output", type=Path, required=True)
@click.option("--dotenv", type=Path)
def arxiv_command(url: str, output: Path, dotenv: Path | None):
    if dotenv is not None:
        load_dotenv(dotenv)
    openai.api_key = os.environ["OPENAI_API_KEY"]
    voicevox_url = os.environ["VOICEVOX_URL"]
    id_ = to_arxiv_id(url)
    summary = cache_output_text(
        lambda: from_arxiv_url(url).summary, output / f"{id_}_summary.txt"
    )
    print(summary, file=sys.stderr)
    description = cache_output_text(
        lambda: arxiv_summary_to_description(summary),
        output / f"{id_}_description.txt",
    )
    print(description, file=sys.stderr)
    text_to_wav(description, voicevox_url, output/f"{id_}.mp3")


@main.command()
@click.option("--input", "input_", type=click.File("r"), required=True)
@click.option("--output", type=Path, required=True)
@click.option("--dotenv", type=Path)
def summary_text(input_, output: Path, dotenv: Path | None):
    if dotenv is not None:
        load_dotenv(dotenv)
    openai.api_key = os.environ["OPENAI_API_KEY"]
    voicevox_url = os.environ["VOICEVOX_URL"]
    summary = input_.read()

    print(summary, file=sys.stderr)
    description = cache_output_text(
        lambda: arxiv_summary_to_description(summary),
        Path(output.parent / (output.name + ".description.txt"))
    )
    print(description, file=sys.stderr)
    text_to_wav(description, voicevox_url, output)


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


set_completions_command(APP_NAME, main)

if __name__ == "__main__":
    main()
