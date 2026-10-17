"""A deliberately small service whose shutdown can be observed."""
import os
import signal
import time

stopping = False


def request_stop(signum, frame):
    global stopping
    stopping = True


if os.environ.get("HANDLE_TERM", "1") == "1":
    signal.signal(signal.SIGTERM, request_stop)
else:
    signal.signal(signal.SIGTERM, signal.SIG_DFL)

print(f"READY pid={os.getpid()} ppid={os.getppid()}", flush=True)
while not stopping:
    time.sleep(0.1)

print("TERM_RECEIVED", flush=True)
print("CLEANUP_BEGIN", flush=True)
time.sleep(float(os.environ.get("CLEANUP_SECONDS", "1")))
print("CLEANUP_DONE", flush=True)
