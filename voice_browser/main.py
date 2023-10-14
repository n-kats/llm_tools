"""
API
* リコメンダー作成API
* リコメンデーション取得API
* 履歴取得API
* 再生データ取得API
* 再生完了API
* プレイリスト取得API
* プレイリスト更新API（追加・除去）
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI()


class RecommenderConfig(BaseModel):
    recommender_type: str
    params: dict


class HistoryItem(BaseModel):
    user_id: int
    song_id: int


class PlaybackDataItem(BaseModel):
    user_id: int
    song_id: int
    duration: int


class PlaylistItem(BaseModel):
    song_id: int


from voice_browser import recommenders, recommender_models


@app.post("/recommenders/")
def create_recommender(config: RecommenderConfig) -> str:
    recommender = recommenders.create(
        type=config.recommender_type, params=config.params
    )
    return recommender.id


@app.get("/recommendations/{recommender_id}}", response_model=List[RecommendationItem])
def get_recommendations(recommender_id: str):
    recommender = recommenders.get_recommender(recommender_id)
    return recommender.get_recommendations()


@app.get("/history/{recommender_id}}")
def get_history(recommender_id: str):
    return recommender_models.get_history(recommender_id)


@app.get("/play/", response_model=List[PlaybackDataItem])
def get_play_data():
    return playback_data


@app.post("/playback_data/", response_model=PlaybackDataItem)
def complete_playback(playback_item: PlaybackDataItem):
    playback_data.append(playback_item)
    return playback_item


@app.get("/playlist/", response_model=List[PlaylistItem])
def get_playlist():
    return playlist


@app.post("/playlist/add/", response_model=PlaylistItem)
def add_to_playlist(item: PlaylistItem):
    playlist.append(item)
    return item


@app.delete("/playlist/remove/", response_model=PlaylistItem)
def remove_from_playlist(item: PlaylistItem):
    if item in playlist:
        playlist.remove(item)
        return item
    else:
        raise HTTPException(status_code=404, detail="Item not found in the playlist")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
