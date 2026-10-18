# -*- coding: utf-8 -*-
"""打包与运行入口：把项目根目录加入 sys.path 后启动 app.main。"""
from __future__ import annotations

import os
import sys


def _main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    from app.main import main

    return main()


if __name__ == "__main__":
    sys.exit(_main())
