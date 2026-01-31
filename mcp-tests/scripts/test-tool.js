#!/usr/bin/env node

/**
 * Test a specific tool on an MCP server
 * Usage: node test-tool.js <tool-name> [--arg key=value ...]
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

function parseArgs(args) {
    const toolName = args[0];
    const toolArgs = {};
    
    for (let i = 1; i < args.length; i++) {
        const arg = args[i];
        
        if (arg === '--arg' || arg === '-a') {
            const pair = args[++i];
            if (pair) {
                const [key, ...valueParts] = pair.split('=');
                const value = valueParts.join('=');
                
                // Try to parse as JSON, fall back to string
                try {
                    toolArgs[key] = JSON.parse(value);
                } catch {
                    toolArgs[key] = value;
                }
            }
        } else if (arg === '--json' || arg === '-j') {
            // Next arg is JSON object of all arguments
            const jsonStr = args[++i];
            if (jsonStr) {
                Object.assign(toolArgs, JSON.parse(jsonStr));
            }
        } else if (arg.includes('=')) {
            // Direct key=value format
            const [key, ...valueParts] = arg.split('=');
            const value = valueParts.join('=');
            try {
                toolArgs[key] = JSON.parse(value);
            } catch {
                toolArgs[key] = value;
            }
        }
    }
    
    return { toolName, toolArgs };
}

async function main() {
    const args = process.argv.slice(2);
    
    if (args.length === 0) {
        console.log('Usage: test-tool.js <tool-name> [key=value ...] [--arg key=value] [--json \'{"key":"value"}\']');
        console.log('');
        console.log('Examples:');
        console.log('  test-tool.js echo message="hello world"');
        console.log('  test-tool.js calculate --arg expression="2+2"');
        console.log('  test-tool.js search --json \'{"query":"test","limit":10}\'');
        process.exit(1);
    }

    const { toolName, toolArgs } = parseArgs(args);
    
    console.log(`Tool: ${toolName}`);
    console.log(`Arguments: ${JSON.stringify(toolArgs, null, 2)}`);
    console.log('');

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
        name: 'mcp-test-tool',
        version: '1.0.0'
    });

    try {
        await client.connect(transport);
        
        console.log('Calling tool...\n');
        const startTime = Date.now();
        
        const result = await client.callTool({
            name: toolName,
            arguments: toolArgs
        });
        
        const duration = Date.now() - startTime;
        
        console.log('=== Result ===');
        console.log(JSON.stringify(result, null, 2));
        console.log('');
        console.log(`Duration: ${duration}ms`);
        console.log(`Is Error: ${result.isError || false}`);
        
        await client.close();
        
        process.exit(result.isError ? 1 : 0);
    } catch (error) {
        console.error(`Error: ${error.message}`);
        process.exit(1);
    }
}

main();
