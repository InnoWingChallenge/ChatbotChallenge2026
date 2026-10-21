# 网站图片恢复、整理与描述试做

本目录记录 2026-10-17 的步骤 1–5 小批试做。完整结果见 [pilot_report.md](pilot_report.md)，其中可逐张打开描述和原图预览。尚未执行第 6 步入库。

## 文件用途

- `inventory.json`：全部 119 张现场图片和 6,584 条网站图片 URL 的统一来源清单。区分历史下载状态、当前文件状态、实际路径与历史路径。
- `exact_duplicates.json`：历史网站哈希与实际现场图片哈希的完全重复分组。未下载的历史记录不是本轮文件校验结果。
- `recovery_selection.json`、`recovery.json`：84 个试点下载目标及逐条恢复结果，包括原 URL、历史/当前哈希、实际本地路径、下载时间及错误。
- `similarity.json`：84 张已恢复网站图与 119 张现场图的指纹、5 对近似候选。候选只是提示，不代表必须合并；没有删除原图。尚未下载的图片不在视觉近似检查范围内。
- `pilot_batch.json`、`sol_batch.json`、`luna_batch.json`：20 张描述对象和两组各 10 张的分工。
- `sol_descriptions.json`、`luna_descriptions.json`：分别由指定模型直接查看图片后生成的结果，保存模型和 low 档位。
- `pilot_reviews.json`：导出描述的来源登记。状态为待全面复核的模型描述，不混入原有 `manual_reviews.json`。
- `quality_review.json`：主代理对 4 张图片的视觉抽查、修正和局限。不代表全部图片已人工核验。
- `../pilot_descriptions/*/prompt.md`：便于阅读的描述，图片可见内容与网页上下文分开。

## 原图在哪里

本轮恢复的原图存放在 `submission_repo/data/web_academy/recovered/<SHA-256>.<扩展名>`，预览在 `submission_repo/data/web_academy/previews/`。这两个目录被 Git 忽略。每张图的准确路径见 recovery.json，不要再只按旧 manifest 的 local_path 查找本轮文件。

原始 manifest、原有 24 份描述和数据库没有覆盖。对于字节哈希变化的图片，保留历史哈希和新文件，本轮不沿用历史描述；哈希变化可能来自重新压缩，也可能是视觉内容变化，须另外检查。原先没有哈希的新下载记录单独统计，不能误算成内容变化。

网站全部历史唯一原图约 3.9 GB，本轮只恢复 84 个 URL（约 144 MB），不是全量恢复。下次扩大批次时沿用已恢复缓存；相同字节仅存一份，多个 URL 仍分别记录。为防止缓存再次丢失，迁移或删除 worktree 前应单独备份原图目录；Git pull 不会恢复缓存。

## 重现命令

在 image worktree 的 submission_repo 中，使用已激活的 Python 环境：

```powershell
# 图像工具隔离安装，不修改两个 worktree 共用的 Python 依赖
python -m pip install --target data/web_academy/tools -r build/requirements-images.txt
python -m build.prepare_image_batch audit
python -m build.prepare_image_batch recover --limit 60 --workers 3
python -m build.prepare_image_batch audit
python -m build.prepare_image_batch group
```

`recover --limit 60` 指最多 60 张新候选，加上已有完成描述的代表图片。本轮按 URL/尺寸/来源页面做启发式排序，偏重海报；没有声称覆盖全部网站图片类型。下载遵循 robots.txt，小并发并重试，每条完成后保存进度，超过 40 MB 的单文件暂缓。

`batch --size 20` 会重新选择并覆盖分工文件，已有模型结果时不要随意重跑。`export_image_pilot` 校验分工、模型标识和原图哈希后，只生成试做描述，不调用模型、不修改正式入库登记表。继续下一批时应先归档本批分工和模型结果，避免覆盖。

## 模型试做结论

工具中没有 light 名称，此处映射为 gpt-6-sol / gpt-6-luna 的 low 推理档位。两者各描述 10 张不同的图片，不构成控制变量的模型对比。主要文字和布局可用，密集技术海报仍有小字漏录。抽查后由原模型补了中文标语、移除了无依据的赞助关系推断，并修正了标题标点。实际计费/额度数据未提供，不报告推测的节省比例。

描述仍保留不确定性，特别是无法辨认的小字。下一步应先复核高价值数值、姓名、日期和未录细字，再决定哪些描述可转入正式入库目录。
