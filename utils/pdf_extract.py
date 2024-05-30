import cv2
from collections import defaultdict
import boto3
from enum import Enum
from PIL import Image
import numpy as np
from typing import Optional
import subprocess
import tempfile
from dataclasses import dataclass
import json
from pdf2image import convert_from_path

from pathlib import Path


class BlockType(Enum):
    KEY_VALUE_SET = "KEY_VALUE_SET", False, False, False
    PAGE = "PAGE", False, False, False
    LINE = "LINE", False, False, False
    WORD = "WORD", False, False, False
    TABLE = "TABLE", False, False, False
    CELL = "CELL", False, False, False
    SELECTION_ELEMENT = "SELECTION_ELEMENT", False, False, False
    MERGED_CELL = "MERGED_CELL", False, True, False
    TITLE = "TITLE", False, False, False
    QUERY = "QUERY", False, False, False
    QUERY_RESULT = "QUERY_RESULT", False, False, False
    SIGNATURE = "SIGNATURE", False, False, False
    TABLE_TITLE = "TABLE_TITLE", False, True, False
    TABLE_FOOTER = "TABLE_FOOTER", False, True, False
    LAYOUT_TEXT = "LAYOUT_TEXT", True, False, False
    LAYOUT_TITLE = "LAYOUT_TITLE", True, False, False
    LAYOUT_HEADER = "LAYOUT_HEADER", True, False, False
    LAYOUT_FOOTER = "LAYOUT_FOOTER", True, False, False
    LAYOUT_SECTION_HEADER = "LAYOUT_SECTION_HEADER", True, False, False
    LAYOUT_PAGE_NUMBER = "LAYOUT_PAGE_NUMBER", True, False, False
    LAYOUT_LIST = "LAYOUT_LIST", True, False, False
    LAYOUT_FIGURE = "LAYOUT_FIGURE", True, False, True
    LAYOUT_TABLE = "LAYOUT_TABLE", True, False, True
    LAYOUT_KEY_VALUE = "LAYOUT_KEY_VALUE", True, False, False

    def __init__(self, key: str, is_layout: bool, is_table: bool, is_figure: bool):
        self.key = key
        self.is_layout = is_layout
        self.is_table = is_table
        self.is_figure = is_figure


@dataclass
class PDFLayout:
    block_type: BlockType
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @classmethod
    def from_dict(cls, d: dict):
        block_type = BlockType[d["BlockType"]]
        xmin = d["Geometry"]["BoundingBox"]["Left"]
        ymin = d["Geometry"]["BoundingBox"]["Top"]
        width = d["Geometry"]["BoundingBox"]["Width"]
        height = d["Geometry"]["BoundingBox"]["Height"]
        xmax = xmin + width
        ymax = ymin + height
        return cls(block_type=block_type, xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)

    @classmethod
    def from_json_dict(cls, d: str):
        return cls(
            block_type=BlockType[d["block_type"]],
            xmin=d["xmin"],
            ymin=d["ymin"],
            xmax=d["xmax"],
            ymax=d["ymax"],
        )


IMAGE_PATH_FORMAT = "images/{part_index:06d}.jpg"


@dataclass
class PDFPart:
    page: int  # 1-indexed
    part_index: int
    layout: PDFLayout
    text: str | None = None
    image: Optional[Image] = None
    image_index: int | None = None
    parent: int | None = None

    def save_image_and_to_dict(self, output_dir):
        if self.image:
            image_path = IMAGE_PATH_FORMAT.format(part_index=self.image_index)
            output_image_path = Path(output_dir) / image_path
            Path(output_image_path).parent.mkdir(exist_ok=True, parents=True)
            self.image.save(output_image_path)
            image_path_str = str(image_path)
        else:
            image_path_str = None
        return {
            "page": self.page,
            "part_index": self.part_index,
            "layout": {
                "block_type": self.layout.block_type.name,
                "xmin": self.layout.xmin,
                "ymin": self.layout.ymin,
                "xmax": self.layout.xmax,
                "ymax": self.layout.ymax,
            },
            "text": self.text,
            "image_path": image_path_str,
            "image_index": self.image_index,
            "parent": self.parent,
        }

    @classmethod
    def from_json(cls, json_str: str):
        d = json.loads(json_str)
        return cls(
            page=d["page"],
            part_index=d["part_index"],
            layout=PDFLayout.from_json_dict(d["layout"]),
            text=d["text"],
            image=None,
            image_index=d["image_index"],
            parent=d["parent"],
        )


