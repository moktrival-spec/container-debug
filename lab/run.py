"""Run Docker cases and retain logs. No third-party Python dependencies."""
import argparse
import datetime
import json
import pathlib
import subprocess
import time
import uuid

HERE = pathlib.Path(__file__).resolve().parent


def docker(*args, check=True):
    result = subprocess.run(["docker", *args], text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError("Docker command failed: " + repr(args) + "\n" + result.stdout + result.stderr)
    return result


def run_case(image, out, label, command, opts, timeout, expected):
    name = "mc-stop-" + label + "-" + uuid.uuid4().hex[:8]
    docker("run", "-d", "--name", name, "--label", "mc-stop-lab=true",
           *opts, image, *command)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            log = docker("logs", name).stdout
            if "READY" in log:
                break
            if docker("inspect", "-f", "{{.State.Running}}", name).stdout.strip() != "true":
                raise RuntimeError(f"{label}: exited before READY: {log}")
            time.sleep(0.1)
        else:
            raise RuntimeError(f"{label}: no READY within 15 seconds")
        # Read inside the container: these PIDs belong to its PID namespace.
        probe = "import pathlib; print(pathlib.Path('/proc/1/cmdline').read_bytes().replace(bytes([0]), b' ').decode())"
        pid1 = docker("exec", name, "python3", "-c", probe).stdout.strip()
        zombie_count = None
        if "zombies" in expected:
            time.sleep(0.7)
            count = "import pathlib; print(sum('State:\\tZ ' in p.read_text() for p in pathlib.Path('/proc').glob('[0-9]*/status')))"
            zombie_count = int(docker("exec", name, "python3", "-c", count).stdout.strip())
        tree = docker("exec", name, "python3", "/lab/proc_tree.py").stdout
        (out / f"{label}-processes.txt").write_text(tree, encoding="utf-8")
        start = time.monotonic()
        docker("stop", "--timeout", str(timeout), name)
        elapsed = time.monotonic() - start
        state = json.loads(docker("inspect", name).stdout)[0]["State"]
        logs = docker("logs", name)
        body = logs.stdout + logs.stderr
        (out / f"{label}.log").write_text(body, encoding="utf-8")
        actual = {"term": "TERM_RECEIVED" in body,
                  "done": "CLEANUP_DONE" in body, "exit": state["ExitCode"]}
        if zombie_count is not None:
            actual["zombies"] = zombie_count
        result = dict(case=label, pid1=pid1, seconds=round(elapsed, 3),
                      actual=actual, expected=expected,
                      oom_killed=state["OOMKilled"], passed=actual == expected)
        (out / f"{label}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
        return result
    finally:
        # Only this invocation's uniquely named container is removed.
        docker("rm", "-f", name, check=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="mc-stop-lab:local")
    parser.add_argument("--base-image", default="python:3.12-slim-bookworm")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    docker("info")
    out = HERE / "results" / (datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    out.mkdir(parents=True)
    if not args.no_build:
        build = docker("build", "--build-arg", "BASE_IMAGE=" + args.base_image,
                       "-t", args.image, str(HERE), check=False)
        (out / "build.log").write_text(build.stdout + build.stderr, encoding="utf-8")
        if build.returncode:
            raise RuntimeError("Docker build failed:\n" + build.stdout + build.stderr)
    (out / "base-image-inspect.json").write_text(docker("image", "inspect", args.base_image).stdout, encoding="utf-8")
    probe = "import platform,os; print(platform.python_version()); print(os.readlink('/bin/sh')); print(open('/etc/os-release').read())"
    (out / "container-environment.txt").write_text(docker("run", "--rm", args.image, "python3", "-c", probe).stdout, encoding="utf-8")
    (out / "docker-version.txt").write_text(docker("version").stdout, encoding="utf-8")
    (out / "image-inspect.json").write_text(docker("image", "inspect", args.image).stdout, encoding="utf-8")
    ok = {"term": True, "done": True, "exit": 0}
    killed = {"term": False, "done": False, "exit": 137}
    cases = [
        ("bad-shell", ["sh", "/lab/bad.sh"], [], 3, killed),
        ("exec", ["sh", "/lab/good.sh"], [], 3, ok),
        ("init-exec", ["sh", "/lab/good.sh"], ["--init"], 3, ok),
        ("init-bad-shell", ["sh", "/lab/bad.sh"], ["--init"], 3,
         {"term": False, "done": False, "exit": 143}),
        ("slow-3s", ["sh", "/lab/good.sh"], ["-e", "CLEANUP_SECONDS=5"], 3,
         {"term": True, "done": False, "exit": 137}),
        ("slow-8s", ["sh", "/lab/good.sh"], ["-e", "CLEANUP_SECONDS=5"], 8, ok),
        ("default-pid1", ["sh", "/lab/good.sh"], ["-e", "HANDLE_TERM=0"], 3, killed),
        ("default-init", ["sh", "/lab/good.sh"], ["--init", "-e", "HANDLE_TERM=0"], 3,
         {"term": False, "done": False, "exit": 143}),
        ("orphan-pid1", ["python3", "-u", "/lab/orphan.py"], [], 3,
         {"term": False, "done": True, "exit": 0, "zombies": 1}),
        ("orphan-init", ["python3", "-u", "/lab/orphan.py"], ["--init"], 3,
         {"term": False, "done": True, "exit": 0, "zombies": 0}),
    ]
    results = [run_case(args.image, out, *case) for case in cases]
    (out / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("Evidence:", out)
    raise SystemExit(0 if all(x["passed"] for x in results) else 1)


if __name__ == "__main__":
    main()
