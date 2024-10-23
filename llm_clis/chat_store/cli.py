import json
import sys
import uuid
from pathlib import Path
from typing import List, Optional

import click
import requests
from websockets.sync.client import connect

from .server import MessageToRead, MessageToWrite


class ChatClient:
    def __init__(self, host: str, history_dir: Path = Path.home() / ".cache/chat_store"):
        self.__host = host
        self.__history_dir = history_dir

    def current_room(self) -> Optional[str]:
        last_room_file_path = self.__history_dir / "last_room"
        if last_room_file_path.exists():
            return last_room_file_path.read_text().rstrip()
        return None

    def new_room(self) -> str:
        return uuid.uuid4().hex

    def read_history(self, room: str) -> List[MessageToRead]:
        return [
            MessageToRead(**message)
            for message in requests.get(f"{self.__host}/api/v1/history", json={"room_name": room}).json()
        ]

    def send_message(self, message: MessageToWrite):
        response = requests.post(f"{self.__host}/api/v1/post_message", json=message.dict())
        self.__history_dir.mkdir(parents=True, exist_ok=True)
        (self.__history_dir / "last_room").write_text(message.room_name)
        print(response.json(), file=sys.stderr)

    def watch(self, room: str):
        with connect(f"ws://{self.__host}/ws/{room}") as ws:
            while True:
                yield json.loads(ws.recv())


@click.command()
@click.option("--prompt", "-p")
@click.option("--new", "-n", is_flag=True, help="Create a new chat room")
@click.option("--room", "-r", help="Room to join")
@click.option("--user", default="user", help="User name")
@click.option("-h", "--host", default="localhost:8080")
def send(
    host: str,
    user: str,
    prompt: Optional[str] = None,
    new: bool = False,
    room: Optional[str] = None,
):
    input_ = sys.stdin.read()
    client = ChatClient(host=host)
    room = room if room else client.current_room() if not new else None
    if room is None:
        room = client.new_room()
    history = client.read_history(room)
    print(history, file=sys.stderr)

    message = PromptMessageBuilder(prompt).build(input_, room, user)
    client.send_message(message)


@click.command()
@click.option("--room", "-r", help="Room to join")
@click.option("-h", "--host", default="localhost:8080")
def watch(host: str, room: Optional[str] = None):
    client = ChatClient(host=host)
    room = room if room else client.current_room()
    if room is None:
        raise ValueError("No room specified")
    print(f"[Room] {room}")
    for message in client.watch(room):
        if not isinstance(message, list):
            message = [message]
        for m in message:
            print(f"[Message] {m}")


class PromptMessageBuilder:
    def __init__(self, prompt: Optional[str]):
        self.__prompt = prompt

    def build(self, text: str, room: str, user: str):
        return MessageToWrite(message=text, room_name=room, name=user, meta={"prompt": self.__prompt})
