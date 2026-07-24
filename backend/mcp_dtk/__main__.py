"""python -m mcp_dtk 入口。"""
from mcp_dtk.server import server

if __name__ == "__main__":
    server.run(transport="stdio")
