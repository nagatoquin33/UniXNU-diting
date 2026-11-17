# UniXNU-sm8475-common

SM8475（Cape）共享硬件描述，来自 NothingOSS SM8475 源码和 Diting Android 设备树。包含 4/3/1 CPU 拓扑、GICv3、19.2 MHz 时钟、UFS 与 PCIe0 控制器资源。板级 GPIO、QCA6490、面板、固件和 DRAM 保留区由 UniXNU-diting 提供。

这是本机版本化的 SoC 仓库；尚未发布远程仓库。Diting feed 固定本仓库提交，使用其 format2 构建入口。音频与 Wi-Fi 的实际可用性由设备日志单独记录。

来源：`Chengdong-Yu/UniXNU-pong @ f62243e` 的 `migration/format2/soc-seed`；现由本仓库维护，CI 不再访问该远程仓库。Pong 的历史记录仍保留在 `migration/ipados18/`。
