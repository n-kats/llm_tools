from pydantic import BaseModel
from datetime import datetime
from collections import defaultdict
from typing import Sequence, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy_serializer import SerializerMixin

database_url = "sqlite:///./debug.db"
engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Room(Base, SerializerMixin):  # type: ignore
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    messages = relationship("Message", back_populates="room")

    __table_args__ = (UniqueConstraint("name", name="uq_room_name"),)

    @classmethod
    def find_by_name(cls, session, name):
        return session.query(cls).filter(cls.name == name).first()

    @classmethod
    def get_or_create(cls, session, name):
        room = session.query(cls).filter(cls.name == name).first()
        if room is None:
            room = cls(name=name)
            session.add(room)
            session.commit()
        return room


class Message(Base, SerializerMixin):  # type: ignore
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(String)
    name = Column(String)
    time = Column(DateTime)
    meta = Column(JSON)
    room_id = Column(Integer, ForeignKey("rooms.id"))
    room = relationship("Room", back_populates="messages")

    def to_dict(self):
        return super().to_dict(only=self.serializable_keys - {"room"})


app = FastAPI()
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>Room ID: <span id="room-id"></span></h1>
        <form action="" onsubmit="sendMessage(event)">
            name: <input type="text" id="userName" autocomplete="off"/></br>
            text: <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'></ul>
        <script>
            var room_id = "{room}";
            document.querySelector("#room-id").textContent = room_id;
            var ws = new WebSocket(`ws://100.64.1.24:33333/ws/${{room_id}}`);
            ws.onmessage = function(event) {{
                var data = JSON.parse(event.data)

                if (!Array.isArray(data)) {{
                    data = [data]
                }}
                data.forEach(message => {{
                    var text = `[${{message.name}}] ${{message.message}}`
                    var messages = document.getElementById('messages')
                    var message = document.createElement('li')
                    var content = document.createTextNode(text)
                    message.appendChild(content)
                    messages.appendChild(message)
                }})
            }};
            function sendMessage(event) {{
                var user = document.getElementById("userName")
                var text = document.getElementById("messageText")
                ws.send(JSON.stringify({{"name": user.value, "message": text.value}}))
                text.value = ''
                event.preventDefault()
            }}
        </script>
    </body>
</html>
"""


class ConnectionManager:
    def __init__(self):
        self.__room_to_member = defaultdict[str, set[WebSocket]](set)
        self.__mebmer_to_room = dict[WebSocket, str]()

    async def connect(self, websocket: WebSocket, room: str):
        await websocket.accept()
        self.__room_to_member[room].add(websocket)
        self.__mebmer_to_room[websocket] = room

    def disconnect(self, websocket: WebSocket):
        room = self.__mebmer_to_room[websocket]
        del self.__mebmer_to_room[websocket]
        self.__room_to_member[room].remove(websocket)
        if not self.__room_to_member[room]:
            del self.__room_to_member[room]

    async def broadcast(self, message: Any, room: str, not_send: Sequence = tuple()):
        for connection in self.__room_to_member[room]:
            if connection not in not_send:
                await connection.send_json(message)


manager = ConnectionManager()


class MessageToWrite(BaseModel):
    message: str
    name: str
    meta: dict
    room_name: str


class MessageToRead(BaseModel):
    message: str
    name: str
    time: datetime
    meta: dict
    room_id: int


@app.get("/app/{room}")
async def get(room: str):
    return HTMLResponse(html.format(room=room))


@app.get("/api/v1/room_names")
async def get_room_names() -> list[str]:
    session = SessionLocal()
    names = [room.name for room in session.query(Room).all()]
    session.close()
    return names


class RoomQuery(BaseModel):
    room_name: str


@app.get("/api/v1/history")
async def get_history(q: RoomQuery) -> list[MessageToRead]:
    session = SessionLocal()
    room = Room.find_by_name(session, q.room_name)
    messages = (
        [MessageToRead(**message.to_dict()) for message in room.messages]
        if room is not None
        else []
    )
    session.close()
    return messages


@app.post("/api/v1/post_message")
async def post_message(message: MessageToWrite) -> MessageToRead:
    session = SessionLocal()
    room = Room.get_or_create(session, message.room_name)
    now = datetime.utcnow()
    message = Message(
        message=message.message,
        name=message.name,
        time=now,
        meta=message.meta,
        room=room,
    )
    session.add(message)
    session.commit()
    result = MessageToRead(**message.to_dict())
    await manager.broadcast(result.json(), room.name)
    session.close()
    return result


@app.websocket("/ws/{room_name}")
async def websocket_endpoint(websocket: WebSocket, room_name: str):
    await manager.connect(websocket, room_name)
    session = SessionLocal()
    room = Room.get_or_create(session, room_name)
    await websocket.send_json([message.to_dict() for message in room.messages])
    session.close()
    try:
        while True:
            data = await websocket.receive_json()
            message_str = data.pop("message", "")
            name = data.pop("name", "")
            now = datetime.utcnow()
            message = Message(
                message=message_str, name=name, time=now, meta=data, room=room
            )
            session = SessionLocal()
            session.add(message)
            session.commit()
            stored = message.to_dict()
            session.close()
            await manager.broadcast(stored, room_name)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


Base.metadata.create_all(bind=engine)
