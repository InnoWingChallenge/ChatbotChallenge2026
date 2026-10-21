# 优先描述：设备、设施与空间布局

本轮从 `../selection/reviewed_keep.json` 选择设备/设施 165 张、空间布局 230 张，共 395 张。人工暂缓的图片不在任务中。首批 58 张使用 **GPT 6 Luna / low**，剩余图片改由用户连接 VPN 后通过 **GPT-5-mini API** 生成。两种模型的结果分别标注，已有 Luna 文件保留。

**现在请使用 [API 运行说明](API_RUN.md)**：包括三张试跑、全量断点续跑、完整 prompt、按模型查看结果及常见错误。`description_registry.csv` 可直接用 Excel 按模型筛选。

## 文件

- `tasks.json`：全量任务、原图哈希、来源、预览路径和独立网页上下文。
- `pilot.json`：6 张试点（3 张设备、3 张空间），先验证描述格式与事实边界。
- `assignment-0/1/2.json`：后续分批任务；续跑时跳过已通过校验的同哈希描述。
- `descriptions/<id>.json`：实际查看图片后写入的逐图结构化描述；缺少文件表示尚未完成，不能当作无价值图片。
- `summary.json / remaining.json`：运行 status 后生成的完成统计与尚未描述任务。

原图保留；本轮预览在 `submission_repo/data/web_academy/priority_description_previews/`，长边最多 1600 像素，透明背景合成白底。阅读细小标牌时仍需查看原图或裁切，不根据预览猜测文字。

## 描述约束

每条记录绑定图片 ID、SHA-256、模型、实际推理档位、提示词版本和实际查看标记（Luna 使用 `equipment-space-v1`，API 使用 `equipment-space-api-v2`）。内容分为 `visible_text`（可辨认文字）、`visual_facts`（事实）、`spatial_relations`（空间关系）、`uncertainties`（不能确定的信息）。网页上下文留在任务中，不伪装成图片直接证据。

如果放大后发现只是无关活动照，可写 `suitable: false` 并说明原因；不会强行补造设备或空间描述。所有描述仍是模型生成，需要质量核验，不能仅凭结构校验就称为事实全部正确。

在 `submission_repo` 运行以下命令查看完成情况（不调用模型）：

```powershell
python -m build.describe_priority_images status
```

`describe_priority_images prepare` 只生成任务和预览，不能代替实际视觉描述。API 调用由 `describe_priority_api run` 执行。两者都不会自动写入数据库。完整 prompt 已接入 API 版本；原 Luna 版本是此前子代理使用的简化指令，不能混淆。描述完成后导出完整批次，再准备入库和原图支持的检验题。
