# docker stop：从启动脚本追到退出日志

这组代码对应《为什么 docker stop 了，程序却没有正常退出？》。可以先跑完十组对照，再挑一个结果手动观察。

## 1. 准备环境与代码

- Git；手动命令使用 Bash（Linux、macOS、WSL 或 Git Bash）。
- 可访问的 Docker daemon，运行 **Linux 容器**；`docker info` 必须成功。普通用户需要已有的 Docker 访问权限。
- 自动运行器需要宿主机 Python 3，只使用标准库。手动观察只需要 Docker 与 Git，Python 在容器里运行。
- Docker CLI 需要支持 `docker stop --timeout`，并支持 `docker run --init`。
- 使用独立 PID 命名空间，不增加 `--pid=host`、`--pid=container:...` 或 `-t`。这些参数会改变本文研究的条件。

从零开始：

```bash
git clone https://github.com/moktrival-spec/container-debug.git
cd container-debug/lab
docker info
```

如果已经克隆仓库，直接进入它的 `lab` 目录即可，后续命令都从这个目录执行。Windows Docker Desktop 需切换到 Linux 容器模式；在原生 PowerShell 中运行自动脚本时，可以把 `python3` 换成 `py -3`。下文的多行反斜杠续行按 Bash 语法书写。

## 2. 自动跑完十组

```bash
python3 run.py
```

默认使用 `python:3.12-slim-bookworm` 构建 `mc-stop-lab:local`。构建需要能访问 Docker Hub，或者本机已经有可用的对应镜像。

运行器会等到每组服务打印 `READY`，再保存容器内的 PID 1、进程列表，调用停止命令，记录退出码、OOMKilled 和应用日志。全部符合预期时进程退出码为 0，有不符时为 1。不要只看运行器的退出码，还应打开结果文件判断是哪一个条件发生了变化。

结果在 `results/<时间-随机标识>/`：`summary.json` 汇总全部用例；每组另有 JSON、应用日志和进程快照。耗时包含 Docker CLI 调用成本，不是精密性能基准。

容器名带有本轮随机后缀，结束时只清理本轮创建的容器。实验镜像保留，重复运行会重新构建相同标签；需要隔离标签可以指定 `--image mc-stop-lab:my-run`。脚本不执行 prune，不挂载宿主目录，也不暴露端口。

### 访问不了 Docker Hub，或想固定基础镜像

可以使用本机已有的 Linux 镜像，但它必须包含 `python3` 和 `/bin/sh`。以下名称是示例，请替换成自己的镜像名：

```bash
python3 run.py --base-image my-python-base:local
```

手动构建时对应的参数是：

```bash
docker build --build-arg BASE_IMAGE=my-python-base:local \
  -t mc-stop-lab:local .
```

需要固定环境时，可以在 `--base-image` 中指定自己实际解析出的 `仓库名@sha256:摘要`，不要把“摘要”字样原样粘贴执行。运行器会保存基础镜像和实验镜像的 inspect 元数据；这些本地结果可能包含自己的镜像信息，因此 `results/` 已被 Git 忽略。

预期结果对应本文使用的 dash 与 init 行为。换成另一种 Shell、init 或进程结构后，个别结果可能不同，应结合日志解释差异，不应直接修改预期来让脚本通过。文章中的原始观测不随代码上传；请用本机产生的日志、进程快照和 JSON 结果核验自己的运行。

## 3. 十组分别看什么

| 用例 | 改变的条件 | 预期观察 |
|---|---|---|
| bad-shell | Shell 是 PID 1，无转发 | Python 无 TERM 标记，无清理完成，137 |
| exec | Shell exec 为 Python，清理 1 秒 | 收到 TERM，清理完成，0 |
| init-exec | --init + exec | 收到 TERM，清理完成，0 |
| init-bad-shell | --init + 错误 Shell 包装 | 本例 Shell 先退出，Python 未清理，143 |
| slow-3s | 清理 5 秒，预算 3 秒 | 收到 TERM，清理未完成，137 |
| slow-8s | 清理 5 秒，预算 8 秒 | 收到 TERM，清理完成，0 |
| default-pid1 | Python PID 1，恢复 SIGTERM 默认动作 | 不走清理，预算耗尽，137 |
| default-init | 同一应用放到 --init 下 | 默认 SIGTERM 终止，无业务清理，143 |
| orphan-pid1 | 应用 PID 1 收养孤儿但不回收 | 停止前留下 1 个 Z 状态进程 |
| orphan-init | init 收养并回收孤儿 | 停止前没有留下 Z 状态进程 |

