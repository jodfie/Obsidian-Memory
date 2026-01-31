#!/usr/bin/env node

/**
 * MCP Server Test Runner
 * Connects to remote MCP servers and executes test suites
 */

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { SSEClientTransport } from '@modelcontextprotocol/sdk/client/sse.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import fs from 'fs';
import path from 'path';

// Configuration from environment
const config = {
    serverUrl: process.env.MCP_SERVER_URL,
    accessToken: process.env.MCP_ACCESS_TOKEN,
    refreshToken: process.env.MCP_REFRESH_TOKEN,
    timeout: parseInt(process.env.TEST_TIMEOUT || '30000'),
    outputDir: process.env.TEST_OUTPUT_DIR || '/app/results',
    cfClientId: process.env.CF_ACCESS_CLIENT_ID,
    cfClientSecret: process.env.CF_ACCESS_CLIENT_SECRET,
};

// Test results collection
const results = {
    server: config.serverUrl,
    timestamp: new Date().toISOString(),
    tests: [],
    summary: { total: 0, passed: 0, failed: 0, skipped: 0 }
};

/**
 * Create MCP client with appropriate transport
 */
async function createClient() {
    const url = new URL(config.serverUrl);
    
    // Build headers for authentication
    const headers = {};
    
    if (config.accessToken) {
        headers['Authorization'] = `Bearer ${config.accessToken}`;
    }
    
    // Cloudflare Access service token auth
    if (config.cfClientId && config.cfClientSecret) {
        headers['CF-Access-Client-Id'] = config.cfClientId;
        headers['CF-Access-Client-Secret'] = config.cfClientSecret;
    }

    // Determine transport type from URL
    let transport;
    
    if (url.pathname.endsWith('/sse') || url.pathname.includes('/sse')) {
        console.log('Using SSE transport');
        transport = new SSEClientTransport(url, { headers });
    } else {
        console.log('Using Streamable HTTP transport');
        transport = new StreamableHTTPClientTransport(url, { headers });
    }

    const client = new Client({
        name: 'mcp-test-harness',
        version: '1.0.0'
    });

    await client.connect(transport);
    return client;
}

/**
 * Run a single test case
 */
async function runTest(client, test) {
    const startTime = Date.now();
    const testResult = {
        name: test.name,
        type: test.type,
        status: 'pending',
        duration: 0,
        error: null,
        output: null
    };

    try {
        console.log(`  Running: ${test.name}`);

        switch (test.type) {
            case 'list-tools':
                const toolsResult = await client.listTools();
                testResult.output = toolsResult.tools;
                testResult.status = toolsResult.tools.length > 0 ? 'passed' : 'failed';
                if (test.expect?.minTools) {
                    testResult.status = toolsResult.tools.length >= test.expect.minTools ? 'passed' : 'failed';
                }
                break;

            case 'list-resources':
                const resourcesResult = await client.listResources();
                testResult.output = resourcesResult.resources;
                testResult.status = 'passed';
                break;

            case 'list-prompts':
                const promptsResult = await client.listPrompts();
                testResult.output = promptsResult.prompts;
                testResult.status = 'passed';
                break;

            case 'call-tool':
                const toolResult = await client.callTool({
                    name: test.tool,
                    arguments: test.arguments || {}
                });
                testResult.output = toolResult;

                // Check expectations
                // Note: MCP SDK returns isError: undefined for success, not isError: false
                const actualIsError = toolResult.isError === true;

                if (test.expect) {
                    if (test.expect.isError !== undefined) {
                        const expectedIsError = test.expect.isError === true;
                        testResult.status = (actualIsError === expectedIsError) ? 'passed' : 'failed';
                    } else if (test.expect.contains) {
                        const content = JSON.stringify(toolResult);
                        testResult.status = content.includes(test.expect.contains) ? 'passed' : 'failed';
                    } else {
                        testResult.status = 'passed';
                    }
                } else {
                    testResult.status = actualIsError ? 'failed' : 'passed';
                }
                break;

            case 'read-resource':
                const resourceResult = await client.readResource({
                    uri: test.uri
                });
                testResult.output = resourceResult;
                testResult.status = 'passed';
                break;

            case 'get-prompt':
                const promptResult = await client.getPrompt({
                    name: test.prompt,
                    arguments: test.arguments || {}
                });
                testResult.output = promptResult;
                testResult.status = 'passed';
                break;

            default:
                testResult.status = 'skipped';
                testResult.error = `Unknown test type: ${test.type}`;
        }

    } catch (error) {
        testResult.error = error.message;

        // If test expects an error, this is a pass
        if (test.expect?.isError === true) {
            testResult.status = 'passed';
            console.log(`    (Expected error: ${error.message})`);
        } else {
            testResult.status = 'failed';
            console.log(`    ✗ Error: ${error.message}`);
        }
    }

    testResult.duration = Date.now() - startTime;
    
    const statusIcon = testResult.status === 'passed' ? '✓' : 
                       testResult.status === 'failed' ? '✗' : '○';
    console.log(`    ${statusIcon} ${testResult.status} (${testResult.duration}ms)`);
    
    return testResult;
}

