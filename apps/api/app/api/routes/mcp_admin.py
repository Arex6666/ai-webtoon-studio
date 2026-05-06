"""GET/POST/DELETE /v1/mcp/connections/* — outbound MCP server admin."""
import uuid
from typing import Optional, Literal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.mcp_server_connection import McpServerConnection
from app.services.agent.mcp_client_pool import MCP_CLIENT_POOL

router = APIRouter(prefix="/v1/mcp/connections", tags=["MCP"])


class McpConnectionOut(BaseModel):
    id: str
    name: str
    transport: str
    command: Optional[str]
    args_json: Optional[list]
    url: Optional[str]
    status: str
    last_connected_at: Optional[datetime]
    last_error: Optional[str]
    capabilities_json: Optional[dict]
    scope: str
    project_id: Optional[str]

    class Config:
        from_attributes = True


@router.get("", response_model=list[McpConnectionOut])
def list_connections(
    scope: Optional[str] = None, project_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(McpServerConnection)
    if scope:
        q = q.filter(McpServerConnection.scope == scope)
    if project_id:
        q = q.filter(McpServerConnection.project_id == project_id)
    return q.order_by(McpServerConnection.created_at.desc()).all()


class AddConnectionRequest(BaseModel):
    name: str
    transport: Literal["stdio", "sse", "streamable_http"]
    command: Optional[str] = None
    args: Optional[list[str]] = None
    url: Optional[str] = None
    env: Optional[dict] = None
    scope: Literal["global", "project"] = "project"
    project_id: Optional[str] = None


@router.post("", response_model=McpConnectionOut)
async def add_connection(req: AddConnectionRequest, db: Session = Depends(get_db)):
    if req.transport == "stdio" and not req.command:
        raise HTTPException(400, "stdio transport requires `command`")
    if req.transport != "stdio" and not req.url:
        raise HTTPException(400, f"{req.transport} transport requires `url`")
    if req.transport == "stdio" and req.command in ("bash", "sh", "zsh", "powershell.exe"):
        raise HTTPException(400, f"command '{req.command}' rejected — use a specific executable path")

    row = McpServerConnection(
        id=str(uuid.uuid4()),
        name=req.name, transport=req.transport,
        command=req.command, args_json=req.args, url=req.url, env_json=req.env,
        scope=req.scope, project_id=req.project_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    try:
        await MCP_CLIENT_POOL._spawn_or_connect(db, row)
    except Exception as e:
        row.status = "failed"
        row.last_error = str(e)
        db.commit()

    return row


@router.post("/{conn_id}/reconnect", response_model=McpConnectionOut)
async def reconnect(conn_id: str, db: Session = Depends(get_db)):
    row = db.query(McpServerConnection).filter_by(id=conn_id).first()
    if not row:
        raise HTTPException(404)
    try:
        await MCP_CLIENT_POOL.reconnect(db, conn_id)
    except Exception as e:
        row.status = "failed"
        row.last_error = str(e)
        db.commit()
    db.refresh(row)
    return row


@router.delete("/{conn_id}")
async def remove_connection(conn_id: str, db: Session = Depends(get_db)):
    row = db.query(McpServerConnection).filter_by(id=conn_id).first()
    if not row:
        raise HTTPException(404)
    await MCP_CLIENT_POOL._disconnect(conn_id)
    db.delete(row)
    db.commit()
    return {"ok": True}