class TextractClient:
    def __init__(self, profile_name, region_name):
        session = boto3.Session(profile_name=profile_name, region_name=region_name)
        self.__client = session.client("textract")

    def analyze(self, document: bytes):
        return self.__client.analyze_document(
            Document={"Bytes": document}, FeatureTypes=["TABLES", "LAYOUT"]
        )


PAGE_FORMAT = "page_%06d.pdf"
DEFAULT_MAX_PAGES = 1000


def extract_pdf_by_textract(
    pdf_path: Path,
    textract_client: TextractClient,
    output_dir: Path,
    max_pages: int = DEFAULT_MAX_PAGES,
):
    output_dir.mkdir(exist_ok=True, parents=True)
    # output_textract_result = output_dir / "textract_result.json"
    output_textract_result = Path("test_textract_result.json")
    if not output_textract_result.exists():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            tmp.mkdir(exist_ok=True, parents=True)
            subprocess.run(
                ["pdfseparate", str(pdf_path), str(tmp / PAGE_FORMAT)],
                stderr=subprocess.DEVNULL,
                check=True,
            )
            pdfs = list(tmp.glob("*.pdf"))
            n_pages = len(pdfs)
            if n_pages > max_pages:
                raise ValueError(f"too many pages: {len(pdfs)}")

            results = []
            for i in range(1, n_pages + 1):
                pdf = tmp / (PAGE_FORMAT % i)
                with open(pdf, "rb") as f:
                    response = textract_client.analyze(f.read())
                    results.append(response)
        output_textract_result.write_text(
            json.dumps(results, indent=2, ensure_ascii=False)
        )
    else:
        results = json.loads(output_textract_result.read_text())

    pdf_images = convert_from_path(pdf_path)
    pdf_parts = gather_pdf_parts(results, pdf_images)
    output_jsonl = output_dir / "pdf_parts.jsonl"

    with output_jsonl.open("w") as output_json:
        for part in pdf_parts:
            d = part.save_image_and_to_dict(output_dir)
            print(json.dumps(d, ensure_ascii=False), file=output_json)


