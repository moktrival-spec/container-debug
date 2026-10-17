import pathlib

print("PID\tPPID\tSTATE\tCOMMAND")
for item in sorted(pathlib.Path("/proc").glob("[0-9]*"), key=lambda p: int(p.name)):
    try:
        fields = dict(line.split(":", 1) for line in (item / "status").read_text().splitlines())
        cmd = (item / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        print(f"{item.name}\t{fields['PPid'].strip()}\t{fields['State'].strip()}\t{cmd}")
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
