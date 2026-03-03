# clawanki(1)

## NAME
**clawanki** — Bridge between OpenClaw session logs and Anki decks.

## SYNOPSIS
```bash
clawanki [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]
PYTHONPATH=src python -m clawanki.cli [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]
```

## DESCRIPTION
clawanki 将 OpenClaw Agent 的纠错对话转化为 Anki 牌组。典型场景是：

- 你用英文和 Agent 对话；
- Agent 在回复中嵌入一个 ANKI_CORRECTION 区块：

  ```text
  [[ANKI_CORRECTION_START]]
  Original: "..."
  Refined: "..."
  [[ANKI_CORRECTION_END]]
  ```

- clawanki 在会话日志 JSONL 中自动识别这些块，将其抽取成结构化记录；
- 每条记录变成一张卡片：
  - Front: Refined 的翻译（例如中文释义）；
  - Back: Refined（纠正后的英文句子）；
  - Followup: 纠错后紧随其后的第一个自然段（通常是有价值的回答内容）；
  - Audio_refine / Audio_reply: 对应两段文本的语音（通过 edge-tts 生成的 .ogg）；
  - Original: 你最初说的那句英文（一般有错，仅供自查，不建议频繁看）。

clawanki 采用两阶段流水线：

- `extract`: 从 session 日志中提取纠错记录到 JSONL；
- `build-deck`: 从 JSONL 构建 Anki 牌组（翻译 + TTS）。

---

## GLOBAL OPTIONS

目前没有全局级别的额外选项，仅有子命令。

clawanki 会在启动时尝试从项目根目录加载 `.env` 文件：

- 路径：`<repo_root>/.env`；
- 行格式：`KEY=VALUE`；
- 行首 `#` 为注释；
- 加载策略：仅当 `os.environ` 中没有该 key 时，才使用 `.env` 中的值（不会覆盖已有环境变量）。

推荐做法：

```bash
cp ENV.example .env
# 然后编辑 .env 填写 SMALL_LLM_*、CLAWANKI_TTS_* 等
```

---

## extract(1)

### NAME
**clawanki extract** — Phase 1: 从 OpenClaw 会话日志中提取 ANKI_CORRECTION 纠错记录

### SYNOPSIS
```bash
clawanki extract \
  --date 2026-03-02 \
  --agent-dir ~/.openclaw/agents/main \
  --out corrections-2026-03-02.jsonl
```

或使用日期区间：

```bash
clawanki extract \
  --from 2026-03-01 --to 2026-03-07 \
  --agent-dir ~/.openclaw/agents/main \
  --out corrections-week1.jsonl
```

### OPTIONS

```text
usage: clawanki extract [-h] [--date DATE] [--from DATE_FROM] [--to DATE_TO]
                        [--agent-dir AGENT_DIR] [--marker MARKER] --out OUT

options:
  -h, --help            show this help message and exit
  --date DATE           Single date YYYY-MM-DD (local time)
  --from DATE_FROM      Start date YYYY-MM-DD (local time)
  --to DATE_TO          End date YYYY-MM-DD (local time)
  --agent-dir AGENT_DIR
                        Agent directory (default: ~/.openclaw/agents/main)
  --marker MARKER       Logical marker name to extract (default:
                        ANKI_CORRECTION)
  --out OUT             Output JSONL path
```

### BEHAVIOR

1. **日期解析**
   - `--date`：解析为单日；
   - `--from` + `--to`：解析为日期区间（如 end < start 会自动交换）；
   - 都不提供时：默认取 `CLAWANKI_TZ`（或 Europe/Luxembourg）的“昨天”。

2. **时间窗口**
   - 将日期区间转换为 UTC 毫秒区间 `[ts_from_ms, ts_to_ms)`；

