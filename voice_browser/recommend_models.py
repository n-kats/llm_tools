from dataclasses import dataclass
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from voice_browser.models_common import Base
from voice_browser.item_models import PlayItem
from typing import Any, Dict

Item = Any


class DebugRecommender(Base):
    __tablename__ = "debug_recommenders"

    id = Column(Integer, primary_key=True, index=True)
    history_id = Column(Integer, ForeignKey("user_histories.id"))
    history = relationship("UserHistory", back_populates="debug_recommenders")

    def recommend(self, history):
        return None


class UserHistory(Base):
    __tablename__ = "user_histories"

    id = Column(Integer, primary_key=True, index=True)
    states = relationship("RecommendingState", back_populates="history")

    def to_recommendation_input(self):
        states = sorted(
            self.states, key=lambda x: (x.recommend_index, x.group_index, x.play_index)
        )
        done = []


class RecommendingState(Base):
    __tablename__ = "recommending_states"

    id = Column(Integer, primary_key=True, index=True)
    history_id = Column(Integer, ForeignKey("user_histories.id"))
    history = relationship("UserHistory", back_populates="recommending_states")

    play_index = Column(Integer)  # 再生番号(再生されていたらその番号、そうでなければ推薦された番号)
    group_index = Column(Integer)  # 0: 再生されていた場合, 1: 未再生の場合
    recommend_index = Column(Integer)  # 推薦番号

    play_item_id = Column(Integer, ForeignKey("play_items.id"))
    play_item = Column("PlayItem", nullable=True)
    played = Column(Boolean, default=False)
    ordered = Column(Boolean, default=False)


@dataclass
class ItemWithIndex:
    item: Item
    play_index: int
    group_index: int
    recommendation_index: int

    @property
    def priority(self):
        return self.play_index, self.group_index, self.recommendation_index

    def __hash__(self):
        return hash(self.item)


@dataclass
class WaitingState:
    selected: bool


@dataclass
class RecommendState:
    current_item: ItemWithIndex
    history: list
    waiting_list: Dict[ItemWithIndex, WaitingState]

    def update(self, item, waiting_state):
        waiting_list = self.waiting_list.copy()
        waiting_list[item] = waiting_state
        return RecommendState(
            current_item=self.current_item,
            history=self.history.copy(),
            waiting_list=waiting_list,
        )
