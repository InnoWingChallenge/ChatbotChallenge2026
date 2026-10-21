# 将筛选结果生成 embedding 并入库

在 image worktree 的 `submission_repo/.env` 中沿用现有 embedding 的网关、密钥和
`EMBED_DEPLOYMENT` 配置。目前离线检查为 `text-embedding-3-small`。
它与图片识别的 `VISION_DEPLOYMENT` 无关。不要更换 embedding 模型后混入旧库；
维度相同也不代表不同模型的向量可以混用。

连接 VPN，避免同时运行其他入库脚本，在 PowerShell 执行：

```powershell
cd D:\Project\Innowing_Project\ChatbotChallenge2026-image\submission_repo
$py = '..\..\ChatbotChallenge2026\submission_repo\.venv\Scripts\python.exe'

# 离线校验、显示模型和需要调用的新增片段数
& $py -m build.ingest_curated_images plan

# 生成新增 embedding，并更新 Chroma、图片 BM25 和本地证据清单
& $py -m build.ingest_curated_images index
```

当前新增 140 条，合并后 368 条图片证据。只对新增片段生成向量；旧图片和文字向量
不重算、不删除。复用 `bot.llm.embed`，不调用聊天或视觉模型。
脚本不会重置数据库；原 Chroma 中的旧图片证据须已存在并与交付基线对应，否则停止。

默认每批 16 条。需要减小请求批量时：

```powershell
& $py -m build.ingest_curated_images index --batch-size 8
```

失败或 Ctrl+C 后重跑同一命令。已完成的 embedding 批次保存到
`submission_repo/data/image_evidence/embeddings/`；当前未保存的批次可能再次计费。
额度用尽或访问失败时先解决额度/VPN/配置问题，再续跑。已有环境变量优先于 `.env`。

全部向量缓存后才更新检索库。写库阶段中断可能留下部分新增记录，重跑通过相同 ID
补齐，不会产生重复记录。Chroma 与文件更新不是跨文件事务；出现 pending 标记时，
应完成重跑再使用 chatbot。`--cached-only` 可在向量全部缓存后禁止新的 embedding 调用。

## 成功与输出

终端最后显示：

```text
Complete: Chroma and image BM25 updated; existing text preserved.
```

- `data/chroma/`：新增图片向量。
- `data/image_search.sqlite`：合并图片证据的关键词检索索引。
- `data/image_evidence/records.json` / `sources.json`：合并后的证据和来源。
- `data/image_evidence/curated_indexed.json`：完成回执、模型及交付哈希。
- `data/image_evidence/curated_backups/<时间>/`：更新前的证据文件、BM25 和旧回执备份。
  此处不是完整 Chroma 备份；脚本通过不删除旧向量和幂等重跑保留已有内容。

源文件或旧证据发生变化时会停止，避免用过期快照覆盖新内容。此次只执行离线校验
和模拟测试，实际 embedding 与写库由上述命令执行。入库成功不代表描述已完成视觉核验，
后续仍应使用测试题评估检索质量。