3. **会话文件扫描**
   - 在 `agent-dir/sessions` 下匹配 `*.jsonl*` 文件；
   - 按 `st_mtime` 降序处理：越新的文件越先扫描；
   - 对于 **活跃文件**（没有 `.reset.` / `.delete.` 后缀）：
     - 如果某个文件的 mtime 早于窗口起点，则直接 `break`，不再扫描更旧文件；
   - 对于 **归档文件**：
     - 文件名包含 `.reset.YYYY-MM-DD` 或 `.delete.YYYY-MM-DD`；
     - 从文件名中解析 `archive_date`；
     - 若 `archive_date < d_from`，则 `continue`（跳过，不可能包含目标日期内容）；
     - 若 `archive_date >= d_from`，则允许穿透扫描（因为可能包含目标日期或之前几天的数据）。

4. **消息过滤**
   - 仅保留 JSONL 中：
     - `type == "message"`；
     - `message.role` 在 `{user, assistant}`；
     - `timestamp` 为：
       - Unix 毫秒数字，或
       - ISO8601 字符串（例如 `"2026-02-27T21:41:21.422Z"`）；
     - 时间在 `[ts_from_ms, ts_to_ms)` 内；
   - 文本内容从 `message.content[]` 中 `type == "text"` 的条目中提取，并按行拼接。

5. **ANKI_CORRECTION block 解析**
   - 针对 `assistant` 的消息，查找：

     ```text
     [[ANKI_CORRECTION_START]]
     ...
     [[ANKI_CORRECTION_END]]
     ```

   - 在 block 内解析：

     ```text
     Original: "..."
     Refined: "..."
     ```

   - `Followup` 的定义：
     - 从 `[[ANKI_CORRECTION_END]]` 之后的文本开始；
     - 按空行分段；
     - 取第一个非空自然段作为 `followup`。

6. **JSONL 输出**
   - 对每个 block 输出一条记录，字段至少为：

     ```json
     {
       "original": "...",
       "refined": "...",
       "followup": "...",
       "timestamp": "2026-02-27T21:41:21.422Z",
       "session_id": "02847788-d42f-4853-8c20-5120ef862fb3",
       "marker": "ANKI_CORRECTION"
     }
     ```

---

## build-deck(1)

### NAME
**clawanki build-deck** — Phase 2: 从 JSONL 构建 Anki 牌组（翻译 + TTS）

### SYNOPSIS

```bash
clawanki build-deck \
  --source corrections-2026-02-27.jsonl \
  --out english_practice_2026-02-27.apkg \
  --src-lang en --tgt-lang zh \
  --use-small-llm --use-tts
```

### OPTIONS

```text
usage: clawanki build-deck [-h] --source SOURCE --out OUT
                           [--src-lang SRC_LANG] [--tgt-lang TGT_LANG]
                           [--use-small-llm] [--use-tts]
                           [--dedup-mode {none,semantic}]
                           [--dedup-threshold DEDUP_THRESHOLD]

options:
  -h, --help            show this help message and exit
  --source SOURCE       Source JSONL path produced by 'clawanki extract'
  --out OUT             Output .apkg path
  --src-lang SRC_LANG   Source language code for refined sentences (default:
                        en)
  --tgt-lang TGT_LANG   Target language code for card fronts (default: zh)
  --use-small-llm       Use SMALL_LLM_* to translate refined sentences into
                        fronts
  --use-tts             Use TTS (edge-tts) to generate ogg audio for
                        Back/Followup
  --dedup-mode {none,semantic}
                        Deduplication mode (default: none)
  --dedup-threshold DEDUP_THRESHOLD
                        Semantic dedup cosine threshold when --dedup-
                        mode=semantic
```

### BEHAVIOR

1. **读取 JSONL**
   - 使用 `CorrectionRecord` dataclass 承接字段：
     - `original`, `refined`, `followup`, `timestamp`, `session_id`, `marker`；

