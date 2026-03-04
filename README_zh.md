# clawanki

**语言：** [English](README.md) | 中文说明

`clawanki` 是一个将 OpenClaw 会话日志中的纠错对话，自动转化为 Anki 牌组的工具集，
默认示例针对“英语→中文”，但整体设计是 **多语言友好** 的：

- 具体语种由命令行参数 `--src-lang` / `--tgt-lang` 决定，只要 small LLM 能翻译即可；
- 语音由 `edge-tts` 负责，只要 Azure TTS 支持的语言/voice，都可以通过
  `CLAWANKI_TTS_LANG` / `CLAWANKI_TTS_VOICES` 配置出来。

典型工作流：

1. 你用英文和 OpenClaw Agent 对话；
2. Agent 在回复中嵌入一个标准的 `ANKI_CORRECTION` 块，例如：

   ```text
   [[ANKI_CORRECTION_START]]
   Original: "I agree with you, the standard output is very important for the agent to monitor the progress."
   Refined: "I agree with you; standard output is crucial for the agent to monitor progress."
   [[ANKI_CORRECTION_END]]
   ```

3. `clawanki` 从会话 JSONL 日志中提取这些块，并构建出 Anki 卡片，例如：
   - Front：Refined 句子的中文释义；
   - Back：纠正后的英文句子（Refined）；
   - Followup：纠正后紧接着的那段回答（内容本身也值得听/读）；
   - Audio_refine / Audio_reply：两段英文的语音；
   - Original：你当时说的原句（一般有错，仅供自查）。

目标是：让你“顺手练口语 + 自动制卡”，尽量不需要额外整理笔记。

---

## 1. 安装与环境

### 1.1 Python 依赖

- Python 3.10+
- 必需：`genanki`, `httpx`
- 可选：`edge-tts`（如果要生成语音）

开发环境安装（editable）：

```bash
cd clawanki
python -m pip install -e .
```

### 1.2 配置 `.env`

仓库根目录提供了一个 `ENV.example`，建议：

```bash
cd clawanki
cp ENV.example .env
# 然后编辑 .env，填入自己的 SMALL_LLM_* / CLAWANKI_TTS_* 等
```

clawanki 启动时会自动加载仓库根目录的 `.env`，但不会覆盖已经存在的系统环境变量。

主要环境变量：

- Small LLM：
  - `SMALL_LLM_BASE_URL`
  - `SMALL_LLM_MODEL`
  - `SMALL_LLM_API_KEY`
- 时区：`CLAWANKI_TZ`（用于解析 `--date/--from/--to`，默认 `Europe/Luxembourg`）
- TTS：
  - `CLAWANKI_TTS_ENGINE`（当前仅支持 `edge-tts`）
  - `CLAWANKI_TTS_LANG`（如 `en-US`）
  - `CLAWANKI_TTS_VOICES`（逗号分隔的 voice 列表，例如两男两女）
  - `CLAWANKI_MEDIA_DIR`（.ogg 文件输出目录）
- 模板目录（可选）：`CLAWANKI_TEMPLATE_DIR`（覆盖默认 `templates/`）

---

## 2. 总览：双阶段流水线

clawanki 的核心是两条命令：

- `clawanki extract`：Phase 1，从 OpenClaw session 日志中提取纠错记录到 JSONL；
- `clawanki build-deck`：Phase 2，从 JSONL 构建 Anki 牌组（翻译 + 语音）。

查看帮助：

```bash
clawanki --help
clawanki extract --help
clawanki build-deck --help
```

---

## 3. Phase 1：`clawanki extract`

### 3.1 用法示例

按单日提取：

```bash
clawanki extract \
  --date 2026-02-27 \
  --agent-dir ~/.openclaw/agents/main \
  --out /tmp/corrections-2026-02-27.jsonl
```

按日期区间提取：

```bash
clawanki extract \
  --from 2026-02-25 --to 2026-02-27 \
  --agent-dir ~/.openclaw/agents/main \
  --out /tmp/corrections-2026-02-25_to_27.jsonl
```

关键参数：

- `--date YYYY-MM-DD`：单日（本地时区）；
- `--from` / `--to`：起止日期；
- `--agent-dir`：Agent 目录，默认 `~/.openclaw/agents/main`；
- `--marker`：逻辑标记名，当前默认为 `ANKI_CORRECTION`；
- `--out`：输出 JSONL 文件路径。

### 3.2 行为

- 根据 `--date/--from/--to` 解析出日期区间，并转换为 UTC 毫秒窗口；
- 扫描 `agent-dir/sessions/*.jsonl*`：
  - 活跃文件：按 mtime 降序扫描，并在 mtime 早于窗口起点时提前停止；
  - 归档文件（`.reset.*` / `.delete.*`）：
    - 从文件名中解析归档日期（例如 `.reset.2026-02-27T...`）；
    - 如果归档日期早于目标起始日，则跳过；
    - 否则强制扫描，因为里面可能包含目标日期的对话。
