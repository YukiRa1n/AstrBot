"""连接管理模块 - 路径/token/socket/发送

从 __main__.py 提取的连接相关功能，不导入 astrbot 框架。
"""

import json
import os
import socket
import sys
import tempfile
import uuid
from pathlib import Path


def _get_source_root() -> Path:
    """源码安装根目录（通过 __file__ 向上定位）。"""
    return Path(__file__).resolve().parents[3]


def _get_working_root() -> Path | None:
    """Locate the nearest AstrBot instance rooted at the current directory."""
    current = Path.cwd().resolve()
    candidates = (current, *current.parents)

    for candidate in candidates:
        data_dir = candidate / "data"
        if (data_dir / ".cli_connection").is_file() or (
            data_dir / ".cli_token"
        ).is_file():
            return candidate

    for candidate in candidates:
        data_dir = candidate / "data"
        if data_dir.is_dir() and (
            candidate == current
            or (candidate / "astrbot").is_dir()
            or (candidate / "pyproject.toml").is_file()
        ):
            return candidate
    return None


def get_data_path() -> str:
    """获取数据目录路径

    优先级：
    1. 环境变量 ASTRBOT_ROOT
    2. 当前工作目录或其最近的 AstrBot 父目录
    3. 客户端源码目录（通过 __file__ 获取）
    """
    if root := os.environ.get("ASTRBOT_ROOT"):
        return str(Path(root).expanduser().resolve() / "data")

    if working_root := _get_working_root():
        return str(working_root / "data")

    source_data = _get_source_root() / "data"
    if source_data.is_dir():
        return str(source_data)

    return str(Path.cwd().resolve() / "data")


def get_temp_path() -> str:
    """获取临时目录路径,兼容容器和非容器环境"""
    if root := os.environ.get("ASTRBOT_ROOT"):
        return str(Path(root).expanduser().resolve() / "data" / "temp")

    data_path = Path(get_data_path())
    if data_path.is_dir():
        return str(data_path / "temp")

    return tempfile.gettempdir()


def load_auth_token() -> str:
    """从密钥文件加载认证token

    Returns:
        token字符串,如果文件不存在则返回空字符串
    """
    token_file = Path(get_data_path()) / ".cli_token"
    try:
        return token_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""


def load_connection_info(data_dir: str) -> dict | None:
    """加载连接信息

    从.cli_connection文件读取Socket连接信息

    Args:
        data_dir: 数据目录路径

    Returns:
        连接信息字典，如果文件不存在则返回None
    """
    connection_file = Path(data_dir) / ".cli_connection"
    try:
        with connection_file.open(encoding="utf-8") as f:
            connection_info = json.load(f)
        if not isinstance(connection_info, dict):
            print(
                f"[ERROR] Connection file must contain a JSON object: {connection_file}",
                file=sys.stderr,
            )
            return None
        return connection_info
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        print(
            f"[ERROR] Invalid JSON in connection file: {connection_file}",
            file=sys.stderr,
        )
        print(f"[ERROR] {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(
            f"[ERROR] Failed to load connection info: {e}",
            file=sys.stderr,
        )
        return None


def connect_to_server(connection_info: dict, timeout: float = 120.0) -> socket.socket:
    """连接到服务器

    根据连接信息类型选择Unix Socket或TCP Socket连接

    Args:
        connection_info: 连接信息字典
        timeout: 超时时间（秒）

    Returns:
        socket连接对象

    Raises:
        ValueError: 无效的连接类型
        ConnectionError: 连接失败
    """
    socket_type = connection_info.get("type")

    client_socket: socket.socket | None = None
    if socket_type == "unix":
        socket_path = connection_info.get("path")
        if not socket_path:
            raise ValueError("Unix socket path is missing in connection info")

        try:
            client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_socket.settimeout(timeout)
            client_socket.connect(socket_path)
            return client_socket
        except FileNotFoundError as error:
            if client_socket is not None:
                client_socket.close()
            raise ConnectionError(
                f"Socket file not found: {socket_path}. Is AstrBot running?"
            ) from error
        except ConnectionRefusedError as error:
            if client_socket is not None:
                client_socket.close()
            raise ConnectionError(
                "Connection refused. Is AstrBot running in socket mode?"
            ) from error
        except Exception as e:
            if client_socket is not None:
                client_socket.close()
            raise ConnectionError(f"Unix socket connection error: {e}") from e

    elif socket_type == "tcp":
        host = connection_info.get("host")
        port = connection_info.get("port")
        if not host or not port:
            raise ValueError("TCP host or port is missing in connection info")

        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(timeout)
            client_socket.connect((host, port))
            return client_socket
        except ConnectionRefusedError as error:
            if client_socket is not None:
                client_socket.close()
            raise ConnectionError(
                f"Connection refused to {host}:{port}. Is AstrBot running?"
            ) from error
        except TimeoutError as error:
            if client_socket is not None:
                client_socket.close()
            raise ConnectionError(f"Connection timeout to {host}:{port}") from error
        except Exception as e:
            if client_socket is not None:
                client_socket.close()
            raise ConnectionError(f"TCP socket connection error: {e}") from e

    else:
        raise ValueError(
            f"Invalid socket type: {socket_type}. Expected 'unix' or 'tcp'"
        )


