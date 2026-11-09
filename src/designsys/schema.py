"""最小 JSON Schema 校验器（标准库实现，路线 C）。只支持下面列出的关键字；遇到不支持的关键字或未知类型一律抛 SchemaError，绝不静默放过。"""
from __future__ import annotations

import re

ANNOTATIONS = frozenset({"$schema", "$id", "title", "description", "examples", "default", "$comment", "$defs"})
SUPPORTED = frozenset({"type", "required", "properties", "additionalProperties", "items", "minItems", "enum", "const", "pattern", "minLength", "$ref"})
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


class SchemaError(ValueError):
    """Schema 本身不合法或超出本校验器的支持范围；不得当作通过。"""


def _err(path: str, message: str) -> dict:
    return {"path": path, "message": message}


def _is_type(value, name: str) -> bool:
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name not in TYPES:
        raise SchemaError(f"不支持的类型 {name}")
    if name in ("string", "object", "array") and isinstance(value, bool):
        return False
    return isinstance(value, TYPES[name])


def _resolve(ref: str, root: dict) -> dict:
    if not ref.startswith("#/"):
        raise SchemaError(f"无法解析的引用 {ref}：只支持文档内的 #/ 引用")
    node = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise SchemaError(f"无法解析的引用 {ref}")
        node = node[part]
    return node


def _check_keywords(schema: dict) -> None:
    for key in schema:
        if key not in SUPPORTED and key not in ANNOTATIONS:
            raise SchemaError(f"不支持的 JSON Schema 关键字 {key}：本校验器不会静默忽略它")


def _check_type_names(schema: dict, where: str) -> None:
    if "type" not in schema:
        return
    names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
    for name in names:
        if name not in TYPES and name not in ("integer", "number"):
            raise SchemaError(f"{where} 使用了不支持的类型 {name}")


def _check_schema(schema, where: str) -> None:
    """递归检查整份 Schema：不论数据是否会走到，凡不支持的关键字或类型都在这里拒绝。"""
    if not isinstance(schema, dict):
        raise SchemaError(f"{where} 处的 Schema 必须是对象")
    _check_keywords(schema)
    _check_type_names(schema, where)
    for key, sub in schema.get("properties", dict()).items():
        _check_schema(sub, f"{where}.properties.{key}")
    if "items" in schema:
        _check_schema(schema["items"], f"{where}.items")
    for key, sub in schema.get("$defs", dict()).items():
        _check_schema(sub, f"{where}.$defs.{key}")


def _walk(value, schema: dict, root: dict, path: str, out: list) -> None:
    if not isinstance(schema, dict):
        raise SchemaError(f"{path} 处的 Schema 必须是对象")
    _check_keywords(schema)
    if "$ref" in schema:
        _walk(value, _resolve(schema["$ref"], root), root, path, out)
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, n) for n in names):
            out.append(_err(path, f"类型应为 {schema['type']}，实际是 {type(value).__name__}"))
            return
    if "enum" in schema and value not in schema["enum"]:
        out.append(_err(path, f"取值不在枚举 {schema['enum']} 中"))
    if "const" in schema and value != schema["const"]:
        out.append(_err(path, f"取值应为 {schema['const']!r}"))
    if isinstance(value, str):
        _walk_string(value, schema, path, out)
    if isinstance(value, list):
        _walk_array(value, schema, root, path, out)
    if isinstance(value, dict):
        _walk_object(value, schema, root, path, out)


def _walk_string(value: str, schema: dict, path: str, out: list) -> None:
    if len(value) < schema.get("minLength", 0):
        out.append(_err(path, f"长度不足 {schema['minLength']}"))
    if "pattern" in schema and not re.search(schema["pattern"], value):
        out.append(_err(path, f"不匹配模式 {schema['pattern']}"))


def _walk_array(value: list, schema: dict, root: dict, path: str, out: list) -> None:
    if len(value) < schema.get("minItems", 0):
        out.append(_err(path, f"元素数不足 {schema['minItems']}"))
    if "items" in schema:
        for i, item in enumerate(value):
            _walk(item, schema["items"], root, f"{path}[{i}]", out)


def _walk_object(value: dict, schema: dict, root: dict, path: str, out: list) -> None:
    for key in schema.get("required", []):
        if key not in value:
            out.append(_err(path, f"缺少必填字段 {key}"))
    props = schema.get("properties", dict())
    for key, sub in props.items():
        if key in value:
            _walk(value[key], sub, root, f"{path}.{key}", out)
    if schema.get("additionalProperties") is False:
        for key in value:
            if key not in props:
                out.append(_err(path, f"不允许的字段 {key}"))


def validate(value, schema: dict) -> list:
    """返回错误列表（空表示通过）。Schema 超出支持范围时抛 SchemaError。"""
    _check_schema(schema, "$")
    out = []
    _walk(value, schema, schema, "$", out)
    return out
