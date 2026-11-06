"""看板按终端列宽对齐中文。"""
import unicodedata


def width(text):
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in str(text))
