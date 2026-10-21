# Chroma / HNSW 现状（组内同步）

日期：2026-09-24  
范围：`submission_repo/`，InnoWing Chatbot Challenge 2026

---

## 一句话

本地和 Codabench 上都出现 **HNSW 向量图加载失败**。答题入口把异常吃掉后 stdout 变空行，评测记 **0 分**。  
`chromadb==1.5.9` 与 `requirements.txt` **一致**，不是装错版本。  
已经回退「HNSW 失败就改走 BM25」的投机写法；**正道是删掉坏库、重建 `data/chroma`。**

---

## 现象

本地（`submission_repo`）：

```text
python main.py "Innowing is named in memory of who?"
[error] InternalError: Error executing plan: Error sending backfill request to copactor: Error constructing hnsw segment reader: Error creating hnsw segment reader: Error loading hnsw index
```

`main.py` 捕获任意异常后打印空答案，退出码仍是 0，所以 Codabench 看起来像「跑完了但 0 分」，且经常 **No logs available**。

同一原因在评分机上：向量库打不开 → 整场空答案 → 五级平均 0。

---

## 库文件分别是什么

路径：`submission_repo/data/chroma/`

| 路径 | 作用 | 和报错的关系 |
|---|---|---|
| `chroma.sqlite3` | 集合目录、id、文档、metadata | 不是 HNSW reader 直接读的图；打开库会改 sqlite，容易和下面的 `.bin` **时间不一致** |
| `87930812-dbe4-445c-85d8-99852d740eb2/` | **一整套 HNSW 段** | 报错里的 `hnsw segment reader` 读的就是这里 |
| `data_level0.bin` | 向量本体（约 39MB） | 与 header / link_lists 必须成套 |
| `link_lists.bin` | 近邻边 | 同上 |
| `header.bin` / `length.bin` / `index_metadata.pickle` | 图头、长度、元数据 | 同上 |

没法只标「某一个 `.bin` 坏了」：Chroma 把 uuid 目录当**一段**加载，对不上就整段 `Error loading hnsw index`。

当前还能看到：HNSW 几个 bin 停在 **9/23 21:00**，`chroma.sqlite3` 在之后打开查询时被改过（例如 **9/24 16:21**）。compactor backfill 更容易失败。

同目录旁的 **`data/text_search.sqlite`（BM25）和 `data/knowledge/*.json` 与这次 HNSW 报错无关**，重建 Chroma 时不必删它们。

---

## 已经排除 / 已经回退的

- **版本**：当前解释器 `chromadb` 模块与发行版都是 **1.5.9**，和 `requirements.txt` 第 6 行一致。
- **投机方案（已回退，不要再合进去）**：在 `retrieve()` / `store.query()` 里 `except` 掉 HNSW 错误，改走 BM25。本地能答出 *Mr Tam Wing Fan*，但那是关键词检索，**不是向量 RAG**。组内已 `git checkout` 恢复 `bot/answer.py`、`bot/store.py`。
- 桌面上旧的 `innowing_chatbot_submission.zip` 若仍是 fallback 包，**不要当最终提交**；等向量库重建后再打。

---

## 建议改法（按顺序）

### 1. 重建向量库（必须做）

在 **港大 VPN** 下，于 `submission_repo/`：

```powershell
python check_setup.py
# 必须 READY（chat + embedding 都 PASS）

# 整份删除，不要只删某一个 bin
Remove-Item -Recurse -Force .\data\chroma

python build/index.py
```

`build/index.py` 会 reset collection、重新 embedding、写出新的 sqlite + 新的 uuid/HNSW 目录。  
按 AGENTS.md：文本重建后还要：

```powershell
python build/images.py --index-only
```

（若还没有 `data/descriptions.json`，需先 `--describe-only`。Vision 目前可能因 `max_tokens` vs `max_completion_tokens` 失败，那是图片管线，和本次 HNSW 加载是另一件事。）

不要删：`data/processed/`、`data/pages.json`、`data/text_search.sqlite`（`index.py` 会重写 FTS）、`data/knowledge/`。

### 2. 立刻验收（判断重建是否成功）

```powershell
python main.py "Innowing is named in memory of who?"
```

- **成功**：stdout 有答案，stderr **没有** `Error loading hnsw index`。
- **仍失败**：不是 `answer.py` 的问题。检查是否还有别的 Python 进程锁着 chroma、是否混用了另一个 venv 的 chromadb，然后重复第 1 步。

### 3. 再打包提交

zip **根目录必须是 `main.py`**，包含 `bot/`、`build/`、完整 `data/chroma/`（sqlite **和** uuid 文件夹）、`data/text_search.sqlite`、`data/knowledge/`。  
不要带 `.env`、真实 key、Labs、`.git`。

评分机常是 Linux + 只读解压。Windows 上建的 HNSW 若在 Linux 仍加载失败，再讨论：评分机同版本重建，或恢复只读拷贝到临时目录（`store.py` 旧逻辑）。**先把本机加载跑通。**

### 4. 不要做的

- 不要只提交 `chroma.sqlite3`、丢掉 uuid 目录（最早那份 zip 就是这样，库是空壳）。
- 不要用 `except` 把 HNSW 错误吞掉当长期方案。
- 不要把 API key 打进 zip 或 commit。

---

## 和比赛约束的关系（AGENTS.md）

- 答题逻辑在 `bot/answer.py`；建库在 `build/index.py`。
- 看图只在摄入时做；运行时用缓存描述，每题 30 秒。
- 交付物是 `submission_repo/`；评测跑 `python main.py "..."`。

---

## 当前结论

| 项 | 状态 |
|---|---|
| chromadb 版本 | 1.5.9，与 requirements 一致 |
| HNSW 文件 | uuid 目录存在但 **加载失败**（段损坏或与 sqlite 不一致） |
| 答题代码 | 已回到「必须能 query Chroma」，无 BM25 兜底 |
| 组内下一步 | 删 `data/chroma` → VPN 下 `index.py` → 本地确认无 HNSW 报错 → 再打 zip |

负责人建议：谁连着 VPN 谁跑重建，跑完在群里贴：`indexed N text chunks` 的 N、以及上述 `main.py` 测试有无 `[error] InternalError`。
