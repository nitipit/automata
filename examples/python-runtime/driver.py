"""External independent-process driver for the SAME persistent kernel."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

DEFAULT_SOCKET = Path(__file__).resolve().parent / ".run" / "agent.sock"


async def request(message, socket=DEFAULT_SOCKET):
    reader, writer = await asyncio.open_unix_connection(str(socket), limit=131072)
    try:
        writer.write((json.dumps(message) + "\n").encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), 60)
        if not raw:
            raise RuntimeError("Server closed without reply; code may have executed; do not replay")
        return json.loads(raw)
    finally:
        writer.close()
        await writer.wait_closed()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["execute", "status", "interrupt", "restart"])
    parser.add_argument("code", nargs="?", help="Python code, or '-' for stdin (driver only)")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--socket", type=Path, default=DEFAULT_SOCKET)
    args = parser.parse_args()
    code = sys.stdin.read() if args.code == "-" else args.code
    if args.command == "execute" and code is None:
        parser.error("execute requires code")
    try:
        reply = asyncio.run(request(dict(command=args.command, code=code,
                                         timeout=args.timeout), args.socket))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(reply, indent=2))
    result = reply.get("result", {})
    return 0 if reply["ok"] and result.get("status", "ok") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
