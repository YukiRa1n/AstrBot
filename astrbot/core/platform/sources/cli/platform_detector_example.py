"""
Integration Examples for PlatformDetector Module

This file demonstrates how to use the PlatformDetector module
in various scenarios within the CLI platform adapter.
"""

import logging

from platform_detector import detect_platform

# Configure logging to see the detailed logs
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")


def example_1_basic_usage():
    """Example 1: Basic platform detection"""
    print("\n=== Example 1: Basic Platform Detection ===")

    # Detect platform information
    info = detect_platform()

    # Access platform information
    print(f"Operating System: {info.os_type}")
    print(f"Python Version: {info.python_version}")
    print(f"Unix Socket Support: {info.supports_unix_socket}")


def example_2_socket_selection():
    """Example 2: Use platform info to select socket type"""
    print("\n=== Example 2: Socket Type Selection ===")

    info = detect_platform()

    if info.supports_unix_socket:
        socket_type = "unix"
        print(f"Platform supports Unix Socket, using: {socket_type}")
    else:
        socket_type = "tcp"
        print(f"Platform does not support Unix Socket, using: {socket_type}")

    return socket_type


def example_3_conditional_logic():
    """Example 3: Platform-specific conditional logic"""
    print("\n=== Example 3: Platform-Specific Logic ===")

    info = detect_platform()

    if info.os_type == "windows":
        print("Running on Windows")
        if info.supports_unix_socket:
            print("  - Unix Socket available (Windows 10+ with Python 3.9+)")
        else:
            print("  - Unix Socket not available, will use TCP Socket")
    elif info.os_type == "linux":
        print("Running on Linux")
        print("  - Unix Socket fully supported")
    elif info.os_type == "darwin":
        print("Running on macOS")
        print("  - Unix Socket fully supported")


def example_4_integration_with_factory():
    """Example 4: Integration with SocketFactory pattern"""
    print("\n=== Example 4: SocketFactory Integration ===")

    # Step 1: Detect platform
    platform_info = detect_platform()

    # Step 2: Configuration (from user config)
    config = {
        "socket_type": "auto",  # or "unix" or "tcp"
        "socket_path": "/tmp/astrbot.sock",
        "tcp_host": "127.0.0.1",
        "tcp_port": 0,
    }

    # Step 3: Decide socket type based on platform and config
    if config["socket_type"] == "auto":
        if platform_info.supports_unix_socket:
            selected_type = "unix"
        else:
            selected_type = "tcp"
    else:
        selected_type = config["socket_type"]

    print(f"Platform: {platform_info.os_type}")
    print(f"Config socket_type: {config['socket_type']}")
    print(f"Selected socket type: {selected_type}")

    # Step 4: Create appropriate socket server (pseudo-code)
    if selected_type == "unix":
        print(f"  -> Creating UnixSocketServer at {config['socket_path']}")
    else:
        print(
            f"  -> Creating TCPSocketServer at {config['tcp_host']}:{config['tcp_port']}"
        )


def example_5_error_handling():
    """Example 5: Error handling and logging"""
    print("\n=== Example 5: Error Handling ===")

    try:
        info = detect_platform()
        print(f"Platform detection successful: {info}")
    except Exception as e:
        print(f"Platform detection failed: {e}")
        # Fallback to safe defaults
        print("Falling back to TCP Socket for maximum compatibility")


def example_6_pipeline_usage():
    """Example 6: Unix pipeline pattern"""
    print("\n=== Example 6: Pipeline Pattern ===")

    # Pipeline: Detect -> Validate -> Select -> Configure

    # Step 1: Detect
    platform_info = detect_platform()
    print(f"Step 1 - Detect: {platform_info}")

    # Step 2: Validate (check if platform is supported)
    supported_platforms = ["windows", "linux", "darwin"]
    is_supported = platform_info.os_type in supported_platforms
    print(f"Step 2 - Validate: Platform supported = {is_supported}")

    # Step 3: Select socket type
    socket_type = "unix" if platform_info.supports_unix_socket else "tcp"
    print(f"Step 3 - Select: Socket type = {socket_type}")

    # Step 4: Configure (return configuration dict)
    config = {
        "platform": platform_info.os_type,
        "socket_type": socket_type,
        "requires_token": True if socket_type == "tcp" else False,
    }
    print(f"Step 4 - Configure: {config}")

    return config


if __name__ == "__main__":
    print("=" * 60)
    print("PlatformDetector Integration Examples")
    print("=" * 60)

    # Run all examples
    example_1_basic_usage()
    example_2_socket_selection()
    example_3_conditional_logic()
    example_4_integration_with_factory()
    example_5_error_handling()
    example_6_pipeline_usage()

    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
