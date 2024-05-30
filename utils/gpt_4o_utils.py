from PIL import Image
from io import BytesIO
import base64


def to_image_content(image: Image, image_type: str):
    with BytesIO() as f_out:
        image.save(f_out, format=image_type)
        encoded = base64.b64encode(f_out.getvalue()).decode("utf-8")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/{image_type};base64,{encoded}"},
    }


def run_gpt_4o(client, messages, **kwargs):
    return (
        client.chat.completions.create(model="gpt-4o", messages=messages, **kwargs)
        .choices[0]
        .message.content
    )
