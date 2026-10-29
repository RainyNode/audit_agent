# audit_agent：共用审计 Agent 主循环（骨架 v0.1）

对应开题报告第四节的"最小接口约定"。组长负责主循环；A/B 的模型接入、
C 的检索工具、D 的案例、E 的记录表都接在这套骨架上。

## 目录结构

```
code/
├── audit_agent/            # 共用程序（组长维护）
│   ├── loop.py             # 主循环：模型请求 -> 工具校验/执行/回填 -> 预算收尾
│   ├── budget.py           # 四项预算：时限 / 模型请求 / 检索次数 / 代码字符数
│   ├── recorder.py         # 运行记录：events.jsonl / raw/ / report.md / summary.json
│   ├── config.py           # 任务配置加载
│   ├── llm/                # 模型适配层（A、B 的接入点）
│   │   ├── base.py         #   统一接口：messages + tools -> LLMResponse
│   │   ├── openai_compat.py#   GLM / DeepSeek 共用的 OpenAI 兼容适配器
│   │   └── mock.py         #   无密钥自测适配器
│   └── tools/              # 只读工具层（C 的接入点）
│       ├── base.py         #   工具白名单注册表
│       └── retrieve_v1.py  #   V1 关键词检索（文本扫描最小版）
├── tasks/                  # 任务配置（D 填审计范围，匿名不含答案）
├── sample_repo/            # 演示源码（联调用，非真实案例）
└── runs/                   # 运行记录输出（每次运行一个 run_id 目录，只追加归档）
```

## 快速开始

```bash
git clone https://github.com/RainyNode/audit_agent.git   # 组员克隆仓库
cd audit_agent                                           # 组长本机已在 code/ 目录，可省略
python -m audit_agent --task tasks/demo_starlette.json      # Mock 跑通全流程，无需密钥
python -m audit_agent --task tasks/demo_budget_probe.json   # 演示预算耗尽的收尾路径
```

跑完后查看 `runs/<run_id>/`：

| 文件 | 内容 | 谁用 |
| --- | --- | --- |
| `events.jsonl` | 逐轮事件：模型请求/响应、工具请求/结果、异常、起止时间 | E 核对过程 |
| `summary.json` | 一次运行的汇总：run_id、模型、策略、用量、结束原因 | E 记录表的数据源 |
| `report.md` | 模型最终审计报告（预算收尾产生的报告同样保存在此） | D 核查 |
| `raw/` | 模型原始响应 | A/B 排查接口差异 |

## 接入真实模型（GLM / DeepSeek）

1. `pip install -r requirements.txt`
2. 设置环境变量（PowerShell）：`$env:AUDIT_LLM_API_KEY="你的key"`
   （也可在任务配置里改 `api_key_env` 用别的变量名，如 `GLM_API_KEY` / `DEEPSEEK_API_KEY`）
3. 修改任务配置的 `model` 段：

```json
"model": {
  "adapter": "glm",              // 或 "deepseek"
  "model_name": "由 A/B 核实后填准确型号",
  "api_key_env": "AUDIT_LLM_API_KEY"
}
```

内置接口地址在 `audit_agent/llm/__init__.py`，如官方地址变更由 A/B 核实后修改并写入联调记录。

## 各成员接入点（接口约定的落地位置）

| 成员 | 接入点 | 本周要做的事 |
| --- | --- | --- |
| A（GLM） | `llm/openai_compat.py` | 核实型号与用量字段，配好环境变量后真实调用一次，把 raw/ 里的用量字段反馈给 E |
| B（DeepSeek） | `llm/openai_compat.py` | 同上；与 A 共用适配器，接口差异写进事件记录 |
| C（代码选择） | `tools/retrieve_v1.py` | 替换为基于索引的实现（文件/函数/行号），保持 `Tool("retrieve_code", ...)` 接口不变，再加 V2/V3 |
| D（案例核查） | `tasks/*.json` | 新案例 = 新任务配置：`repo_path` 指向固定版本源码，`scope` 匿名、不含 CVE 与答案位置 |
| E（评价资源） | `runs/<run_id>/summary.json` | 按 summary 字段设计记录表；费用 = Token 用量 × 单价，单价另存并注明查询日期 |

## 主循环规则（与开题报告条款的对应）

- 只允许调用登记的只读工具；参数不合法把错误回给模型，模型可在剩余预算内修正（第四节）
- 四项预算：总时限 / 模型请求次数 / 检索次数 / 累计代码字符数；重复返回的代码照常计数（第五节）
- 接口异常至多自动重试一次，重试消耗请求预算并保留事件（第五节）
- 预算耗尽时用收尾提示要求模型基于已有证据出报告；没有剩余请求额度则如实记 `budget_*` 结束、无报告
- 密钥只从环境变量读取，不进入配置和任何记录文件（第八节）

## 版本与仓库管理

- 代码仓库：https://github.com/RainyNode/audit_agent ，组员克隆后**只改自己的接入点**，公共部分（主循环/预算/记录）的修改由组长统一做
- 程序版本 = `0.1.0 + git 短提交号`，每次运行自动读取并写入记录（version.py）；zip 分发或未装 git 时回退为 `0.1.0`
- `runs/` 运行记录随仓库提交归档：只追加、不删改，这正是开题要求的"原始记录只追加归档"
- `PROMPT_VERSION = prompt-v0.1`，正式实验开始前由 E 冻结；提示词在 `loop.py` 顶部，改动需组长登记