2. **翻译 (Front 生成)**
   - 当 `--use-small-llm` 打开时：
     - 从 `SMALL_LLM_BASE_URL` / `SMALL_LLM_MODEL` / `SMALL_LLM_API_KEY` 读取配置；
     - 对每条记录的 `refined` 调用 small LLM，生成 `front` 文本：
       - 示例 prompt："将下面的 {src_lang} 句子翻译成简洁、自然的 {tgt_lang}，用于 Anki 卡片正面提示。只输出翻译文本，不要解释。"；
   - 当 `--use-small-llm` 关闭或配置缺失时：
     - 简易回退：`front = refined`。

3. **TTS (Audio_refine / Audio_reply)**
   - 当 `--use-tts` 打开时：
     - 使用 `edge-tts` CLI，并从以下环境变量读取配置：
       - `CLAWANKI_TTS_ENGINE`（当前仅支持 `edge-tts`）；
       - `CLAWANKI_TTS_VOICES`（逗号分隔的 voice 列表，例如两男两女）；
       - `CLAWANKI_TTS_LANG`（如 `en-US`）；
       - `CLAWANKI_MEDIA_DIR`（.ogg 文件输出目录）；
     - 合成策略：
       - 每条记录分别为 `refined`（Back）和 `followup` 生成 `.ogg`；
       - 每次调用随机或轮询选取一个 voice；
       - `.ogg` 文件名基于 `kind + hash(text)`，保证重复文本复用已有文件；
       - 将文件名（不含路径）写入 `audio_refine` / `audio_reply` 字段。

4. **去重 (Dedup)**
   - `--dedup-mode none`（默认）：
     - 不做语义去重，只保留所有记录；
   - `--dedup-mode semantic`：
     - 预留接口，用于未来基于 embedding 的语义相似去重；
     - 目前实现中，该模式还是占位，返回原列表不做修改。

5. **Anki 模型与模板**
   - 字段：
     - `Front`, `Back`, `Followup`, `Audio_refine`, `Audio_reply`, `Original`；
   - 模板与样式：
     - 从模板目录读取（默认 `templates/`，可通过 `CLAWANKI_TEMPLATE_DIR` 覆盖）：
       - `front.html` → qfmt
       - `back.html` → afmt
       - `style.css` → css
     - 默认内置模板采用你提供的 "LOOK AND SPEAK" 样式：
       - 正面：`<h1 class="R">LOOK AND SPEAK</h1><p>{{Front}}</p>`；
       - 背面包括 Back + Followup + Original，以及条件渲染的音频字段。

6. **音频字段与媒体打包**
   - 在生成 Note 时：
     - 将 `audio_refine` / `audio_reply` 字段包装为 `[sound:文件名.ogg]`：
       - 符合 Anki 播放规范；
   - 在打包阶段：
     - 通过 `package.media_files = [...]` 把所有 `.ogg` 文件的路径加入到 genanki Package；
     - 路径使用 `CLAWANKI_MEDIA_DIR` + 文件名拼接；
     - 确保 `.apkg` 中实际包含媒体文件，而不只是“空链接”。

---

## ENVIRONMENT

clawanki 主要使用以下环境变量：

- Small LLM：
  - `SMALL_LLM_BASE_URL`
  - `SMALL_LLM_MODEL`
  - `SMALL_LLM_API_KEY`

- 时区：
  - `CLAWANKI_TZ`（例如 `Europe/Luxembourg`）

- TTS：
  - `CLAWANKI_TTS_ENGINE`（当前仅支持 `edge-tts`）
  - `CLAWANKI_TTS_LANG`（如 `en-US`）
  - `CLAWANKI_TTS_VOICES`（逗号分隔的 voice 列表，例如两男两女）
  - `CLAWANKI_MEDIA_DIR`（.ogg 媒体输出目录）

- 模板目录：
  - `CLAWANKI_TEMPLATE_DIR`（可选，覆盖默认 `templates/`）

`ENV.example` 提供了一份可复制的环境变量模板，推荐：

```bash
cp ENV.example .env
# 然后编辑 .env 按需修改
```

---

## SEE ALSO

- `README.md` — 高层目标与使用示例；
- `DESIGN.md` — 设计草案与后续扩展计划（例如 from-article）。
