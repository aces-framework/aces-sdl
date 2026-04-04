"""Entry point: ``python -m aces.mcp``."""

from aces.mcp.server import create_server

server = create_server()
server.run()
