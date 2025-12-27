# ADR 0004: Thread-Based XML-RPC Server

## Status

Accepted

## Context

The Homematic backend pushes events to aiohomematic via XML-RPC callbacks. The current implementation uses Python's `SimpleXMLRPCServer` in a dedicated thread, dispatching events to the main asyncio event loop.

A proposal was made to migrate to an async aiohttp-based implementation for consistency with the rest of the codebase.

## Decision

**Retain the thread-based XML-RPC callback server.** Do NOT migrate to an async aiohttp-based implementation.

### Current Implementation

```python
# central/rpc_server.py
class XmlRpcServer:
    """Thread-based XML-RPC server for backend callbacks."""

    def __init__(self, ...):
        self._server = SimpleXMLRPCServer(...)
        self._thread = threading.Thread(target=self._serve_forever)

    def _dispatch_event(self, ...):
        # Dispatch to asyncio event loop
        asyncio.run_coroutine_threadsafe(
            self._handle_event(...),
            self._loop
        )
```

### Proposed (Rejected) Implementation

```python
# Would require custom XML-RPC parsing with aiohttp
class AsyncXmlRpcServer:
    async def _handle_request(self, request: web.Request) -> web.Response:
        body = await request.read()
        params, method = xmlrpc.client.loads(body)  # Manual parsing
        result = await self._dispatch(method, params)
        response_xml = xmlrpc.client.dumps((result,), methodresponse=True)
        return web.Response(body=response_xml, content_type="text/xml")
```

## Consequences

### Advantages of Keeping Thread-Based Server

- **Proven stability**: The threading model has been stable for years
- **Low risk**: No changes to critical event delivery path
- **Standard library**: Uses well-tested `SimpleXMLRPCServer`
- **Simple dispatch**: `run_coroutine_threadsafe` is reliable for thread-to-asyncio bridging

### Disadvantages Accepted

- **Mixed concurrency model**: Threading + asyncio in the same codebase
- **Thread overhead**: One dedicated thread for XML-RPC server

### Why Async Migration Was Rejected

1. **Critical path risk**: XML-RPC server is the sole event delivery mechanism. Any regression breaks core functionality.

2. **No standard library support**: Python provides no async XML-RPC server. Implementation requires:

   - aiohttp for HTTP handling
   - Manual XML-RPC parsing via `xmlrpc.client.loads()`
   - Custom response serialization
   - Custom error handling

3. **Marginal performance benefit**: Estimated 10-20ms latency improvement per event. With typical event rates (few per second), this is imperceptible.

4. **Unfavorable effort-to-benefit ratio**: 5-7 days development + extensive testing for minimal improvement.

## Alternatives Considered

### 1. aiohttp with Custom XML-RPC Parsing

**Rejected**: High complexity, no standard library support, significant testing required.

### 2. Third-Party Async XML-RPC Library

**Rejected**: No mature, well-maintained async XML-RPC server library exists. Would add risky external dependency.

### 3. Migrate to JSON-RPC Only

**Rejected**: Homematic backends require XML-RPC for event callbacks. Not all operations support JSON-RPC.

## References

- `aiohomematic/central/rpc_server.py` - Current implementation
- `docs/architecture.md` - Architecture overview

---

_Created: 2025-12-10_
_Author: Architecture Review_
