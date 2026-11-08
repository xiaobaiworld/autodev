# 定位: responder.py 飞书消息发送器（支持 Interactive Card、文本与 Markdown 文件上传）。
from __future__ import annotations

import io
import json
import logging

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateFileRequest,
    CreateFileRequestBody,
    CreateMessageRequest,
    CreateMessageRequestBody,
)

log = logging.getLogger("autodev.req")


class FeishuResponder:
    def __init__(self, app_id: str, app_secret: str) -> None:
        self._client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    def send_text(self, chat_id: str, text: str) -> bool:
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}, ensure_ascii=False))
                .build()
            )
            .build()
        )
        resp = self._client.im.v1.message.create(request)
        if not resp.success():
            log.error("发送文本失败: code=%s msg=%s", resp.code, resp.msg)
            return False
        return True

    def send_card(self, chat_id: str, card: dict) -> bool:
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("interactive")
                .content(json.dumps(card, ensure_ascii=False))
                .build()
            )
            .build()
        )
        resp = self._client.im.v1.message.create(request)
        if not resp.success():
            log.error("发送卡片失败: code=%s msg=%s", resp.code, resp.msg)
            return False
        return True

    def upload_text_file(self, chat_id: str, text: str, filename: str = "requirements.md") -> bool:
        stream = io.BytesIO(text.encode("utf-8"))
        up = (
            CreateFileRequest.builder()
            .request_body(
                CreateFileRequestBody.builder()
                .file_type("stream")
                .file_name(filename)
                .file(stream)
                .build()
            )
            .build()
        )
        up_resp = self._client.im.v1.file.create(up)
        if not up_resp.success():
            log.error("上传文件失败: code=%s msg=%s", up_resp.code, up_resp.msg)
            return False

        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("file")
                .content(json.dumps({"file_key": up_resp.data.file_key}))
                .build()
            )
            .build()
        )
        resp = self._client.im.v1.message.create(request)
        return resp.success()
