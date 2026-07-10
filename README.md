# 小米摄像头视频自动归档工具

将小米摄像头录制的分钟级视频片段，按天合并、加密压缩后上传到百度网盘。

## 需求背景

小米摄像头通过 Samba 协议将录像片段保存到 NAS，每个文件约 1 分钟。本工具按天收集这些零散片段，合并为完整视频，加密压缩后上传到百度网盘存档。

## 工作流程

```
Samba 录像目录  →  按天/按小时收集 .mp4 片段
                        ↓
                   ffmpeg concat 合并为单文件（流复制，不重编码）
                        ↓
                   7z 加密压缩为 .7z（AES-256）
                        ↓
                   删除原始 .mp4，释放磁盘
                        ↓
                   后台线程上传到百度网盘（BaiduPCS-Go）
                        ↓
                   上传完成后删除本地 .7z
```

## 流水线设计

合并压缩（主线程）和上传（后台线程）并行执行，通过 Python `queue.Queue` 解耦：

- `Queue(maxsize=4)` — 最多积压 4 个待上传的 `.7z`
- 队列满时主线程自动阻塞，磁盘不会无限堆积

## 依赖

### 系统工具

- **ffmpeg** — 视频拼接（需支持 concat demuxer）
- **p7zip** (7z) — 加密压缩
- **[BaiduPCS-Go](https://github.com/qjfoidnh/BaiduPCS-Go)** — 百度网盘 CLI 上传工具（首次使用需执行 `BaiduPCS-Go login` 扫码授权）

### Python 包

```bash
pip install natsort
```

## 配置

脚本开头配置区可直接修改：

```python
start_time   = datetime.datetime(2024, 1, 1, 0, 0)   # 开始日期
end_time     = datetime.datetime(2026, 6, 30, 0, 0)   # 结束日期
root_dir     = "/path/to/samba/videos/"                # 摄像头录像 Samba 目录
prefix       = "0"                                     # 文件前缀（多摄像头区分）
upload_dir   = "/apps/bypy/客厅"                        # 百度网盘上传路径
baidupcs_bin = "./BaiduPCS-Go-xxx/BaiduPCS-Go"        # BaiduPCS-Go 路径
zip_password = "TNAzi"                             # 7z 加密密码                             # 7z 加密密码
hour_range   = (5, 23)                                 # 截取时段：(0,24)全天 (5,23)白天
```

## 多摄像头

不同摄像头复制脚本并修改 `prefix`、`root_dir`、`upload_dir` 即可。
