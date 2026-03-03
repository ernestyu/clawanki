# clawanki DESIGN.md

一种将 OpenClaw 英语对话自动转化为 Anki 牌组的通用工具集设计草案。

本设计文档只描述目标、数据结构和 CLI 形状，不包含具体实现细节。代码在这些细节对齐后再动手。

---

## 1. 目标与范围

### 1.1 核心目标

- 将你与 OpenClaw Agent 的 **英语纠错对话** 高效、稳定地沉淀为 Anki 卡片。
- 使用脚本和 CLI，而不是依赖 Agent 的“记忆”，保证流程可重复、可审计。
- 支持逐步扩展：从“纠错对话制卡”开始，未来可以加上“文章/播客制卡”等更多入口。

### 1.2 当前阶段聚焦

第一阶段，clawanki 专注于两个主要入口：

1. **纠错对话 → Anki**
   - 从 session JSONL 中提取带特定标记（如 `ANKI_CORRECTION`）的纠错片段；
   - 每条纠错片段转化为一张或多张卡片，包含：翻译、正确表达、语音等。

2. **（预留）文章/播客 → Anki**
   - 从长文本（文章、播客转录）中批量制卡；
   - 这部分先在设计中占位，稍后再细化。

---

## 2. 总体架构：双阶段流水线

clawanki 整体采用 **双阶段流水线**：

- Phase 1：`extract` — 只负责从日志中“提纯文本结构”；
- Phase 2：`build-deck` — 负责翻译 / 语音 / 生成 Anki 牌组。

### 2.1 Phase 1：抽取（extract）

**职责**：

- 从 OpenClaw 的会话日志中，提取出所有符合条件的纠错片段；
- 不调用 LLM，不调用 TTS，只做“结构化文本抽取”；
- 输出纯文本中间文件（CSV 或 JSONL），方便后续脚本消费。

**来源**：

- 默认读取 `~/.openclaw/agents/main/sessions/*.jsonl`；
- 通过参数允许指定 `--agent-dir`；
- 支持按日期或日期区间过滤（UTC 或指定时区）以控制范围。

**中间格式**：

- Phase 1 的输出采用 **JSONL**（一行一条记录）：更适合扩展字段（时间戳、session id、语言信息等），也方便 Python 处理；
- Phase 2 在构建牌组时如有需要，可以额外导出一份 CSV 作为人工审阅用的快照，但内部主格式以 JSONL 为准。

**标记机制（marker）**：

- 默认使用 `ANKI_CORRECTION` 这一逻辑标记。
- 实际实现上，有两种可能：
  1. **物理 block**（推荐、现有约定）：
     - Agent 在纠错回复中输出：
       ```text
       [[ANKI_CORRECTION_START]]
       Original: "..."
       Refined: "..."
       [[ANKI_CORRECTION_END]]
       ```
     - extractor 只需要识别 block + 之后的正文片段；
  2. **关键词标记**：
     - 未来支持其它模式时，可以通过 `--marker` 提供（例如 `--marker ANOTHER_PATTERN`）。

**开放需求**：

- `clawanki extract` 需要支持：
  - `--marker`：关键字 / 模式名（默认 `ANKI_CORRECTION`）；
  - 未来可以将不同 marker 映射到不同字段布局或不同的后续流程。

### 2.2 Phase 2：构建（build-deck）

**职责**：

- 从 Phase 1 的中间文件中读取纯文本结构；
- 统一调用 small LLM 进行翻译；
- 调用 edge-tts 生成语音；
- 用 genanki 构造 `.apkg` 文件。

**重要设计点**：

- 翻译和语音放在 **第二阶段**：
  - 不在 extractor 里零散地调用模型；
  - 所有“智能加工”集中在 build-deck，便于控制成本和调试。
- 去重策略：
  - 透传你的偏好：**完全相同的行几乎不会出现，不做额外精确去重**；
  - Phase 2 可选支持“语义相似去重”（embedding），但**默认关闭**，避免过度去掉重复——因为语言学习本身需要重复强化。

---

## 3. 数据模型：字段设计

你提出的字段设计非常重要，是整个流水线的“型”。目前的目标 schema 为：

```text
Front, Back, Followup, Audio_refine, Audio_reply, Original
```

逐一解释：

- **Front**
  - 卡片正面显示的内容：
  - 你的设想：
    - “纠正后句子的翻译”——即 Refined 句子的中文解释（或更自然的中文表达）；
  - 学习模式：
    - 你看中文（Front），回忆地道英语表达（Back）。

- **Back**
  - 卡片背面：纠正后的英文句子（Refined）。

- **Followup**
  - 关键：
    - “关键字 ANKI_CORRECTION 后面的第一段，这段话一般是直接回答，也很有意义”；
  - 这里指的是 Agent 在纠正之后，给你的那段“内容回答”——比如针对你问题的答复、解释说明；
  - 这段文本本身很适合作为听力 / shadowing 材料。 

- **Audio_refine**
  - 针对 Back（Refined 句子）的 TTS 音频引用；
  - 具体格式：
    - 使用 edge-tts 生成的 `.ogg` 文件（文件名在打包时由 build-deck 决定）；
    - Anki 模板中通过 `sound:xxx.ogg` 形式引用。

- **Audio_reply**
  - 针对 Followup 的 TTS 音频引用；
  - 同样使用 `.ogg` 音频文件。

- **Original**
  - 你最初说的那句英文（一般有错）；
  - 只用于**事后审核 / 自我反思**，正常复习时不建议看，避免固化错误印象；
  - 在 Anki 模板中可以放在 `Extra` 区块或折叠区。

