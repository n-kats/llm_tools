import argparse
from openai import OpenAI
from utils.gpt_4o_utils import to_image_content, run_gpt_4o
import httpx
from pathlib import Path
from utils.voice_utils import VoiceVoxSpeaker, text_to_wav
from pdf2image import convert_from_path


def download_pdf(url: str, output_path: Path):
    if output_path.exists():
        return output_path

    # Download the PDF
    response = httpx.get(url)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(response.content)

    return output_path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--disable_cache",  action="store_true")
    parser.add_argument("--voicevox_url", type=str)
    parser.add_argument("--speaker_id", type=str, default="1")
    parser.add_argument("--speaker_speed", type=float, default=1.5)
    return parser.parse_args()


def main():
    args = parse_args()
    client = OpenAI()

    pdf_id = args.url.split("/")[-1]
    if pdf_id.endswith(".pdf"):
        pdf_id = pdf_id[:-4]

    output_root = args.output / pdf_id
    output_pdf = output_root / f"{pdf_id}.pdf"

    output_path = download_pdf(args.url, output_pdf)
    pdf_images = convert_from_path(output_path)

    results = []
    for i, page in enumerate(pdf_images, start=1):
        result_path = output_root / "summary" / f"{i}.txt"
        if result_path.exists():
            print(f"# {result_path}(from cache)")
            result = result_path.read_text()
            results.append(result)
            print(result)
            continue
        result = run_gpt_4o(
            client,
            messages=[
                {
                    "role": "system",
                    "content": "以下の論文の一部を日本語で読み上げツールで読み上げられる形式で解説してください（数式を使わない・英単語はカタカナ表記に変更する）。",
                },
                {
                    "role": "user",
                    "content": [to_image_content(page, "PNG")],
                }
            ]
        )
        print(f"# {result_path}")
        results.append(result)
        print(result)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(result)
    all_result = "\n".join(results)

    output = output_root / "summary.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    print("writing to", output)
    output.write_text(all_result)

    speaker = VoiceVoxSpeaker(
        speaker_id=args.speaker_id, speed=args.speaker_speed, url=args.voicevox_url
    )
    text_to_wav(all_result, speaker, output_root/f"{pdf_id}.mp3")
    print("done!")


if __name__ == '__main__':
    main()
