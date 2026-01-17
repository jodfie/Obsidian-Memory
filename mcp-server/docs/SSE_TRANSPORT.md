# SSE Transport Implementation

## Overview

The SSE (Server-Sent Events) transport enables the MCP server to be accessed via HTTP, allowing remote access and integration with Claude.ai and other web-based clients.

## Current Status

The SSE transport infrastructure has been implemented with:
- HTTP server using Bun.serve
- SSE endpoint for receiving messages from the server
- POST endpoint for sending messages to the server
- CORS support for web clients
- Health check endpoint

## Architecture

### Endpoints

- `GET /sse` - SSE stream for receiving server messages
- `POST /message` - Send JSON-RPC requests to the server
- `GET /health` - Health check endpoint
- `OPTIONS /*` - CORS preflight support

### Message Flow

1. Client connects to `/sse` endpoint via GET request
2. Server establishes SSE connection and sends initialization message
3. Client sends JSON-RPC requests via POST to `/message`
4. Server processes requests and sends responses via SSE stream

## Usage

### Starting the Server with SSE Transport

```bash
MCP_TRANSPORT=sse MCP_SSE_PORT=3000 bun run src/index.ts
```

### Environment Variables

- `MCP_TRANSPORT` - Set to `sse` to enable SSE transport (default: `stdio`)
- `MCP_SSE_PORT` - Port for SSE server (default: `3000`)
- `MCP_SSE_PATH` - Path for SSE endpoint (default: `/sse`)

## Limitations

The current implementation provides the HTTP/SSE infrastructure but requires full integration with the MCP SDK's Server class for complete protocol support. The MCP SDK's Server is designed to work with Transport implementations that handle the low-level JSON-RPC protocol.

For full functionality, a custom Transport class implementing the MCP Transport interface would be needed to properly route messages through the Server's request handlers.

## Future Improvements

1. Implement custom Transport class for full MCP protocol support
2. Add connection management and routing to specific clients
3. Implement proper JSON-RPC request/response handling
4. Add authentication/authorization
5. Add WebSocket support as an alternative transport

## Testing

To test the SSE transport:

1. Start the server:
   ```bash
   MCP_TRANSPORT=sse bun run src/index.ts
   ```

2. Connect to SSE endpoint:
   ```bash
   curl -N http://localhost:3000/sse
   ```

3. Send a message:
   ```bash
   curl -X POST http://localhost:3000/message \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
   ```

4. Check health:
   ```bash
   curl http://localhost:3000/health
   ```
