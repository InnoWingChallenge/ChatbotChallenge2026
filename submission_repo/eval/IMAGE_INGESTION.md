# 第一批图片证据：入库与检验

本次代码在 `ChatbotChallenge2026-image` worktree 的 `feat/image-processing` 分支。不要在另一个 benchmark worktree 运行以下新命令。

## 当前状态

- 已整理 119 张现场图片及 24 张已完成描述的网站图片，共 228 条图片描述/网页上下文证据。
- `data/image_evidence/records.json` 保存派生证据；`sources.json` 保存图片标识、来源、哈希等信息。原图与描述仍独立保存。没有把测试答案导入数据库。
- 已生成 `data/image_search.sqlite`，接入现有混合检索；原文字 BM25 数据库保持独立。
- 尚未调用线上 embedding、尚未写入生产 Chroma。仓库 AGENTS.md 要求用户连接 HKU VPN 后运行线上 API 检查和入库。
- 描述来自已有 assistant review，并非本轮逐图人工核验。拍摄日期未知时明确标为 unknown；网页 caption 与图片可见内容分开。部分网站原图在这个 worktree 缺失，来源清单保留此状态；不阻止使用已有描述。

## 完成 Chroma 入库

先连接 HKU VPN。在 PowerShell 中进入本 worktree 的 `submission_repo`。可以复用主目录已有 Python 环境（下面假设当前终端位于 `ChatbotChallenge2026-image/submission_repo`）：

```powershell
$py = (Resolve-Path '../../ChatbotChallenge2026/submission_repo/.venv/Scripts/python.exe').Path
& $py check_setup.py
& $py -m build.ingest_reviewed_images index
& $py main.py "What is 3D printing also known as?"
& $py main.py "What words appear on the Brainstorming Area wall?" "What is the room number of the Podcast Studio?"
```

请先确保当前 worktree 配置了自己的 `.env` 或相应环境变量；复用 Python 环境不等于自动继承另一个目录的 `.env`。不要提交密钥。仅在 `check_setup.py` 成功后继续；403 通常需检查 VPN，401 检查密钥。

`index` 批量生成并缓存 embedding，完成后再向已有 Chroma upsert；只清理本流程的过期记录，不删除文字或旧图片记录。重复运行可复用缓存。成功时输出 Chroma/BM25 数量并写入 `data/image_evidence/indexed.json`。中途失败可重跑，不把部分执行当作成功。

今后修改描述后执行：

```powershell
& $py -m build.ingest_reviewed_images prepare
& $py -m build.ingest_reviewed_images bm25
& $py -m build.ingest_reviewed_images index
```

前两步不调用 API。`build/index.py` 会重置 Chroma，重建文字后先按原流程恢复旧图片，再运行本流程的 `index`。Git 合并代码不会自动合并数据库内容，应从来源重新入库。运行时需保留 `data/image_search.sqlite` 和 Chroma；本地 SQLite、embedding 缓存及测试报告被 Git 忽略，提交包仍需包含运行所需索引。

## 检验题与结果

人工阅读 `eval/image_questions.md`；机器题集为 `eval/image_smoke.json`。共 25 题，覆盖标牌、房间编号、颜色、数量、跨图比较、网站图片以及信息不足时不应猜测的情况。每题带参考答案、证据路径和摘录。参考答案仍需对照原图核实。

```powershell
# 离线检索：文字 BM25 + 图片 BM25 + 已有知识，检查证据排名
& $py -m eval.check_images --mode lexical --output eval/image_runs/my-lexical-01
# VPN/API 可用且入库后：加入真实向量检索，不运行回答生成/LLM 重排
& $py -m eval.check_images --mode hybrid --output eval/image_runs/my-hybrid-01
# 实际 main.py 回答：逐题 30 秒超时，人工对照参考答案评分
& $py -m eval.check_images --mode answers --output eval/image_runs/my-answers-01
```

可加 `--ids image_001 image_007` 仅运行部分题。每次使用新的输出目录，不覆盖旧报告。结果位于指定目录的 `report.json` 和 `report.md`，包含问题、参考答案、实际回答或检索证据、耗时和错误。回答模式须人工评分，不自动将关键词匹配当成正确答案。

本轮离线结果：25 题无运行错误，完整证据进入前 5 条的比例为 100%，前 1 条为 64%，平均约 0.11 秒/题。它是用于调整检索的开发验收集，不能代表独立 benchmark 成绩，也不代表最终回答准确率或线上耗时。后续应补充未参与调整的新问题。

离线单元测试：`& $py -m unittest discover -s tests -v`，29 项通过；包括真实临时 Chroma 的重复写入、仅清理本流程记录，以及写入失败时保留旧记录。线上回答和平均 30 秒限制尚待实测。
