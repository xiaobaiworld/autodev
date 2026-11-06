"""按显示宽度计算字符串宽度（中文占两格），看板和日志窗格共用。"""
import unicodedata


def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)
