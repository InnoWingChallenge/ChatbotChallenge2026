# 用 GPT-5-mini 接着描述剩余图片

脚本：`submission_repo/build/describe_priority_api.py`。只处理当前人工保留清单中已选定的设备/设施和空间图片；不会自动入库或修改 Chroma。

2026-10-20 离线核对：共 395 张，已有 **58 张 Luna low** 结果，跳过；剩余 **337 张**进入 API 队列。实际数量每次运行前重新核对。

## 运行

连接 HKU VPN，确认 **image worktree 的** `submission_repo/.env` 中 API key 和网关配置有效，并设置：

```dotenv
VISION_DEPLOYMENT=gpt-5-mini
```

已有终端环境变量优先于 `.env`。若以前在终端设置过其他部署，可在当前 PowerShell 显式执行 `$env:VISION_DEPLOYMENT="gpt-5-mini"`。脚本会拒绝其他部署，不会悄悄换模型。

下面使用迁移后主目录里的共享 Python 环境，不必重新创建 venv：

```powershell
cd D:\Project\Innowing_Project\ChatbotChallenge2026-image\submission_repo
$py = '..\..\ChatbotChallenge2026\submission_repo\.venv\Scripts\python.exe'

# 离线检查：验证原图、已有描述，列出真正剩余的任务，不调用 API
& $py -m build.describe_priority_api plan

# 先试 3 张；建议查看输出内容，确认文字、数量和空间关系的覆盖
& $py -m build.describe_priority_api run --limit 3

# 接着处理全部剩余图片；有效结果自动跳过
& $py -m build.describe_priority_api run
```

Ctrl+C 可以停止，重跑相同命令继续。请求已成功但本地尚未来得及保存时中断，下一次可能重做该张；已经保存并校验通过的文件不会重复调用。脚本用进程锁防止两个 API 下载描述任务同时运行；不要同时启动 Luna 代理写入同一批描述文件。

## Prompt 与图片

脚本每次读取 `prompt_from_web/DESCRIPTION_PROMPT.txt` 的完整五项要求：位置、物体与数量、逐字可见文字、空间关系、颜色与材质。追加设备与空间专用规则，再将段落输出改为 JSON，保留事实覆盖要求，不再限定 3–10 条事实。

当前新结果使用 `equipment-space-api-v3`：优先检查设备铭牌、用途标签、型号、房间标识和操作标题，并要求再次检查遗漏文字；遮挡时不强行精确计数，不将耳罩、支架等部件数量当作整套设备数量；减少人物和杂物细节，对无法读清的标签注明位置以便后续局部补读。这是 prompt 约束，不代表脚本已自动裁剪或调用第二次 OCR。

首次试跑的三张 `equipment-space-api-v2` 结果继续保留、跳过，不会重标为 v3。新运行的剩余图片使用 v3；已启动的旧进程需停止并重新运行才会加载新规则。

发送的是从原图重新生成的 JPEG，默认长边最多 2400 像素，`detail=high`；不是筛选拼图或之前的 768 像素缩略图。透明图合成白底。非常细小的文字仍可能需要单独放大核查。

默认参数为 low 推理档位、6000 completion token 上限、120 秒请求超时。使用 `max_completion_tokens`，不发送 `temperature` 或旧的 `max_tokens`；依据 [Azure reasoning models 文档](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning)。保留项目现有 HKU 网关路由，不切换端点。

可选参数：

```powershell
& $py -m build.describe_priority_api run --limit 10 --max-edge 3000 --max-completion-tokens 9000 --reasoning-effort low --timeout 180
```

响应为空、截断、拒绝、JSON 格式错误、字段缺失或模型标识异常时，不会记为完成。只对连接/超时、429 和部分服务端错误做有限重试；401/403/400/404 或返回模型不符会立即停下，不对后续几百张重复失败。其他错误连续导致三张失败时也会暂停，排查后重跑即可。

- 401：检查 key 和 `.env`。
- 403：检查 HKU VPN / 网关访问权限。
- 400：检查该网关部署是否支持请求参数。
- 404：检查部署名称与网关路由。

## 怎么区分模型

每张结果仍保存到 `descriptions/<图片ID>.json`，不会覆盖已有 Luna 文件。

| 字段 | 原有 Luna | 新 API 描述 |
|---|---|---|
| `model` | `gpt-6-luna` | `gpt-5-mini` |
| `reasoning_effort` | `low` | 实际请求档位，默认 `low` |
| `prompt_version` | `equipment-space-v1` | 首次三张 `equipment-space-api-v2`；后续 `equipment-space-api-v3` |
| `response_model` | 原记录未提供 | API 返回的模型/快照名称 |
| `generator` | 原记录未提供 | `azure_vision_api` |
| `prompt_sha256` | 原记录未记录 | 实际发送 prompt 的 SHA-256 |

同时保存原图哈希、发送图片的哈希与尺寸、时间、响应 ID、token 用量、完成原因。`prompts/<hash>.txt` 保存实际发送的完整 prompt 快照。旧 Luna 结果不会被补写成“使用过完整 prompt”；两批 prompt 不同，不能仅根据两批结果判断模型孰优孰劣。

用 Excel 打开 **`description_registry.csv`**，按 `model` 筛选，就能看到每张图由哪个模型处理。pending 行尚未生成，不会提前标成 GPT-5 已完成。

- `api_plan.json`：缓存跳过数量、按模型统计、剩余任务和被阻止的记录。
- `api_failures.json`：失败类型、HTTP 状态和尝试时间，不保存 API key 或请求图片正文。
- `summary.json / remaining.json`：运行结束后更新的总进度。也可手动运行下面命令。

```powershell
& $py -m build.describe_priority_images status
```

原图哈希变化或已有描述损坏时，脚本会将记录标记 blocked，不擅自覆盖。即使 prompt 更新，已有有效描述仍跳过；如需重描述，应另建明确的对照批次。

## 全部描述后

先抽查 GPT-5-mini 结果。`suitable:false` 也算完成描述判断，但不会作为图片证据入库。

```powershell
# 全部任务完成且来源校验通过后才能导出；这里不调用 embedding
& $py -m build.describe_priority_images export
```

现有入库适配已经保留每条记录的真实 `description_model`、`description_effort`、`prompt_version` 等元数据，混合批次不会全部误标为 Luna。此脚本本身不执行入库，之后再准备完整证据集合、入库和测试。

本次开发只执行离线计划和模拟 API 测试；实际网关连通性及效果由 VPN 下的三张试跑验证。
