#!/usr/bin/env python3
"""Launch the context-bundle local GUI.

    python3 gui/server.py [--host 127.0.0.1] [--port 8765] [--no-open]

Stdlib only (wsgiref) -- binds to localhost by default since this serves
config/bundle contents from the local machine with no authentication,
same trust model as any other localhost dev dashboard.
"""

import argparse
import os
import sys
from wsgiref.simple_server import make_server

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="context-bundle local GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="don't auto-open a browser tab")
    args = parser.parse_args(argv)

    httpd = make_server(args.host, args.port, app)
    url = "http://{}:{}/".format(args.host, args.port)
    print("context-bundle GUI running at {} (Ctrl+C to stop)".format(url))

    if not args.no_open:
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
