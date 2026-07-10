from natsort import natsorted
import datetime, time
import sys, os, subprocess
import glob
import threading
from queue import Queue

start_time = datetime.datetime(2024, 1, 1, 0, 0)
end_time = datetime.datetime(2026, 6, 30, 0, 0)
root_dir = "/home/samba/xiaomi_camera_videos/78DF720F87D6/"
prefix = "0"
upload_dir = "/apps/bypy/客厅"
baidupcs_bin = "./BaiduPCS-Go-v4.0.1-linux-amd64/BaiduPCS-Go"
zip_password = "TNAzi"
hour_range = (5, 23)  # (0, 24) 全天  (5, 23) 白天

# 上传队列，maxsize=1 保证最多只有 1 个 .7z 文件在磁盘等待上传
# 主线程 put 时如果队列已满会自动阻塞，等上传线程消费完才继续
upload_queue = Queue(maxsize=4)

def upload_worker():
    """后台上传线程：逐个消费队列中的日期，上传 .7z 到百度网盘后清理文件"""
    while True:
        day_str = upload_queue.get()
        if day_str is None:
            upload_queue.task_done()
            break
        print(f"upload {prefix}_{day_str}.mp4.7z")
        subprocess.run(
            f'{baidupcs_bin} u --norapid '
            f'{prefix}_{day_str}.mp4.7z {upload_dir} '
            f'&& rm -rf {prefix}_{day_str}.mp4 {prefix}_{day_str}.mp4.7z',
            shell=True, check=True
        )
        upload_queue.task_done()

upload_thread = threading.Thread(target=upload_worker, daemon=True)
upload_thread.start()

# 主循环：逐个日期做 拼接 → 压缩，上传交给后台线程异步执行
# 形成流水线：Day N 压缩完成后立刻开始 Day N+1 的拼接压缩，
#            同时 Day N 的 .7z 由后台线程上传，两者并行
for i in range((end_time - start_time).days + 1):
    day = start_time + datetime.timedelta(days=i)
    day_str = day.strftime("%Y%m%d")

    # 收集该天指定时段的小米摄像头片段，按文件名时间排序
    all_files = []
    for h in range(*hour_range):
        hour_dir = root_dir + day.strftime("%Y%m%d") + f"{h:02d}"
        if not os.path.exists(hour_dir):
            continue
        for root, dirs, files in os.walk(hour_dir):
            files = natsorted(files)
            for file in files:
                if file.endswith('.mp4'):
                    all_files.append(os.path.join(root, file))

    if not all_files:
        continue

    # 写入 concat demuxer 需要的文件列表
    file_list = f"{prefix}_file.txt"
    with open(file_list, 'w') as fid:
        for f in all_files:
            print('file ' + f, file=fid)

    # 拼接：ffmpeg concat 将多个分段合并为一个完整视频
    print(f"merge {prefix}_{day_str}.mp4")
    subprocess.run(
        f'ffmpeg -stats -loglevel error -y -f concat -safe 0 -i {file_list} '
        f'-c copy -strict -2 {prefix}_{day_str}.mp4',
        shell=True, check=True
    )

    # 压缩：7z 加密压缩，节省空间并保护隐私
    print(f"compress {prefix}_{day_str}.mp4")
    subprocess.run(
        f'7z a -bsp1 -p{zip_password} {prefix}_{day_str}.mp4.7z {prefix}_{day_str}.mp4',
        shell=True, check=True
    )
    # 压缩完成后立即删除原始 .mp4，释放磁盘空间
    os.remove(f"{prefix}_{day_str}.mp4")

    # 将日期放入上传队列，交给后台线程上传
    # 如果队列满（已有 1 个待上传），这里会阻塞等待，保证磁盘不堆积
    upload_queue.put(day_str)

# 通知上传线程退出，并等待所有上传完成
upload_queue.put(None)
upload_thread.join()
