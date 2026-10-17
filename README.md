# container-debug

「机器与代码」的容器排障示例。第一个案例对应《为什么 docker stop 了，程序却没有正常退出？》：从 Shell 包装脚本追踪 SIGTERM，区分信号没有送到、清理超时和 init 提前退出。

## 跑起来

需要 Git、Python 3 和可正常运行 Linux 容器的 Docker。Python 运行器只用标准库，不需要 pip 安装依赖。默认构建还需要访问 Docker Hub；已有本地基础镜像的用法见 lab README。

```bash
git clone https://github.com/moktrival-spec/container-debug.git
cd container-debug/lab
python3 run.py
```

Windows 原生终端可以使用 `py -3 run.py`，Docker Desktop 需处于 Linux 容器模式；手动操作示例按 Bash 编写。

运行器会在每个服务打印 `READY` 后调用 `docker stop`，保存进程列表、日志、退出码和 OOM 状态，完成后移除自己创建的容器。结果位于 `lab/results/`。实验镜像保留以便继续观察。

## 从哪里读

- [lab/README.md](lab/README.md)：环境要求、十组对照、逐步操作、重复运行和清理。
- [lab/service.py](lab/service.py)：处理 SIGTERM 与模拟清理。
- [lab/bad.sh](lab/bad.sh) / [lab/good.sh](lab/good.sh)：保留 Shell 与使用 exec 的区别。
- [lab/orphan.py](lab/orphan.py)：孤儿后代与退出状态回收。
- [lab/run.py](lab/run.py)：自动执行全部十组。

默认基础镜像是 `python:3.12-slim-bookworm`。README 中列出各组要验证的预期行为；实际输出保存在自己本机的 `results/` 中，不提交到仓库。不同 Shell、init 和进程结构可能改变部分现象，耗时也不应与文章中的单次观测逐毫秒对齐。

这些代码用来观察进程和信号，不是生产服务的退出模板。真实应用仍需处理停止接单、在途任务、业务确认和子进程等待。