- 仅保留：
  - `type == "message"`，`role` 为 `user` / `assistant`；
  - `timestamp` 在窗口内（支持 Unix ms 数字和 ISO8601 字符串）；
- 针对 `assistant` 消息，查找 `[[ANKI_CORRECTION_START]] ... [[ANKI_CORRECTION_END]]` 块：
  - 从 block 中解析 `Original: "..."` / `Refined: "..."`；
  - 从 block 结束后的文本中，按空行分段，取第一个非空自然段作为 `Followup`。

输出 JSONL 示例：

```json
{
  "original": "I will explain how the clustering works without embeddings or small LLMs.",
  "refined": "I'll explain how clustering functions without embeddings or small LLMs.",
  "followup": "这里是纠错后的第一段回答……",
  "timestamp": "2026-02-27T21:41:21.422Z",
  "session_id": "02847788-d42f-4853-8c20-5120ef862fb3",
  "marker": "ANKI_CORRECTION"
}
```

---

## 4. Phase 2：`clawanki build-deck`

### 4.1 用法示例

不启用 LLM/TTS（只做最简单的 deck）：

```bash
clawanki build-deck \
  --source /tmp/corrections-2026-02-27.jsonl \
  --out /tmp/english_practice_2026-02-27.apkg
```

启用 small LLM 翻译 + TTS：

```bash
clawanki build-deck \
  --source /tmp/corrections-2026-02-27.jsonl \
  --out /tmp/english_multimodal_2026-02-27.apkg \
  --src-lang en --tgt-lang zh \
  --use-small-llm \
  --use-tts
```

关键参数：

- `--source`：Phase 1 生成的 JSONL 文件；
- `--out`：输出 `.apkg` 路径；
- `--src-lang` / `--tgt-lang`：翻译方向（默认 `en` → `zh`）；
- `--use-small-llm`：是否调用 small LLM 生成 Front；
- `--use-tts`：是否调用 edge-tts 生成音频；
- `--dedup-mode`：`none` / `semantic`（目前 `semantic` 仍为占位实现）；
- `--dedup-threshold`：语义去重阈值（未来使用）。

### 4.2 行为

- 从 JSONL 读取 `original/refined/followup/...` 等字段；
- 翻译（Front）：
  - 打开 `--use-small-llm` 时：
    - 使用 `SMALL_LLM_*` 调用 small LLM，将 `refined` 翻译成 `tgt-lang`，填入 `Front`；
  - 否则：`Front = refined`；
- TTS（Audio_refine / Audio_reply）：
  - 打开 `--use-tts` 时：
    - 使用 `CLAWANKI_TTS_VOICES` 列表随机/轮询选择 voice；
    - 用 edge-tts 生成 `.ogg` 文件，存放于 `CLAWANKI_MEDIA_DIR`；
    - 将文件名写入 `audio_refine` / `audio_reply`；
- 去重：
  - 默认 `--dedup-mode=none`，不做语义去重。

---

## 5. Anki 模板与样式

clawanki 的 Anki 模型字段为：

```text
Front, Back, Followup, Audio_refine, Audio_reply, Original
```

模板与样式默认保存在仓库内的 `templates/` 目录：

- `templates/front.html`：正面模板（默认使用你提供的 "LOOK AND SPEAK" 样式）；
- `templates/back.html`：背面模板；
- `templates/style.css`：卡片 CSS 样式。

可以通过设置 `CLAWANKI_TEMPLATE_DIR` 来指定其它模板目录：

```env
CLAWANKI_TEMPLATE_DIR=/path/to/your/templates
```

目录下需要包含同名文件 `front.html` / `back.html` / `style.css`。

在构建牌组时：

- `Audio_refine` / `Audio_reply` 字段会被包装为 `[sound:xxx.ogg]`；
- 媒体文件会通过 `package.media_files` 一并打包进 `.apkg`；
- 导入 Anki 后即可直接播放音频。

---

## 6. 打包与 CLI

clawanki 使用标准的 `pyproject.toml` 管理包信息和命令行入口：

- 包名：`clawanki`；
- 版本：在 `pyproject.toml` 与 `clawanki/__init__.py` 中维护；
- CLI 入口：
  - `[project.scripts]` 中定义 `clawanki = "clawanki.cli:main"`；
  - 安装后可以直接运行 `clawanki ...`。

开发模式推荐：

```bash
cd clawanki
python -m pip install -e .
# 之后可以直接用：
clawanki extract ...
clawanki build-deck ...
```

## 7. 进一步阅读

- `CLI_HELP_SPEC.md` / `CLI_HELP_SPEC_MANSTYLE.md`：完整 CLI 参数与行为说明。