表中的 TERM 和清理状态指 Python 业务进程。`orphan.py` 安装了 SIGTERM 处理函数，但没有打印 `TERM_RECEIVED`，因此它的 `term=false` 只表示没有这条标记，不能解读为没有收到信号。两组孤儿用例的僵尸数都在停止之前观察。

## 4. 手动跟着文章走

先构建一次。Dockerfile 已经把 `bad.sh`、`good.sh` 和三个 Python 程序一起复制进镜像，切换启动方式不需要重新 build；修改源码后则需要重新构建。

```bash
docker build -t mc-stop-lab:local .
```

每一小节分为两段命令：先运行第一段，看到 `READY` 后，**按 Ctrl+C 退出日志跟随**，再执行第二段。Ctrl+C 只退出 `docker logs -f`，不会停止后台容器。如果迟迟没有 READY，先检查 `docker logs`、`docker ps -a` 和镜像构建结果，不要继续停止命令。

手动容器没有加 `--rm`，便于停下后读取退出码。每节最后的 `docker rm` 会删除该节已停止的容器，读取完日志再执行。

### A. 保留 Shell 包装层

```bash
docker run -d --name stop-bad \
  mc-stop-lab:local
docker logs -f stop-bad
```

看到 READY 并按 Ctrl+C 后：

```bash
docker exec stop-bad python3 /lab/proc_tree.py
time docker stop --timeout 3 stop-bad
docker logs stop-bad
docker inspect -f '{{.State.ExitCode}} {{.State.OOMKilled}}' stop-bad
docker rm stop-bad
```

Python 日志通常停在 READY，容器退出码为 137，OOMKilled 为 false。

### B. 用 exec 替换 Shell

```bash
docker run -d --name stop-good \
  mc-stop-lab:local sh /lab/good.sh
docker logs -f stop-good
```

看到 READY 并按 Ctrl+C 后：

```bash
docker exec stop-good python3 /lab/proc_tree.py
time docker stop --timeout 3 stop-good
docker logs stop-good
docker inspect -f '{{.State.ExitCode}} {{.State.OOMKilled}}' stop-good
docker rm stop-good
```

日志出现 TERM_RECEIVED、CLEANUP_BEGIN、CLEANUP_DONE，退出码为 0。

### C. 清理 5 秒，只等 3 秒

```bash
docker run -d -e CLEANUP_SECONDS=5 --name stop-slow \
  mc-stop-lab:local sh /lab/good.sh
docker logs -f stop-slow
```

看到 READY 并按 Ctrl+C 后：

```bash
docker exec stop-slow python3 /lab/proc_tree.py
time docker stop --timeout 3 stop-slow
docker logs stop-slow
docker inspect -f '{{.State.ExitCode}} {{.State.OOMKilled}}' stop-slow
docker rm stop-slow
```

出现 TERM_RECEIVED 和 CLEANUP_BEGIN，没有 CLEANUP_DONE，退出码为 137。

### D. 同样清理 5 秒，这次等 8 秒

```bash
docker run -d -e CLEANUP_SECONDS=5 --name stop-slow-8 \
  mc-stop-lab:local sh /lab/good.sh
docker logs -f stop-slow-8
```

看到 READY 并按 Ctrl+C 后：

```bash
docker exec stop-slow-8 python3 /lab/proc_tree.py
time docker stop --timeout 8 stop-slow-8
docker logs stop-slow-8
docker inspect -f '{{.State.ExitCode}} {{.State.OOMKilled}}' stop-slow-8
docker rm stop-slow-8
```

出现 CLEANUP_DONE，退出码为 0。使用新容器，与上一节的结果分别保留。

### E. init + exec

```bash
docker run -d --init --name stop-init \
  mc-stop-lab:local sh /lab/good.sh
docker logs -f stop-init
```

看到 READY 并按 Ctrl+C 后：

```bash
docker exec stop-init python3 /lab/proc_tree.py
time docker stop --timeout 3 stop-init
docker logs stop-init
docker inspect -f '{{.State.ExitCode}} {{.State.OOMKilled}}' stop-init
docker rm stop-init
```

