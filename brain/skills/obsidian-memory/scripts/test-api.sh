#!/bin/bash

# Test script for Obsidian Memory API
source .env 2>/dev/null || echo "Warning: .env file not found"

API_URL="${1:-https://memory.redleif.dev/mcp}"
API_KEY="${MCP_API_KEY:-e9bd1591a25a117e540810e8a6ab2710ede03ded676c5d7dad51c34b9682d4e0}"

echo "🧪 Testing Obsidian Memory API"
echo "API URL: $API_URL"
echo "API Key: ${API_KEY:0:16}..."
echo ""

# Test 1: Basic search
echo "📍 Test 1: Basic search"
curl -s -X POST "$API_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"method":"mem_search","params":{"query":"test","maxResults":3}}' \
  | jq '.' 2>/dev/null || echo "❌ Search test failed"

echo -e "\n"

# Test 2: Health check (if available)
echo "📍 Test 2: Health check"
curl -s "${API_URL%/mcp}/health" | jq '.' 2>/dev/null || echo "Health endpoint not available"

echo -e "\n✅ Tests complete"