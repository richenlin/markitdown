"""
MarkItDown 统一服务
同时提供：
  - REST API  (/api/convert, /api/health)     ← Electron 客户端调用
  - MCP SSE   (/sse, /messages/)              ← 旧版 MCP 客户端（如 Claude Desktop）
  - MCP HTTP  (/mcp)                          ← 新版 MCP 客户端（Cursor 等）
"""
import base64, contextlib, io, logging, mimetypes, os
from collections.abc import AsyncIterator

logger = logging.getLogger("markitdown-api")

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from markitdown import MarkItDown, StreamInfo
from markitdown_ocr import LLMVisionOCRService
from openai import OpenAI
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send
import uvicorn

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://ollama:11434/v1")
LLM_MODEL    = os.getenv("LLM_MODEL",    "qwen2-vl:7b")
LLM_API_KEY  = os.getenv("LLM_API_KEY",  "ollama")
LLM_PROMPT   = os.getenv("LLM_PROMPT",
    "请精确提取图片中所有文字，严格保持原始顺序和段落结构，只返回纯文字，不添加任何说明或标注。"
)

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt",
    ".xlsx", ".xls", ".csv",
    ".jpg", ".jpeg", ".png",
    ".txt", ".md", ".html", ".epub",
}

def build_markitdown() -> MarkItDown:
    client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    ocr_service = LLMVisionOCRService(
        client=client, model=LLM_MODEL, default_prompt=LLM_PROMPT
    )
    return MarkItDown(enable_plugins=True, ocr_service=ocr_service)


def do_convert(filename: str, content: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    stream_info = StreamInfo(extension=ext, mimetype=mime, filename=filename)
    result = build_markitdown().convert_stream(io.BytesIO(content), stream_info=stream_info)
    return result.markdown


# ══════════════════════════════════════════════════════════════════
# Part A: REST API（FastAPI）
# ══════════════════════════════════════════════════════════════════
rest_app = FastAPI(title="MarkItDown REST API", version="1.0.0")
rest_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:*", "app://*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@rest_app.get("/health")
def health():
    return {"status": "ok", "llm_base_url": LLM_BASE_URL, "llm_model": LLM_MODEL}

@rest_app.post("/convert")
async def convert_file(file: UploadFile = File(...)):
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件类型: {ext}")
    content = await file.read()
    try:
        markdown = do_convert(filename, content)
        return {"filename": filename, "markdown": markdown}
    except Exception as e:
        logger.exception("File conversion failed for %s", filename)
        raise HTTPException(500, "转换失败，请检查文件格式或服务状态")


# ══════════════════════════════════════════════════════════════════
# Part B: MCP 服务器（FastMCP）
# ══════════════════════════════════════════════════════════════════
mcp = FastMCP("markitdown")

@mcp.tool()
async def convert_to_markdown(uri: str) -> str:
    """
    将 http:、https:、file: 或 data: URI 指向的资源转换为 Markdown。
    适合 LLM 直接传入网页链接或 data URI（base64 编码的文件）。
    """
    return build_markitdown().convert_uri(uri).markdown

@mcp.tool()
async def convert_file_content(filename: str, content_base64: str) -> str:
    """
    将 base64 编码的文件内容转换为 Markdown。
    参数：
      filename      - 原始文件名（含扩展名，用于判断格式），如 "report.pdf"
      content_base64 - 文件的 base64 编码字符串
    适合 LLM 调用时直接传入二进制文件内容。
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return f"[错误] 不支持的文件类型: {ext}"
    try:
        content = base64.b64decode(content_base64)
        return do_convert(filename, content)
    except Exception as e:
        logger.exception("MCP conversion failed for %s", filename)
        return "[错误] 转换失败，请检查文件格式或服务状态"


# ══════════════════════════════════════════════════════════════════
# Part C: Starlette 统一挂载
# ══════════════════════════════════════════════════════════════════
def build_app() -> Starlette:
    mcp_server: Server = mcp._mcp_server
    sse = SseServerTransport("/messages/")
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server, event_store=None, json_response=True, stateless=True
    )

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream, write_stream,
                mcp_server.create_initialization_options()
            )

    async def handle_streamable_http(scope: Scope, receive: Receive, send: Send):
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    return Starlette(
        routes=[
            Mount("/api",       app=rest_app),
            Route("/sse",       endpoint=handle_sse),
            Mount("/mcp",       app=handle_streamable_http),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        lifespan=lifespan,
    )


if __name__ == "__main__":
    uvicorn.run(build_app(), host="0.0.0.0", port=8778)
