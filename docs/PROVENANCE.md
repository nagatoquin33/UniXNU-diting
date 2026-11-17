# 记录来源与证据边界（Diting）

本仓库的记录来自三个不同层级。混用它们会把 Pong 的实机历史当成 Diting 的证据，因此每次引用前先确认
记录属于哪一层。

## 三层来源

| 层级 | 内容 | 位置 | 能否当 Diting 证据 |
| --- | --- | --- | --- |
| 上游/官方 | UniXNU 框架、官方移植文档、上游驱动 | `UniXNU/`、unixnu.com 文档、`drivers/` 中标注上游来源的部分 | 契约与实现依据，不是本机结果 |
| Pong 继承 | Nothing Phone 2（同 SM8475）的设备历史、迁移记录与部分驱动实现 | `porting.toml`、`migration/ipados18/`、`drivers/*` 中的 `pong-*` 来源 | **不能**；只作实现参照 |
| Diting 实机 | 在 `diting` 上 `fastboot boot` / Recovery 回读得到的观察 | `AGENTS.md` 时间序条目、[`STATUS.md`](STATUS.md)、`D:\ai\diting\build-work\ramoops-*.bin` | **可以**，并注明镜像与日志路径 |

## 已知的 Pong 继承记录（易被误引）

- **音频/铃声**：`migration/ipados18/services144/145` 等“TFA9873 音频/铃声可闻”的记录来自 **Pong 硬件**；
  Diting 的 live DT 是双 **CS35L41**（`wsa883x` disabled、无 TFA9873），尚未接入，不能引用为 Diting 音频证据。
- **部分 Wi-Fi/存储结论**：早期 Wi-Fi 关联、UFS/窗口几何等“已工作”描述可能来自 Pong 或其它 SM8475 参考设备；
  它们可以提示实现路径，但 Diting 的当前结果只看 `AGENTS.md` 与 `STATUS.md`。
- **驱动实现本身**：`drivers/` 的 `pong-*` 代码是 vendored 参考实现，保留原始许可证与来源；代码存在不等于
  本机功能验证。

## 构建来源与机器身份

- SM8475 seed 现由本仓库 `migration/format2/soc-seed` 提供（来源 `Chengdong-Yu/UniXNU-pong @ f62243e`，见 `migration/format2/soc-commit.json`）；构建 feed 不再访问 Pong 仓库。
- `drivers/*` 中指向 Pong `migration/ipados18/` 的 `services*`/`upstream-*` 链接是历史来源，保留但不算 Diting 证据。
- 机器身份字段（ADT `diting,physical-model`、组件 `repository`、脚本 `board`/`device` 元数据）写 Diting / Redmi K50 Ultra，不写 Nothing Phone (2)。

## 如何读 `porting.toml` 的 evidence

每条 `evidence` 同时带 `kind` 与 `reported_kind`：

- `kind = "source"`：仅说明代码/配置位置，不是运行结果。
- `reported_kind = "host-build"`：主机侧构建/静态检查通过；**不证明**真机功能。
- `reported_kind = "device-*"`（`device` / `device-boot` / `device-capture`）：记录者所在设备的观察。
  对 Pong 继承条目，这台设备是 Pong；只有写入 `AGENTS.md`/`STATUS.md` 的 Diting 条目才是本机证据。

引用时保留原 `provenance`/描述（例如 “Pong live Android DT”），不要改写成 Diting；需要 Diting 结论时，
以带镜像哈希与日志路径的实机条目为准。

## 写入纪律

- 新实机结论：先写 `AGENTS.md`（输入/命令/观察/结论/下一步，含 sha256 与证据路径），再同步 `STATUS.md`。
- Pong 记录可以保留、可以引用为“实现参照”，但不得据此声称 Diting 已通过。
- 不复制：固件二进制、Apple 还原资产（IPSW/kernelcache/OS/userdata 镜像）、Firehose SDK 头、unique-chip-id；
  许可与清单见 [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)。