/**
 * Load test definitions from files
 */
function loadTests() {
    const testsDir = '/app/tests';
    const tests = [];

    // Default connectivity tests (only list-tools - resources/prompts are optional)
    tests.push(
        { name: 'List Tools', type: 'list-tools', expect: { minTools: 0 } }
    );

    // Load custom test files
    if (fs.existsSync(testsDir)) {
        const files = fs.readdirSync(testsDir).filter(f => f.endsWith('.json'));
        
        for (const file of files) {
            try {
                const content = fs.readFileSync(path.join(testsDir, file), 'utf8');
                const customTests = JSON.parse(content);
                
                if (Array.isArray(customTests)) {
                    tests.push(...customTests);
                } else if (customTests.tests) {
                    tests.push(...customTests.tests);
                }
            } catch (error) {
                console.warn(`Warning: Failed to load ${file}: ${error.message}`);
            }
        }
    }

    return tests;
}

/**
 * Main test execution
 */
async function main() {
    console.log('=== MCP Server Test Runner ===');
    console.log(`Server: ${config.serverUrl}`);
    console.log(`Timeout: ${config.timeout}ms`);
    console.log('');

    let client;
    let exitCode = 0;

    try {
        // Connect to server
        console.log('Connecting to MCP server...');
        client = await createClient();
        console.log('Connected successfully!\n');

        // Load and run tests
        const tests = loadTests();
        console.log(`Running ${tests.length} tests...\n`);

        for (const test of tests) {
            const result = await runTest(client, test);
            results.tests.push(result);
            results.summary.total++;
            results.summary[result.status]++;
        }

    } catch (error) {
        console.error(`\nFatal error: ${error.message}`);
        results.error = error.message;
        exitCode = 1;
    } finally {
        if (client) {
            try {
                await client.close();
            } catch (e) {
                // Ignore close errors
            }
        }
    }

    // Write results
    console.log('\n=== Summary ===');
    console.log(`Total: ${results.summary.total}`);
    console.log(`Passed: ${results.summary.passed}`);
    console.log(`Failed: ${results.summary.failed}`);
    console.log(`Skipped: ${results.summary.skipped}`);

    // Ensure output directory exists
    fs.mkdirSync(config.outputDir, { recursive: true });

    // Write detailed results
    fs.writeFileSync(
        path.join(config.outputDir, 'results.json'),
        JSON.stringify(results, null, 2)
    );

    // Write summary for CI
    fs.writeFileSync(
        path.join(config.outputDir, 'summary.json'),
        JSON.stringify(results.summary, null, 2)
    );

    // Write JUnit XML for CI integration
    const junitXml = generateJUnitXml(results);
    fs.writeFileSync(
        path.join(config.outputDir, 'junit.xml'),
        junitXml
    );

    if (results.summary.failed > 0) {
        exitCode = 1;
    }

    process.exit(exitCode);
}

/**
 * Generate JUnit XML for CI systems
 */
function generateJUnitXml(results) {
    const escapeXml = (str) => str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');

    let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
    xml += `<testsuite name="MCP Server Tests" tests="${results.summary.total}" `;
    xml += `failures="${results.summary.failed}" skipped="${results.summary.skipped}" `;
    xml += `timestamp="${results.timestamp}">\n`;

    for (const test of results.tests) {
        xml += `  <testcase name="${escapeXml(test.name)}" time="${test.duration / 1000}"`;
        
        if (test.status === 'passed') {
            xml += '/>\n';
        } else if (test.status === 'skipped') {
            xml += '>\n    <skipped/>\n  </testcase>\n';
        } else {
            xml += '>\n';
            xml += `    <failure message="${escapeXml(test.error || 'Test failed')}">\n`;
            if (test.output) {
                xml += `      ${escapeXml(JSON.stringify(test.output, null, 2))}\n`;
            }
            xml += '    </failure>\n';
            xml += '  </testcase>\n';
        }
    }

    xml += '</testsuite>\n';
    return xml;
}

// Run
main().catch(console.error);