PID 1 是 init，Python 是直接子进程；清理完成，退出码为 0。

### F. 只加 init，仍保留错误包装

```bash
docker run -d --init --name stop-init-bad \
  mc-stop-lab:local sh /lab/bad.sh
docker logs -f stop-init-bad
```

看到 READY 并按 Ctrl+C 后：

```bash
docker exec stop-init-bad python3 /lab/proc_tree.py
time docker stop --timeout 3 stop-init-bad
docker logs stop-init-bad
docker inspect -f '{{.State.ExitCode}} {{.State.OOMKilled}}' stop-init-bad
docker rm stop-init-bad
```

在本文的 dash 环境中，容器很快停止，退出码为 143，但 Python 没有 TERM 标记，也没有清理完成标记。

## 5. 默认信号与孤儿回收

这些对照已经包含在自动运行器中。想手动检查时，下面给出其中一侧；观察完后，再用说明中的另一侧参数重跑。

### 去掉 SIGTERM 处理函数

```bash
docker run -d --name stop-default \
  -e HANDLE_TERM=0 mc-stop-lab:local sh /lab/good.sh
docker logs -f stop-default
```

看到 READY 并按 Ctrl+C 后：

```bash
docker exec stop-default python3 /lab/proc_tree.py
docker stop --timeout 3 stop-default
docker logs stop-default
docker inspect -f '{{.State.ExitCode}} {{.State.OOMKilled}}' stop-default
docker rm stop-default
```

这时 Python 是 PID 1，预期超时后以 137 结束。删除这个已停止的容器后，再在同一条 `docker run` 中、镜像名前加入 `--init`，其余步骤不变：普通子进程的 SIGTERM 默认动作会终止 Python，预期退出码为 143。两侧都没有业务清理完成标记。

### 观察孤儿退出后的 Z 状态

```bash
docker run -d --name stop-orphan \
  mc-stop-lab:local python3 -u /lab/orphan.py
docker logs -f stop-orphan
```

这次等到 `READY` 和 `ORPHAN_EXIT` 两条日志都出现，再按 Ctrl+C。因为这个问题研究的是进程运行期间有没有回收退出状态，必须在 stop 之前观察：

```bash
sleep 1
docker exec stop-orphan python3 /lab/proc_tree.py
docker stop --timeout 3 stop-orphan
docker logs stop-orphan
docker inspect -f '{{.State.ExitCode}} {{.State.OOMKilled}}' stop-orphan
docker rm stop-orphan
```

没有 init 时，应用当 PID 1，却不回收被收养的后代，进程表留下一个 Z 状态。删除容器后，在同一条 `docker run` 的镜像名前加入 `--init`，再重复上述观察：本例的孤儿后代由 init 回收，不再留下 Z 状态。`proc_tree.py` 会列出用于查看进程的 Python 进程本身，这是正常现象。

## 6. 重复运行与清理

如果提示容器名已存在，先用 `docker ps -a` 查看。确认是自己之前创建且已经停止的演示容器后，读取需要保留的日志，再用 `docker rm 容器名` 删除。不要为了重试而批量删除其他容器。

按文章操作但没有逐节清理时，可以先查看这些明确的演示名称：

```bash
docker ps -a --filter name=stop-
```

下面的命令只删除这六个名称所对应的、已经停止的容器；正在运行的容器会被 Docker 拒绝删除。只在确认它们是自己本次创建的演示容器后执行：

```bash
docker rm stop-bad stop-good stop-slow stop-slow-8 stop-init stop-init-bad
```

不再使用默认实验镜像时可运行 `docker image rm mc-stop-lab:local`。没有删除的引用容器可能让 Docker 拒绝删除镜像，按提示先处理自己创建的容器即可，不需要 prune。

## 7. 代码边界

这里只模拟一段清理耗时，不真的持久化业务数据。Python 信号处理在主线程执行，长期阻塞的扩展调用、不同运行时和真实 I/O 都可能影响响应时间。真实服务还需停止接单、为清理设置截止时间、完成事务或消息确认，并等待自己创建的工作进程。

孤儿示例依赖 Linux `fork()`，由 Linux 容器运行；不要用原生 Windows Python 直接运行 `orphan.py`。自动运行器 `run.py` 则可以从 Windows、Linux 或 macOS 主机调用 Docker。
