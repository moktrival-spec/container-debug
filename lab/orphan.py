"""Create one orphan that exits; the long-lived parent does not wait for it."""
import os
import signal
import time

stop = False


def handle_term(signum, frame):
    global stop
    stop = True


signal.signal(signal.SIGTERM, handle_term)
child = os.fork()
if child == 0:
    grandchild = os.fork()
    if grandchild == 0:
        # The intermediate parent is reaped before this process exits.
        time.sleep(0.3)
        print(f"ORPHAN_EXIT pid={os.getpid()} ppid={os.getppid()}", flush=True)
        os._exit(0)
    os._exit(0)
os.waitpid(child, 0)
print(f"READY pid={os.getpid()}", flush=True)
while not stop:
    time.sleep(0.1)
print("CLEANUP_DONE", flush=True)
