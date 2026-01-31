#!/usr/bin/env node

/**
 * List all tools available on an MCP server
 */

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { SSEClientTransport } from '@modelcontextprotocol/sdk/client/sse.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';

const config = {
    serverUrl: process.env.MCP_SERVER_URL,
    accessToken: process.env.MCP_ACCESS_TOKEN,
    cfClientId: process.env.CF_ACCESS_CLIENT_ID,
    cfClientSecret: process.env.CF_ACCESS_CLIENT_SECRET,
};

async function main() {
    const url = new URL(config.serverUrl);
    const headers = {};
    
    if (config.accessToken) {
        headers['Authorization'] = `Bearer ${config.accessToken}`;
    }
    if (config.cfClientId && config.cfClientSecret) {
        headers['CF-Access-Client-Id'] = config.cfClientId;
        headers['CF-Access-Client-Secret'] = config.cfClientSecret;
    }

    let transport;
    if (url.pathname.endsWith('/sse') || url.pathname.includes('/sse')) {
        transport = new SSEClientTransport(url, { headers });
    } else {
        transport = new StreamableHTTPClientTransport(url, { headers });
    }

    const client = new Client({
        name: 'mcp-list-tools',
        version: '1.0.0'
    });

    try {
        await client.connect(transport);
        
        const result = await client.listTools();
        
        console.log('Available Tools:\n');
        
        for (const tool of result.tools) {
            console.log(`📦 ${tool.name}`);
            if (tool.description) {
                console.log(`   ${tool.description}`);
            }
            if (tool.inputSchema?.properties) {
                console.log('   Parameters:');
                for (const [name, schema] of Object.entries(tool.inputSchema.properties)) {
                    const required = tool.inputSchema.required?.includes(name) ? '*' : '';
                    console.log(`     - ${name}${required}: ${schema.type || 'any'}`);
                }
            }
            console.log('');
        }
        
        console.log(`Total: ${result.tools.length} tools`);
        
        await client.close();
    } catch (error) {
        console.error(`Error: ${error.message}`);
        process.exit(1);
    }
}

main();