def gather_pdf_parts(results, pdf_images: list[Image]) -> list[PDFPart]:
    pdf_parts = []
    part_index = 0
    image_index = 0
    for page, (result, page_image) in enumerate(
        zip(results, pdf_images, strict=True), start=1
    ):
        id_to_blocks = {block["Id"]: block for block in result["Blocks"]}
        id_to_layout = {
            block["Id"]: PDFLayout.from_dict(block) for block in result["Blocks"]
        }
        parent_child_pairs = [
            (block["Id"], child_id)
            for block in result["Blocks"]
            if block.get("Relationships")
            for relationship in block["Relationships"]
            if relationship["Type"] == "CHILD"
            for child_id in relationship["Ids"]
        ]
        to_parents = defaultdict(list)
        to_children = defaultdict(list)
        for parent, child in parent_child_pairs:
            to_parents[child].append(parent)
            to_children[parent].append(child)

        for block in result["Blocks"]:
            layout = id_to_layout[block["Id"]]
            skip = False
            for parent in to_parents[block["Id"]]:
                parent_layout = id_to_layout[parent]
                if (
                    parent_layout.block_type.is_layout
                    or parent_layout.block_type.is_table
                    or parent_layout.block_type.is_figure
                ):
                    skip = True
                    break
            if skip:
                continue

            if (
                not layout.block_type.is_layout
                and not layout.block_type.is_table
                and not layout.block_type.is_figure
            ):
                continue
            # if layout.block_type == BlockType.LAYOUT_LIST:
            #     breakpoint()
            if layout.block_type.is_figure:
                image = page_image.crop(
                    (
                        layout.xmin * page_image.width,
                        layout.ymin * page_image.height,
                        layout.xmax * page_image.width,
                        layout.ymax * page_image.height,
                    )
                )
                current_image_index = image_index
                image_index += 1
            else:
                image = None
                current_image_index = None
            texts: list[str] = []
            gather_child_texts(block, id_to_blocks, to_children, texts)
            if layout.block_type == BlockType.LAYOUT_LIST:
                text = "\n\n".join(texts)
            else:
                texts = [t[:-1] if t.endswith("-") else t + " " for t in texts if t]
                text = "".join(texts)

            pdf_part = PDFPart(
                page=page,
                part_index=part_index,
                layout=layout,
                image=image,
                image_index=current_image_index,
                text=text,
            )
            pdf_parts.append(pdf_part)
            part_index += 1
    return pdf_parts


def gather_child_texts(block, id_to_blocks, to_children, texts):
    if block.get("Text"):
        texts.append(block["Text"])
    else:
        for child_id in to_children[block["Id"]]:
            gather_child_texts(id_to_blocks[child_id], id_to_blocks, to_children, texts)


def extract_pdf_data_to_md(extracted_dir: Path):
    pdf_parts = [
        json.loads(line)
        for line in (extracted_dir / "pdf_parts.jsonl").read_text().splitlines()
    ]
    md_path = extracted_dir / "extracted_data.md"
    with md_path.open("w") as md:
        for part in pdf_parts:
            print(f"## {part['part_index']}", file=md)
            print(
                f"Page: {part['page']}, block_type: {part['layout']['block_type']}",
                file=md,
            )
            print("", file=md)
            if part["text"]:
                print(part["text"], file=md)
                print("", file=md)
            if part["image_path"]:
                print(f"![]({part['image_path']})", file=md)
                print("", file=md)


def plot_pdf_parts(pdf_path: Path, extracted_dir: Path):
    pdf_images = [
        np.array(image)[..., ::-1].copy() for image in convert_from_path(pdf_path)
    ]
    pdf_parts = [
        json.loads(line)
        for line in (extracted_dir / "pdf_parts.jsonl").read_text().splitlines()
    ]
    for part in pdf_parts:
        page = part["page"] - 1
        pdf_image = pdf_images[page]
        height, width = pdf_image.shape[:2]
        xmin = int(part["layout"]["xmin"] * width)
        ymin = int(part["layout"]["ymin"] * height)
        xmax = int(part["layout"]["xmax"] * width)
        ymax = int(part["layout"]["ymax"] * height)
        cv2.rectangle(pdf_image, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
        message = f"[{part['part_index']}]"
        cv2.putText(
            pdf_image,
            message,
            (xmin, ymin),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
    output_dir = extracted_dir / "pdf_parts_images"
    output_dir.mkdir(exist_ok=True, parents=True)
    for i, pdf_image in enumerate(pdf_images, start=1):
        output_path = output_dir / f"{i:06d}.jpg"
        cv2.imwrite(str(output_path), pdf_image[..., ::-1])


# # サンプルPDFファイルのパス
# pdf_path = "1912.02424.pdf"
# client = TextractClient("n-kats", "us-east-2")
# extract_pdf_by_textract(Path(pdf_path), client, Path("_debug_pdf_extract"))
# extract_pdf_data_to_md(Path("_debug_pdf_extract"))
# plot_pdf_parts(Path(pdf_path), Path("_debug_pdf_extract"))
