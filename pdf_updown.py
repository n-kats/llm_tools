import fastapi
import json
import openai
from dotenv import load_dotenv

from PIL import Image
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel
from uuid import uuid4
from pdf2image import convert_from_path
import httpx
from utils.gpt_4o_utils import run_gpt_4o,  to_image_content
from utils.voice_utils import VoiceVoxSpeaker, text_to_wav
tmp = Path("_tmp/pdf_updown")

load_dotenv()
app = fastapi.FastAPI()
client = openai.Client()
url_to_request_id_path = tmp / "url_to_request_id.json"
if url_to_request_id_path.exists():
    url_to_request_id = json.loads(url_to_request_id_path.read_text())
else:
    url_to_request_id = {}
    url_to_request_id_path.parent.mkdir(parents=True, exist_ok=True)
    url_to_request_id_path.write_text(json.dumps(url_to_request_id))


app.mount(
    "/static", StaticFiles(directory="./webui/llm_app_ui/dist"), name="static")

app.mount(
    "/assets", StaticFiles(directory="./webui/llm_app_ui/dist/assets/"))


@app.get("/")
def root():
    return fastapi.responses.RedirectResponse("/static/index.html")


class InitRequest(BaseModel):
    url: str


class InitResponse(BaseModel):
    request_id: str
    page_num: int


@app.post("/init/")
def init(req: InitRequest) -> InitResponse:
    if req.url in url_to_request_id:
        request_id = url_to_request_id[req.url]
    else:
        request_id = str(uuid4())
        url_to_request_id[req.url] = request_id
        url_to_request_id_path.parent.mkdir(parents=True, exist_ok=True)
        url_to_request_id_path.write_text(json.dumps(url_to_request_id))
    work_dir = tmp / request_id
    image_dir = work_dir / "images"
    pdf_path = work_dir / "pdf.pdf"
    work_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)
    if not pdf_path.exists():
        pdf_path.write_bytes(httpx.get(req.url).content)
    pages = convert_from_path(pdf_path)
    for i, page in enumerate(pages, start=1):
        if not (image_dir / f"{i:04d}.png").exists():
            page.save(image_dir / f"{i:04d}.png")

    return InitResponse(request_id=request_id, page_num=len(pages))


class ImageRequest(BaseModel):
    request_id: str
    page: int


@app.post("/image/")
def image(req: ImageRequest) -> fastapi.responses.FileResponse:
    # 画像を返す
    work_dir = tmp / req.request_id
    image_path = work_dir / "images" / f"{req.page:04d}.png"
    return fastapi.responses.FileResponse(image_path)


class ExplainRequest(BaseModel):
    request_id: str
    page: int


class ExplainResponse(BaseModel):
    explanation: str


speaker = VoiceVoxSpeaker(
    speaker_id="1",
    speed=1.5,
    volume=4,
    url="http://localhost:50021",
)


@app.post("/explain/")
def explain(req: ExplainRequest) -> ExplainResponse:
    cache_path = tmp / req.request_id / f"explain_{req.page:04d}.txt"
    if cache_path.exists():
        return ExplainResponse(explanation=cache_path.read_text())

    image_path = tmp / req.request_id / "images" / f"{req.page:04d}.png"
    explanation = generate_explanation(image_path)
    cache_path.write_text(explanation)
    audio_path = tmp / req.request_id / f"explain_{req.page:04d}.mp3"
    text_to_wav(explanation, speaker, audio_path)

    return ExplainResponse(explanation=explanation)


def generate_explanation(image_path):
    image = Image.open(image_path)
    image_type = "png"
    image_content = to_image_content(image, image_type)
    response = run_gpt_4o(client, messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "これは論文のあるページです。このページに書かれている内容を説明してください。謝辞・参考文献リストはスルーしてください。TeX形式の数式は **必ず** $で囲んでください。"},
                image_content,
            ]
        }
    ], json_mode=False, model="gpt-4o-mini")
    return response


@app.post("/audio/")
def audio(req: ExplainRequest) -> fastapi.responses.FileResponse:
    audio_path = tmp / req.request_id / f"explain_{req.page:04d}.mp3"
    if not audio_path.exists():
        explanation_path = tmp / req.request_id / f"explain_{req.page:04d}.txt"
        explanation = explanation_path.read_text()
        text_to_wav(explanation, speaker, audio_path)
    return fastapi.responses.FileResponse(audio_path)


@app.post("/regenerate/")
def regenerate(req: ExplainRequest) -> ExplainResponse:
    image_path = tmp / req.request_id / "images" / f"{req.page:04d}.png"
    explanation = generate_explanation(image_path)
    cache_path = tmp / req.request_id / f"explain_{req.page:04d}.txt"
    cache_path.write_text(explanation)
    audio_path = tmp / req.request_id / f"explain_{req.page:04d}.mp3"
    text_to_wav(explanation, speaker, audio_path)

    return ExplainResponse(explanation=explanation)
