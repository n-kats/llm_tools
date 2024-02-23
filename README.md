# 使い方
## 共通
* poetry環境
* jq
* python 3.11くらい

## .env ファイルの内容
```
OPENAI_API_KEY=ChatGPTのAPIキー
VOICEVOX_URL=http://localhost:50021
```

## 前提
```
$ poetry install
$ poetry shell
```

## ずんだもん解説
### サマリーダウンロード
```
$ python download_today_arxiv_summary.py --categories cs.CV math.GT
```

### voicevox起動（GPU使用想定）
```
$ bash ./scripts/launch_voicevox.sh
```

### 音声化
voicevoxを起動した状態で
```
$ text-to-voice summary-text --input 入力ファイル --output 出力ファイル --dotenv .env
```

### 例
以下のコマンドで_cache/daily ディレクトリにファイルが生成される

```bash
python download_today_arxiv_summary.py --categories cs.CV math.GT
find _cache/daily_summary/ -name "*.json" -type f | while read -r line; do
  day="$(basename "$(dirname "$(dirname "$line")")")"
  cat="$(basename "$(dirname "$line")")"
  id="$(basename "$line" | sed "s/.json$//g")"
  output="_cache/daily/$day/$cat/$id.mp3"
  if [[ -e "$output" ]]; then
    echo skip "$output"
    continue
  fi
  echo start "$output"
  text-to-voice summary-text \
    --input "$line" --output "$output" --dotenv .env \
    --prompt_path ./llm_clis/text_to_voice/prompts/templates/arxiv_summary_v2.j2 \
    --tactic sequence
done
```