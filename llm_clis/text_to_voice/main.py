import os
import sys
from pathlib import Path
from typing import Optional

import click
import openai
from dotenv import load_dotenv
from pydantic import BaseModel

from llm_tools.utils.click_utils import set_completions_command
from utils.arxiv_utils import ArxivSummary
from utils.cache_utils import cache_output_text
from utils.voice_utils import text_to_wav, VoiceVoxSpeaker
from utils.prompt_utils import (
    load_template,
    TacticBuilder,
    Adapter,
    TypedPrompt,
    Executor,
    call_gpt,
)

APP_NAME = "text-to-voice"


@click.group()
def main():
    pass


class SummaryText(BaseModel):
    summary: str


def build_tactic(
    tactic_name: str,
    prompt_path: Path,
    prompt_root: Optional[Path],
    max_retry: int,
    verbose: bool,
):
    if tactic_name == "single":
        return _build_single_tactic(prompt_path, prompt_root, max_retry, verbose)
    elif tactic_name == "sequence":
        return _build_sequence_tactic(prompt_path, prompt_root, max_retry, verbose)
    else:
        raise ValueError(f"Unknown tactic: {tactic_name}")


def _build_single_tactic(
    prompt_path: Path, prompt_root: Path | None, max_retry: int, verbose: bool
):
    builder = TacticBuilder("create_description", input_type=SummaryText)

    builder.add_typed_prompt(
        "summary_to_description",
        adapter=Adapter.identity(SummaryText),
        typed_prompt=TypedPrompt(
            load_template(prompt_path, prompt_root),
            input_type=SummaryText,
            output_type=str,
        ),
        executor=Executor(call_gpt, max_retry),
    )
    if verbose:
        builder.show_typed_prompts()
    fn = builder.build()
    return lambda text: fn(SummaryText(summary=text))[0]


class SummaryJP(BaseModel):
    title: str
    main_result: str
    difference: str
    how_to: Optional[str]


class KeyWords(BaseModel):
    keywords: list[str]
    necessary_knowledge: list[str]


def _build_sequence_tactic(
    prompt_path: Path, prompt_root: Path | None, max_retry: int, verbose: bool
):
    builder = TacticBuilder("create_description", input_type=ArxivSummary)
    builder.add_typed_prompt(
        "summary_to_description",
        adapter=Adapter.identity(ArxivSummary),
        typed_prompt=TypedPrompt(
            load_template(
                Path("./llm_clis/text_to_voice/prompts/templates/arxiv_summary_v2.j2")
            ),
            input_type=ArxivSummary,
            output_type=SummaryJP,
        ),
        executor=Executor(call_gpt, max_retry),
    )
    builder.add_typed_prompt(
        "summary_to_keywords",
        adapter=Adapter.project(ArxivSummary),
        typed_prompt=TypedPrompt(
            load_template(
                Path(
                    "./llm_clis/text_to_voice/prompts/templates/arxiv_summary_to_keywords_v1.j2"
                )
            ),
            input_type=ArxivSummary,
            output_type=KeyWords,
        ),
        executor=Executor(call_gpt, max_retry),
    )

    class GenerateHintInput(BaseModel):
        title: str
        title_jp: str
        main_result: str
        keywords: list[str]
        necessary_knowledge: list[str]

    builder.add_typed_prompt(
        "keywords_to_study_hint",
        adapter=Adapter(
            lambda x: GenerateHintInput(
                title=x.title,
                title_jp=x.summary_to_description.title,
                main_result=x.summary_to_description.main_result,
                keywords=x.summary_to_keywords.keywords,
                necessary_knowledge=x.summary_to_keywords.necessary_knowledge,
            )
        ),
        typed_prompt=TypedPrompt(
            load_template(
                Path(
                    "./llm_clis/text_to_voice/prompts/templates/arxiv_keywords_to_study_hint.j2"
                )
            ),
            input_type=GenerateHintInput,
            output_type=str,
        ),
        executor=Executor(call_gpt, max_retry),
    )

    current_type = builder.get_current_context_type()
    builder.add_typed_prompt(
        "output",
        adapter=Adapter.identity(current_type),
        typed_prompt=TypedPrompt(
            load_template(
                Path(
                    "./llm_clis/text_to_voice/prompts/templates/arxiv_summary_v2_output.j2"
                )
            ),
            input_type=current_type,
            output_type=str,
        ),
        executor=Executor(lambda x: x, max_retry),
    )
    if verbose:
        builder.show_typed_prompts()

    fn = builder.build()
    return lambda text: fn(ArxivSummary.model_validate_json(text))[0]


@main.command()
@click.option("--input", "input_", type=click.File("r"), required=True)
@click.option("--output", type=Path, required=True)
@click.option("--tactic", "tactic_name", type=str, default="single")
@click.option("--dotenv", type=Path)
@click.option(
    "--prompt_path",
    type=Path,
    default=Path(__file__).parent / "prompts/templates/arxiv_summary_v1.j2",
)
@click.option("--prompt_root", type=Path)
@click.option("--max_retry", type=int, default=3)
@click.option("--speaker_id", type=str, default="1")
@click.option("--speaker_speed", type=float, default=1.5)
@click.option("--verbose", is_flag=True)
def summary_text(
    input_,
    output: Path,
    tactic_name: str,
    dotenv: Path | None,
    prompt_path: Path,
    prompt_root: Optional[Path],
    max_retry: int,
    speaker_id: str,
    speaker_speed: float,
    verbose: bool,
):
    if dotenv is not None:
        load_dotenv(dotenv)
    openai.api_key = os.environ["OPENAI_API_KEY"]
    voicevox_url = os.environ["VOICEVOX_URL"]

    input_text = input_.read()

    tactic = build_tactic(tactic_name, prompt_path, prompt_root, max_retry, verbose)

    description = cache_output_text(
        lambda: tactic(input_text),
        Path(output.parent / (output.name + ".description.txt")),
    )
    if verbose:
        print(description, file=sys.stderr)

    speaker = VoiceVoxSpeaker(
        speaker_id=speaker_id, speed=speaker_speed, url=voicevox_url
    )
    text_to_wav(description, speaker, output)


set_completions_command(APP_NAME, main)

if __name__ == "__main__":
    main()
