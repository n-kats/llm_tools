import argparse
from pathlib import Path
from dataclasses import dataclass

import gradio as gr
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--password", type=str, default=None)
    return parser.parse_args()


def get_random_audio():
    root = Path("./_cache/daily")
    candidates = [
        p
        for p in root.glob("*/*/*.mp3")
        if p.parent.parent.name >= "202401"
        and (p.parent / (p.name + ".description.txt")).exists()
    ]
    i = np.random.randint(len(candidates))
    target = candidates[i]
    description = (target.parent / (target.name +
                   ".description.txt")).read_text()
    return target, description


field_to_category = {
    "math": ["math.GT", "math.RA", "math.AP"],
    "physics": ["physics.optics", "physics.atom-ph", "physics.comp-ph"],
    "computer": ["cs.CV", "cs.AI", "cs.LG"],
}
category_to_field = {v: k for k, vs in field_to_category.items() for v in vs}


@dataclass
class RandomSampler:
    category: str | None = None
    day_from: str | None = "20240101"
    day_to: str | None = None

    def get_next_audio(self):
        root = Path("./_cache/daily")
        candidates = [
            p
            for p in root.glob("*/*/*.mp3")
            if all([
                self.day_from is None or p.parent.parent.name >= self.day_from,
                self.day_to is None or p.parent.parent.name <= self.day_to,
                self.category is None or p.parent.name == self.category,
                (p.parent / (p.name + ".description.txt")).exists(),
            ])
        ]
        i = np.random.randint(len(candidates))
        target = candidates[i]
        description = (target.parent / (target.name +
                       ".description.txt")).read_text()
        return target, description


@dataclass
class State:
    sampler = RandomSampler()


def next_play(state):
    audio, description = state.sampler.get_next_audio()
    return audio, description


def main():
    args = parse_args()
    with gr.Blocks() as app:
        state = gr.State(State())
        with gr.Accordion("設定変更", open=False):
            with gr.Tab("Random"):
                with gr.Row():
                    with gr.Column(scale=1):
                        field = gr.Dropdown(label="大分野")
                        field.choices = ["math", "physics", "computer"]
                        category = gr.Dropdown(label="カテゴリー")
                        category.choices = ["daily", "weekly", "monthly"]
                        field.select(set_)
                    with gr.Column(scale=1):
                        day_from = gr.Textbox(
                            label="期間(From):YYYYMMDD", max_lines=1)
                        day_to = gr.Textbox(
                            label="期間(To):YYYYMMDD", max_lines=1)
                with gr.Row():
                    with gr.Column(scale=1):
                        button = gr.Button("適用")

            with gr.Tab("Sequential"):
                field = gr.Dropdown(label="大分野")
                field.choices = ["math", "physics", "computer"]
                category = gr.Dropdown("カテゴリー")
                category.choices = ["daily", "weekly", "monthly"]
                button = gr.Button("Apply")

        with gr.Row():
            audio = gr.Audio("_assets/empty.mp3", autoplay=True)
        with gr.Row():
            text = gr.Textbox("")
        with gr.Row():
            button = gr.Button("Play")

        audio.stop(next_play, inputs=[state], outputs=[audio, text])
        button.click(next_play, inputs=[state], outputs=[audio, text])

    if args.password:
        app.launch(
            server_name=args.host,
            server_port=args.port,
            auth=("user", args.password),
            ssl_verify=False,
            ssl_certfile="./server.crt",
            ssl_keyfile="./server.key",
            ssl_keyfile_password="yukkuri",
        )
    else:
        app.launch(
            server_name=args.host,
            server_port=args.port,
            ssl_verify=False,
            ssl_certfile="./server.crt",
            ssl_keyfile="./server.key",
            ssl_keyfile_password="yukkuri",
        )


if __name__ == "__main__":
    main()