> 备注：Phase 1 抽取时，至少要提取 `Original`, `Refined`, `Second_Reply`。Phase 2 负责填充 `Front`（翻译）、`Audio_refine`、`Audio_second` 字段。

---

## 4. CLI 设计草案

### 4.1 顶层结构

```bash
clawanki --help

clawanki extract       # Phase 1: 从日志中抽取结构化纠错数据
clawanki build-deck    # Phase 2: 从中间数据生成 Anki 牌组
clawanki from-article  # （预留）从文章/播客文本制卡
```

### 4.2 `clawanki extract`

**目的**：

- 读取 OpenClaw 会话日志；
- 按日期/范围筛选；
- 抽取满足 marker 条件的纠错块；
- 输出 CSV/JSONL：至少包含 `Original`, `Refined`, `Second_Reply`。

**可能的参数草案**：

```bash
clawanki extract \
  --date 2026-03-02 \
  --agent-dir ~/.openclaw/agents/main \
  --marker ANKI_CORRECTION \
  --out corrections-2026-03-02.csv

clawanki extract \
  --from 2026-03-01 --to 2026-03-07 \
  --marker ANKI_CORRECTION \
  --out corrections-week1.csv
```

- `--date` / `--from` / `--to`：与之前 `collect_anki_pairs.py` 的日期逻辑类似，但做成 CLI 参数；
- `--agent-dir`：可选，默认 `~/.openclaw/agents/main`；
- `--marker`：逻辑 marker 名（默认 `ANKI_CORRECTION`）；
  - 未来可以支持不同 marker → 不同提取规则；
- `--out`：输出文件路径，建议 CSV（UTF‑8‑BOM / UTF‑8）或 JSONL。

**输出字段（Phase 1）**：

最小集合：

```text
Original, Refined, Second_Reply
```

可以在 header 中写明，Phase 2 会在此基础上增加翻译和音频字段。

### 4.3 `clawanki build-deck`

**目的**：

- 从 extract 生成的中间文件中，生成完整的 `.apkg`；
- 统一处理翻译 + TTS + 去重策略。

**可能的参数草案**：

```bash
clawanki build-deck \
  --source corrections-2026-03-02.csv \
  --out english_practice_2026-03-02.apkg \
  --lang-pair zh-en \
  --use-small-llm \
  --use-tts \
  --dedup-mode none

# 使用语义去重的变体
clawanki build-deck \
  --source corrections-week1.csv \
  --out english_practice_week1.apkg \
  --dedup-mode semantic \
  --dedup-threshold 0.9
```

配置：

- `--source`：输入 CSV/JSONL；
- `--out`：输出 apkg；
- `--lang-pair`：翻译方向，初期固定为 `zh-en`（Front 中文 Back 英文）；
- `--use-small-llm`：是否调用 small LLM 生成 Front；
- `--use-tts`：是否调用 edge-tts 生成 `Audio_refine` / `Audio_second`；
- `--dedup-mode`：`none | semantic`（默认 `none`，不做语义去重）；
- `--dedup-threshold`：仅在 `semantic` 模式下使用。

**Phase 2 填充字段**：

- 从 `Original, Refined, Second_Reply` 出发：
  - `Front`：用 small LLM 将 `Refined` 翻译成自然中文；
  - `Back`：直接用 `Refined`；
  - `Second_Reply`：沿用 Phase 1 抽取的文本；
  - `Audio_refine` / `Audio_second`：由 edge-tts 生成音频并写入引用；
  - `Original`：保留，只在 Anki 模板的后侧展示或折叠。

---

## 5. from-article 子命令（预留）

你提到“我经常从播客里生成 Anki 卡片”，这在设计上非常合理。初步想法：

```bash
clawanki from-article \
  --source transcript.md \
  --out article_cards.apkg \
  --mode cloze|qa|phrase \
  --max-cards 50
```

- `--source`：文章或播客转录文本（Markdown 或纯文本）；
- `--mode`：制卡模式（完形填空、问答卡、短语卡等）；
- `--max-cards`：限制生成卡片数量；
- 内部仍然通过 small LLM 生成 Front/Back，并调用 TTS 生成音频。

这部分暂不实现，先留在 DESIGN 中，等纠错对话路径稳定后再细化。

---

## 6. 开放问题 / 待确认

在动手写代码之前，需要和你一起确认/调整的一些点：

1. **日志格式与 marker 解析**：
   - 最终是否统一以 `[[ANKI_CORRECTION_START]]` block 作为主信号？
   - `Second_Reply` 精确定义：是 block 之后的第一段 reply，还是更宽松的范围？

2. **中间文件格式**：
   - CSV vs JSONL：
     - CSV 简单，和之前工作流相似；
     - JSONL 更适合保留上下文、元数据（timestamp、session id 等）。

3. **small LLM & TTS 配置约定**：
   - 是否复用与 Clawkb 相同的 `SMALL_LLM_*` 环境变量？
   - edge-tts 的语音配置（voice name、语速等）如何抽象成参数？

4. **语义去重**：
   - 默认关掉，仅作为 `--dedup-mode semantic` 的可选路径是否符合你的期望？

5. **Anki 模板细节**：
   - Front/Back 的具体 HTML 模板；
   - `Original` 是否默认折叠；
   - Audio 字段在模板中的呈现方式。

---

等你确认/补充以上点之后，我再根据这个 DESIGN 开始分步实现：

1. 先搭好 `clawanki extract` CLI 框架 + 简单的 JSONL 解析和 CSV 输出（不动 LLM/TTS）；
2. 再实现 `clawanki build-deck` 的基础版本（只做 genanki，不调用 LLM/TTS）；
3. 最后逐步接入 small LLM 翻译和 edge-tts 语音，并加上你想要的卡片模板。
