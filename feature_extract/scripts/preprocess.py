"""预处理流水线兼容入口。

实现位于 :mod:`preprocess_core`，保留原有 ``python scripts/preprocess.py``
命令路径，避免已有工作流失效。
"""
from preprocess_core import *  # noqa: F401,F403


if __name__ == "__main__":
    main()
