from sqlalchemy import Column, Integer, String
from voice_browser.models_common import Base

from sqlalchemy.orm import relationship


class DebugItemDetail(Base):
    __tablename__ = "debug_item_details"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)


class PlayData(Base):
    __tablename__ = "play_data"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String)
    text = Column(String)
    play_item = relationship("PlayItem", back_populates="play_data")


class PlayItem(Base):
    __tablename__ = "play_items"

    id = Column(Integer, primary_key=True, index=True)
    play_data = Column("PlayData", nullable=True)
    debug_item_detail = Column("DebugItemDetail", nullable=True)

    def detail(self):
        return self.debug_item_detail
