# -*- coding: utf-8 -*-
"""Agent Proxy Manager: manages the Agent reverse proxy.

Responsible for proxying frontend requests to the Agent gateway port, solving port management issues in cloud environments.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator

import httpx
import websockets
from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse

from haijunbot.haijunbot_web_gateway.agent_manager import AgentManager


# Configure logging
logger = logging.getLogger(__name__)


# Proxy-related exceptions
class AgentProxyError(Exception):
    """Base class for proxy exceptions."""

    pass


class AgentNotFoundError(AgentProxyError):
    """Agent does not exist."""

    pass


class AgentNotRunningError(AgentProxyError):
    """Agent is not running."""

    pass


class ProxyConnectionError(AgentProxyError):
    """Proxy connection failed."""

    pass


class AgentProxyManager:
    """Agent proxy manager: manages the Agent reverse proxy."""

    def __init__(
        self,
        agent_manager: AgentManager,
        http_timeout: float = 30.0,
        ws_timeout: float = 60.0,
    ) -> None:
        """Initialize AgentProxyManager.

        Args:
            agent_manager: AgentManager instance
            http_timeout: HTTP request timeout (seconds)
            ws_timeout: WebSocket connection timeout (seconds)
        """
        self._agent_manager = agent_manager
        self._http_timeout = http_timeout
        self._ws_timeout = ws_timeout

        # Create an httpx async client (with a connection pool)
        # trust_env=False: the target is always the local agent port (127.0.0.1:<port>),
        # so environment variables like HTTP_PROXY/HTTPS_PROXY must be ignored; otherwise requests
        # would be intercepted by the system proxy (httpx does not recognize the "127.*" wildcard in no_proxy), causing a 502.
        self._http_client = httpx.AsyncClient(
            timeout=http_timeout,
            follow_redirects=True,
            trust_env=False,
        )

        logger.info("[PROXY MANAGER] AgentProxyManager initialized")

    async def get_agent_port(self, agent_id: str) -> int:
        """Get the Agent's listening port.

        Args:
            agent_id: Agent ID

        Returns:
            The Agent port number

        Raises:
            AgentNotFoundError: Agent does not exist
            AgentNotRunningError: Agent is not running
        """
        agent = self._agent_manager.get_agent(agent_id)
        if agent is None:
            raise AgentNotFoundError(f"Agent not found: {agent_id}")

        if agent.status != "running":
            raise AgentNotRunningError(
                f"Agent {agent_id} is not running (status: {agent.status})"
            )

        port = agent.port
        if port is None:
            raise AgentNotRunningError(f"Agent {agent_id} has no port assigned")

        logger.debug(f"[PROXY MANAGER] Got port {port} for agent {agent_id}")
        return port

    async def proxy_http_request(
        self,
        request: Request,
        agent_id: str,
        path: str,
    ) -> Response:
        """Proxy an HTTP request to the Agent.

        Args:
            request: FastAPI Request object
            agent_id: Agent ID
            path: Target path

        Returns:
            FastAPI Response object (streaming or regular)

        Raises:
            AgentProxyError: proxy failure
        """
        # Get the Agent port
        try:
            port = await self.get_agent_port(agent_id)
        except AgentProxyError as e:
            logger.error(f"[PROXY MANAGER] Failed to get agent port: {e}")
            raise

        # Build the Agent URL
        agent_url = f"http://127.0.0.1:{port}/{path}"
        logger.info(f"[PROXY MANAGER] Proxying HTTP {request.method} {agent_url}")

        # Prepare request headers (filter out headers like Host that need rewriting)
        headers = dict(request.headers)
        headers.pop("host", None)
        headers["X-Forwarded-For"] = (
            request.client.host if request.client else "unknown"
        )
        headers["X-Forwarded-Proto"] = request.url.scheme

        # Determine whether a streaming response is needed
        accept_header = headers.get("accept", "")
        want_stream = "text/event-stream" in accept_header
        logger.info(
            f"[PROXY MANAGER] Stream detection: Accept={accept_header}, want_stream={want_stream}, agent_id={agent_id}, path={path}"
        )

        # Read the request body
        body = await request.body()

        try:
            if want_stream:
                # Streaming mode: supports SSE
                async def stream_response() -> AsyncIterator[bytes]:
                    async with self._http_client.stream(
                        method=request.method,
                        url=agent_url,
                        headers=headers,
                        content=body,
                        params=request.query_params,
                    ) as response:
                        # Build response headers (headers allowed for streaming)
                        excluded_headers = {
                            "content-encoding",
                            "content-length",
                        }
                        response_headers = {
                            k: v
                            for k, v in response.headers.items()
                            if k.lower() not in excluded_headers
                        }

                        logger.debug(
                            f"[PROXY MANAGER] Agent streaming response: {response.status_code} "
                            f"(headers: {len(response.headers)})",
                        )

                        async for chunk in response.aiter_bytes():
                            if chunk:
                                yield chunk

                        logger.debug(
                            f"[PROXY MANAGER] Streaming completed, "
                            f"content_type={response_headers.get('content-type')}"
                        )

                return StreamingResponse(
                    stream_response(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",  # Disable nginx buffering
                    },
                )
            else:
                # Non-streaming mode: read the full response at once
                response = await self._http_client.request(
                    method=request.method,
                    url=agent_url,
                    headers=headers,
                    content=body,
                    params=request.query_params,
                )

                logger.debug(
                    f"[PROXY MANAGER] Agent response: {response.status_code} "
                    f"(headers: {len(response.headers)} bytes, body: {len(response.content)} bytes)"
                )

                # Build the response
                excluded_headers = {
                    "content-encoding",
                    "content-length",
                    "transfer-encoding",
                    "connection",
                }
                response_headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in excluded_headers
                }

                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=response_headers,
                    media_type=response.headers.get("content-type"),
                )

        except httpx.TimeoutException:
            logger.error(f"[PROXY MANAGER] HTTP proxy timeout: {agent_url}")
            raise ProxyConnectionError(f"HTTP proxy timeout: {agent_url}")
        except httpx.ConnectError as e:
            logger.error(f"[PROXY MANAGER] HTTP proxy connection error: {e}")
            raise ProxyConnectionError(f"Cannot connect to agent: {e}")
        except Exception as e:
            logger.error(f"[PROXY MANAGER] HTTP proxy error: {e}")
            raise ProxyConnectionError(f"HTTP proxy failed: {e}")

    async def proxy_websocket(
        self,
        client_ws: WebSocket,
        agent_id: str,
    ) -> None:
        """Proxy a WebSocket connection to the Agent.

        Args:
            client_ws: The client WebSocket connection
            agent_id: Agent ID

        Raises:
            AgentProxyError: proxy failure
        """
        # Get the Agent port
        try:
            port = await self.get_agent_port(agent_id)
        except AgentProxyError as e:
            logger.error(f"[PROXY MANAGER] Failed to get agent port: {e}")
            await client_ws.close(code=4000, reason=str(e))
            return  # Connection already closed; do not raise

        # Build the Agent WebSocket URL
        agent_url = f"ws://127.0.0.1:{port}/ws"
        logger.info(f"[PROXY MANAGER] Proxying WebSocket to {agent_url}")

        # Prepare subprotocols (required by the Agent Gateway)
        auth_token = os.environ.get("HAIJUNBOT_AUTH_TOKEN")
        subprotocols = ["haijunbot-ws"]
        if auth_token:
            subprotocols.append(f"haijunbot-token.{auth_token}")

        # Connect to the Agent
        try:
            agent_ws = await websockets.connect(
                agent_url,
                close_timeout=self._ws_timeout,
                proxy=None,  # Disable automatic proxy; connect to the local Agent directly
                subprotocols=subprotocols,  # ty: ignore[invalid-argument-type]
            )
        except Exception as e:
            logger.error(f"[PROXY MANAGER] Failed to connect to agent WebSocket: {e}")
            await client_ws.close(code=4001, reason="Cannot connect to agent")
            return  # Connection already closed; do not raise

        logger.info(f"[PROXY MANAGER] WebSocket connected to agent {agent_id}")

        try:
            # Send an authentication message to the Agent Gateway
            # The Agent Gateway requires the first message to be an authentication message
            auth_token = os.environ.get("HAIJUNBOT_AUTH_TOKEN")
            if auth_token:
                auth_message = json.dumps(
                    {"type": "auth", "payload": {"token": auth_token}}
                )
                await agent_ws.send(auth_message)
                logger.info(f"[PROXY MANAGER] Sent auth message to agent {agent_id}")

            # The caching mechanism has been removed; it now relies entirely on WebGateway._message_cache and sync_request

            # Create bidirectional forwarding tasks
            client_to_agent_task = asyncio.create_task(
                self._forward_messages(client_ws, agent_ws, "client->agent", agent_id)
            )
            agent_to_client_task = asyncio.create_task(
                self._forward_messages(agent_ws, client_ws, "agent->client", agent_id)
            )

            # Wait for client->agent to finish first; after the client disconnects, instead of relying on a send failure to the client to trigger caching,
            # explicitly switch to a mode that keeps consuming and caching agent messages.
            await client_to_agent_task

            if not agent_to_client_task.done():
                agent_to_client_task.cancel()
                try:
                    await agent_to_client_task
                except asyncio.CancelledError:
                    pass
                # The caching mechanism has been removed; Agent messages are stored in WebGateway._message_cache
                # and automatically retrieved by the frontend via sync_request after reconnecting

            # Check whether the forwarding tasks raised exceptions
            for task in (client_to_agent_task, agent_to_client_task):
                if task.cancelled():
                    continue
                if task.exception():
                    logger.error(
                        f"[PROXY MANAGER] WebSocket forward task error: {task.exception()}"
                    )
                    # Closing client_ws is managed centrally by agent_websocket_proxy in app.py
                    # Do not close it here to avoid a double-close causing RuntimeError

        finally:
            # Clean up connections
            try:
                if "agent_ws" in locals():
                    await agent_ws.close()
            except Exception as e:
                logger.warning(f"[PROXY MANAGER] Failed to close agent WebSocket: {e}")

            logger.info(f"[PROXY MANAGER] WebSocket proxy closed for agent {agent_id}")

    async def _forward_messages(
        self,
        source_ws: Any,
        target_ws: Any,
        direction: str,
        agent_id: str,
    ) -> None:
        """Forward WebSocket messages.

        Args:
            source_ws: Source WebSocket (websockets WebSocket or FastAPI WebSocket)
            target_ws: Target WebSocket
            direction: Forwarding direction (used for logging)
        """
        try:
            if isinstance(source_ws, WebSocket):
                # FastAPI WebSocket
                while True:
                    data = await source_ws.receive_text()
                    # Forward the ping message to the agent; the agent replies with pong, implementing end-to-end heartbeat detection
                    logger.debug(
                        f"[PROXY MANAGER] Forwarding {direction}: {len(data)} bytes"
                    )
                    if isinstance(target_ws, WebSocket):
                        await target_ws.send_text(data)
                    else:
                        await target_ws.send(data)
            else:
                # websockets WebSocket
                async for message in source_ws:
                    data = message if isinstance(message, str) else message.decode()
                    logger.debug(
                        f"[PROXY MANAGER] Forwarding {direction}: {len(data)} bytes"
                    )
                    try:
                        if isinstance(target_ws, WebSocket):
                            await target_ws.send_text(data)
                        else:
                            await target_ws.send(data)
                    except Exception as e:
                        if direction == "agent->client":
                            logger.info(
                                "[PROXY MANAGER] Client unavailable while forwarding agent message for %s: %s. Message will be available via sync_request.",
                                agent_id,
                                e,
                            )
                            return
                        raise

        except WebSocketDisconnect:
            logger.debug(f"[PROXY MANAGER] {direction}: WebSocket disconnected")
        except Exception as e:
            logger.debug(f"[PROXY MANAGER] {direction}: Forward error: {e}")
            raise

    # Cache-related methods have been removed; it now relies entirely on the WebGateway._message_cache and sync_request mechanisms

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self._http_client.aclose()
        logger.info("[PROXY MANAGER] Cleanup completed")
