"""Smoke test that mcp SDK imports work in our environment + McpClient class shape."""


def test_mcp_imports():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client
    assert ClientSession is not None
    assert stdio_client is not None
    assert sse_client is not None


def test_mcp_client_class_shape():
    from app.services.agent.mcp_client_transports import McpClient
    assert hasattr(McpClient, "initialize")
    assert hasattr(McpClient, "list_tools")
    assert hasattr(McpClient, "call_tool")
    assert hasattr(McpClient, "ping")
    assert hasattr(McpClient, "close")


def test_open_client_function_exists():
    from app.services.agent.mcp_client_transports import open_client
    assert callable(open_client)