def _receive_json_response(client_socket: socket.socket) -> dict:
    """从 socket 接收并解析 JSON 响应

    Args:
        client_socket: socket连接对象

    Returns:
        解析后的响应字典
    """
    response_data = b""
    while True:
        chunk = client_socket.recv(4096)
        if not chunk:
            break
        response_data += chunk
        try:
            return json.loads(response_data.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue

    return json.loads(response_data.decode("utf-8", errors="replace"))


def _get_connected_socket(
    socket_path: str | None = None, timeout: float = 120.0
) -> socket.socket:
    """获取已连接的 socket

    Args:
        socket_path: Unix socket路径(向后兼容)
        timeout: 超时时间（秒）

    Returns:
        已连接的 socket 对象

    Raises:
        ValueError, ConnectionError: 连接失败时
    """
    if socket_path is not None:
        return connect_to_server({"type": "unix", "path": socket_path}, timeout)

    data_dir = get_data_path()
    connection_info = load_connection_info(data_dir)
    if connection_info is not None:
        return connect_to_server(connection_info, timeout)

    fallback_info = {"type": "unix", "path": str(Path(get_temp_path()) / "astrbot.sock")}
    return connect_to_server(fallback_info, timeout)


def _send_request(
    request: dict, socket_path: str | None, timeout: float
) -> dict:
    """连接、发送请求并接收响应，统一处理错误。"""
    auth_token = load_auth_token()
    if auth_token:
        request["auth_token"] = auth_token

    try:
        client_socket = _get_connected_socket(socket_path, timeout)
    except (ValueError, ConnectionError) as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Connection error: {e}"}

    try:
        request_data = json.dumps(request, ensure_ascii=False).encode("utf-8")
        client_socket.sendall(request_data)
        return _receive_json_response(client_socket)
    except TimeoutError:
        return {"status": "error", "error": "Request timeout"}
    except Exception as e:
        return {"status": "error", "error": f"Communication error: {e}"}
    finally:
        client_socket.close()


def send_message(
    message: str, socket_path: str | None = None, timeout: float = 120.0
) -> dict:
    """发送消息到AstrBot并获取响应

    Args:
        message: 要发送的消息
        socket_path: Unix socket路径(仅用于向后兼容)
        timeout: 超时时间（秒）

    Returns:
        响应字典
    """
    request = {"message": message, "request_id": str(uuid.uuid4())}
    return _send_request(request, socket_path, timeout)


def get_logs(
    socket_path: str | None = None,
    timeout: float = 30.0,
    lines: int = 100,
    level: str = "",
    pattern: str = "",
    use_regex: bool = False,
) -> dict:
    """获取AstrBot日志

    Args:
        socket_path: Socket路径
        timeout: 超时时间
        lines: 返回的日志行数
        level: 日志级别过滤
        pattern: 模式过滤
        use_regex: 是否使用正则表达式

    Returns:
        响应字典
    """
    return _send_action_request(
        "get_logs",
        extra_fields={
            "lines": lines,
            "level": level,
            "pattern": pattern,
            "regex": use_regex,
        },
        socket_path=socket_path,
        timeout=timeout,
    )


def get_capabilities(
    socket_path: str | None = None,
    timeout: float = 5.0,
) -> dict:
    """Return the running instance's CLI protocol capabilities."""
    return _send_action_request(
        "get_capabilities",
        socket_path=socket_path,
        timeout=timeout,
    )


def ping_server(
    socket_path: str | None = None,
    timeout: float = 5.0,
) -> dict:
    """Ping the CLI control socket without entering the message pipeline."""
    return _send_action_request("ping", socket_path=socket_path, timeout=timeout)


def _send_action_request(
    action: str,
    extra_fields: dict | None = None,
    socket_path: str | None = None,
    timeout: float = 30.0,
) -> dict:
    """发送 action 请求的通用方法"""
    request: dict = {"action": action, "request_id": str(uuid.uuid4())}
    if extra_fields:
        request.update(extra_fields)
    return _send_request(request, socket_path, timeout)


def _send_supported_action(
    action: str,
    *,
    extra_fields: dict | None = None,
    socket_path: str | None = None,
    timeout: float = 30.0,
) -> dict:
    """Verify a server capability before invoking a versioned action."""
    capability_response = get_capabilities(
        socket_path=socket_path,
        timeout=min(timeout, 5.0),
    )
    if capability_response.get("status") != "success":
        return capability_response
    capabilities = capability_response.get("capabilities")
    if not isinstance(capabilities, list) or action not in capabilities:
        return {
            "status": "error",
            "error": (
                f"运行中的 AstrBot 不支持 CLI action '{action}'，"
                "请升级服务端或确认连接到了正确实例。"
            ),
            "error_code": "UNSUPPORTED_ACTION",
        }
    return _send_action_request(
        action,
        extra_fields=extra_fields,
        socket_path=socket_path,
        timeout=timeout,
    )


def list_tools(socket_path: str | None = None, timeout: float = 120.0) -> dict:
    """列出所有注册的函数工具"""
    return _send_action_request("list_tools", socket_path=socket_path, timeout=timeout)


def list_plugins(
    socket_path: str | None = None,
    timeout: float = 30.0,
) -> dict:
    """List plugins loaded by the running AstrBot instance."""
    return _send_supported_action(
        "list_plugins",
        socket_path=socket_path,
        timeout=timeout,
    )


def set_plugin_enabled(
    plugin: str,
    *,
    enabled: bool,
    socket_path: str | None = None,
    timeout: float = 120.0,
) -> dict:
    """Enable or disable one runtime plugin."""
    return _send_supported_action(
        "set_plugin_enabled",
        extra_fields={"plugin": plugin, "enabled": enabled},
        socket_path=socket_path,
        timeout=timeout,
    )


def reload_plugin(
    plugin: str | None = None,
    *,
    reload_all: bool = False,
    socket_path: str | None = None,
    timeout: float = 180.0,
) -> dict:
    """Reload one runtime plugin or explicitly reload all plugins."""
    return _send_supported_action(
        "reload_plugin",
        extra_fields={"plugin": plugin, "reload_all": reload_all},
        socket_path=socket_path,
        timeout=timeout,
    )


def call_tool(
    tool_name: str,
    tool_args: dict | None = None,
    socket_path: str | None = None,
    timeout: float = 60.0,
) -> dict:
    """调用指定的函数工具"""
    return _send_action_request(
        "call_tool",
        extra_fields={"tool_name": tool_name, "tool_args": tool_args or {}},
        socket_path=socket_path,
        timeout=timeout,
    )


def list_sessions(
    page: int = 1,
    page_size: int = 20,
    platform: str | None = None,
    search_query: str | None = None,
    socket_path: str | None = None,
    timeout: float = 30.0,
) -> dict:
    """列出所有会话"""
    fields: dict = {"page": page, "page_size": page_size}
    if platform:
        fields["platform"] = platform
    if search_query:
        fields["search_query"] = search_query
    return _send_action_request(
        "list_sessions",
        extra_fields=fields,
        socket_path=socket_path,
        timeout=timeout,
    )


def list_session_conversations(
    session_id: str,
    page: int = 1,
    page_size: int = 20,
    socket_path: str | None = None,
    timeout: float = 30.0,
) -> dict:
    """列出指定会话的所有对话"""
    return _send_action_request(
        "list_session_conversations",
        extra_fields={
            "session_id": session_id,
            "page": page,
            "page_size": page_size,
        },
        socket_path=socket_path,
        timeout=timeout,
    )


def get_session_history(
    session_id: str,
    conversation_id: str | None = None,
    page: int = 1,
    page_size: int = 10,
    socket_path: str | None = None,
    timeout: float = 30.0,
) -> dict:
    """获取指定会话的聊天记录"""
    fields: dict = {
        "session_id": session_id,
        "page": page,
        "page_size": page_size,
    }
    if conversation_id:
        fields["conversation_id"] = conversation_id
    return _send_action_request(
        "get_session_history",
        extra_fields=fields,
        socket_path=socket_path,
        timeout=timeout,
    )
