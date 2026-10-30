检索已完成，覆盖了 `app.py`、`multipart.py`、`limits.py` 三个文件的全部相关路径。以下为最终审计报告。

---

# 表单与文件上传处理路径资源使用审计报告

**任务**: demo-glm-debug（重复编号 1）
**审计范围**: `app.py`、`multipart.py`、`limits.py` 中表单解析与文件上传路径
**输入到达路径**: 外部请求 → `handle_upload(request)` / `handle_login(request)`（app.py:11、app.py:25）→ `parse_form(request.body)`（multipart.py:6）→ `split_parts` / `read_part`（multipart.py:16、27）→ `FileItem.write_to`（multipart.py:57）

> 说明：app.py:1-3 的模块 docstring 标明这是演示用调试对象（"这不是真实漏洞验证对象"）。以下结论均针对检索到的代码本身。

---

## 发现 1（高）：文件数量限制在完整解析之后才检查，无法约束解析期资源消耗

- **文件与行号**: app.py:13-15；multipart.py:6-22
- **路径**: `request.body` → `parse_form()`（app.py:13）→ 返回后才执行 `within_count_limit(len(files), limit=50)`（app.py:14）
- **原因**: `parse_form`（multipart.py:6-15）在返回前已完成 `body.split(boundary)` 全量切分（multipart.py:21）、所有分段 payload 的物化（multipart.py:31 `part.partition(b"\r\n\r\n")`）以及全部 `FileItem` 对象的构造（multipart.py:11）。数量检查发生在这一切之后。
- **必要条件**: 攻击者可向 `handle_upload` 提交任意大小的 multipart 请求体。
- **可能影响**: 50 个文件的限制只阻止了超额文件写盘，不阻止解析本身——攻击者可提交含数千个分段的请求体，在检查生效前就已耗尽内存/CPU。限制名义上防"数量过多"，实际只防"写盘文件过多"。
- **修复建议**: 将数量检查移入解析循环内部（如 `split_parts`/`parse_form` 中每解析 N 段即中止并返回 413），或在解析前基于 `Content-Length` 预检。

## 发现 2（高）：解析器内部对分段数量、字段数量、单段大小均无任何限制

- **文件与行号**: multipart.py:16-22（`split_parts`）、multipart.py:6-15（`parse_form`）、multipart.py:27-33（`read_part`）、multipart.py:35-41（`_find_boundary`）
- **路径**: `request.body` → `split_parts` → `read_part` → `fields`/`files` 累积
- **原因**:
  - `split_parts` 用 `body.split(boundary)`（multipart.py:21）一次性生成全部分段列表，分段数无上限；
  - 边界值取自请求体自身的 Content-Type 行（multipart.py:38-39），完全由攻击者控制。边界最短为 `--`（`BOUNDARY_PREFIX` + 空值，multipart.py:4、39），极短边界可使切分次数最大化，放大分段数量；
  - `parse_form` 循环中对 `len(fields)`、`len(files)` 无递增上限（multipart.py:8-13）；
  - `read_part` 将每段 payload 完整保留在内存（multipart.py:31），无单段大小上限。
- **必要条件**: 同发现 1。
- **可能影响**: 内存与 CPU 消耗与攻击者输入成正比且无上界；`fields` 字典与 `files` 列表可无限增长。
- **修复建议**: 在 `split_parts` 中限制最大分段数（如超过即抛错/截断）；在 `read_part` 中限制单段 payload 长度；对边界值长度与格式做校验（拒绝过短边界）。

## 发现 3（高）：请求体总大小无限制，`max_body_bytes` 为死代码

- **文件与行号**: limits.py:8-11（定义）；app.py:13、app.py:27（调用点无大小检查）
- **路径**: `request.body` 直接传入 `parse_form`，无前置大小校验
- **原因**: `limits.py` 定义了 `max_body_bytes()` 返回 1 MiB（limits.py:11 `return 1 << 20`），但检索 "max_body_bytes" 仅命中 limits.py 中的定义处，全代码库无任何调用点；app.py 两个入口均直接 `parse_form(request.body)`。
- **必要条件**: 同发现 1。
- **可能影响**: 预期的 1 MiB 请求体上限完全未生效，任意大小的请求体都会被整体读入并解析。
- **修复建议**: 在调用 `parse_form` 前检查 `len(request.body) > max_body_bytes()` 并返回 413；或在读取 body 的层面实施流式限额。
- **证据缺口**: 检索未找到 `request` 对象/`body` 读取处的定义（搜索 "class Request def body" 未返回 Request 类实现）。若存在外层框架在调用 handler 前强制了 body 大小限制，则该限制位于本次未检索到的代码中——基于现有证据无法确认存在此类保护。

## 发现 4（中）：`handle_login` 路径完全没有数量限制

- **文件与行号**: app.py:25-29
- **路径**: `request.body` → `parse_form(request.body)`（app.py:27）→ 结果直接送 `check_password`
- **原因**: 与 `handle_upload` 不同，此处没有任何 `within_count_limit` 调用；虽然文件列表被 `_` 丢弃（app.py:27），但解析过程仍会处理全部分段并将所有 payload 物化到内存。
- **必要条件**: 攻击者可向登录端点提交任意 multipart 请求体。
- **可能影响**: 与发现 1/2 相同的解析期资源耗尽暴露面，且连事后检查都没有。
- **修复建议**: 登录端点应拒绝 multipart 请求或复用统一的大小/数量限制逻辑。

## 发现 5（中）：限制只计文件个数，不计总字节数或总分段数

- **文件与行号**: app.py:14（`within_count_limit(len(files), limit=50)`）；limits.py:4-6；multipart.py:57-66（`write_to`）
- **路径**: `files` 列表 → 数量检查 → `item.write_to(UPLOAD_DIR)`（app.py:18）
- **原因**: 检查仅针对 `len(files)`。50 个文件每个大小无上限（结合发现 3 无总大小限制），非文件字段数量完全不受该检查约束；`write_to` 将完整 payload 写盘（multipart.py:64-65），无单文件大小限制。
- **必要条件**: 攻击者提交 ≤50 个文件字段、但总体积任意大的请求体。
- **可能影响**: 单个"合法"（通过数量检查的）请求即可耗尽内存与磁盘。
- **修复建议**: 增加总字节数上限（可复用 `max_body_bytes`）与单文件大小上限；数量限制应同时覆盖总分段数（含普通字段）。

## 附加观察（超出本次资源审计主题，仅记录）

- **路径拼接未净化**: multipart.py:63 `os.path.join(directory, self.filename)` 中 `filename` 实为表单字段名（来自 `parse_form` 传入的 `name`，multipart.py:11，由 `_header_name` 从攻击者可控的 content-disposition `name=` 属性解析，multipart.py:41-49）。字段名含 `../` 时存在路径穿越写文件的可能。此项属输入验证问题而非资源使用问题，建议另行审计确认。

---

## 已检查范围与局限

**已检查**:
- `app.py` 全部三个入口/辅助函数（`handle_upload`、`handle_login`、`check_password`/`load_user`）；
- `multipart.py` 全部解析函数（`parse_form`、`split_parts`、`read_part`、`_find_boundary`、`_header_name`、`_is_file`、`FileItem.write_to`）；
- `limits.py` 全部函数及其调用点（`within_count_limit` 仅在 app.py:14 被调用一次；`max_body_bytes` 无调用点）。

**局限**:
1. 未检索到 `request` 对象的定义与 `request.body` 的读取实现，无法确认外层是否存在框架级 body 大小限制（见发现 3 的证据缺口）；
2. 未检索到路由/服务器入口代码，无法确认 `handle_upload`/`handle_login` 的实际暴露方式（本地函数还是网络端点）——"攻击者可提交任意请求体"这一必要条件基于 handler 接收 `request` 的签名推断；
3. 行号以检索工具返回的片段标注为准，个别片段行号区间存在重叠，可能有 ±1 行偏差；
4. 该代码为演示桩（app.py:1-3），实际生产环境中对应逻辑可能不同。

**总体结论**: 解析过程（`parse_form`/`split_parts`/`read_part`）内部对输入数量与大小**均无限制**；唯一存在的数量限制（app.py:14，50 个文件）**因在完整解析之后才执行而无法防止解析期资源耗尽**，且不覆盖总字节数、总分段数与登录路径；`max_body_bytes` 定义了 1 MiB 上限但从未被调用，属死代码。