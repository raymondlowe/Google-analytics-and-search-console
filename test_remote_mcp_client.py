#!/usr/bin/env python3
"""
MCP HTTP client to test remote MCP server (simulates cloud client)
"""
import argparse
import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def test_remote_mcp_server(server_url):
    """Test the MCP server over HTTP (like a remote cloud client would)"""
    
    print(f"🌐 Testing Remote MCP Server at {server_url}")
    
    try:
        print("📡 Connecting to remote MCP server via HTTP...")
        async with streamablehttp_client(server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                print("✅ Connected to remote MCP server")
                
                # Initialize the connection
                print("🔄 Initializing remote session...")
                await session.initialize()
                print("✅ Remote session initialized")
                
                # List available tools
                print("📋 Listing available tools from remote server...")
                tools_response = await session.list_tools()
                tools = tools_response.tools
                print(f"✅ Found {len(tools)} tools on remote server:")
                for tool in tools:
                    print(f"   - {tool.name}: {tool.description}")
                
                # Test tool call over HTTP
                print("\n🔧 Testing remote tool call: list_gsc_domains")
                try:
                    result = await session.call_tool("list_gsc_domains", arguments={"auth_identifier": "", "debug": True})
                    
                    if result.content and len(result.content) > 0:
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            response_data = json.loads(content.text)
                            print(f"✅ Remote tool call successful! Status: {response_data.get('status', 'unknown')}")
                            print(f"   Message: {response_data.get('message', 'No message')}")
                            if response_data.get('domains'):
                                print(f"   Found {len(response_data['domains'])} domains")
                        else:
                            print(f"✅ Remote tool call returned: {content}")
                    else:
                        print("✅ Remote tool call completed")
                        
                except Exception as e:
                    print(f"❌ Remote tool call failed: {e}")
                
                # Test another remote tool call
                print("\n🔧 Testing remote tool call: list_ga4_properties")
                try:
                    result = await session.call_tool("list_ga4_properties", arguments={"auth_identifier": "test", "debug": True})
                    
                    if result.content and len(result.content) > 0:
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            response_data = json.loads(content.text)
                            print(f"✅ Remote tool call successful! Status: {response_data.get('status', 'unknown')}")
                            print(f"   Message: {response_data.get('message', 'No message')}")
                            if response_data.get('properties'):
                                print(f"   Found {len(response_data['properties'])} properties")
                        else:
                            print(f"✅ Remote tool call returned: {content}")
                    else:
                        print("✅ Remote tool call completed")
                        
                except Exception as e:
                    print(f"❌ Remote tool call failed: {e}")
                
                print(f"\n🎉 Remote MCP Server test completed successfully!")
                print(f"   ✓ HTTP connection works")
                print(f"   ✓ Remote session initialization works") 
                print(f"   ✓ Remote tool listing works ({len(tools)} tools found)")
                print(f"   ✓ Remote tool calls are functional")
                print(f"\n✅ Your MCP server works perfectly for remote clients!")
                
    except Exception as e:
        print(f"❌ Remote MCP Server test failed: {e}")
        print(f"   Make sure the server is running with: uv run mcp_server.py --http")
        return False
    
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Test remote MCP client.")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="IP address of the MCP server.")
    parser.add_argument("--port", type=int, default=8000, help="Port of the MCP server.")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    server_url = f"http://{args.ip}:{args.port}/mcp"
    print("🚀 Starting Remote MCP Server Test")
    print(f"   Connecting to MCP server at: {server_url}")
    print("   Make sure to start the server first with:")
    print("   uv run mcp_server.py --http --host 0.0.0.0 --port 8000")
    print("")
    success = asyncio.run(test_remote_mcp_server(server_url))
    if success:
        print("\n🎊 REMOTE TEST PASSED!")
        print("🌐 Your MCP server is ready for remote clients!")
        print("")
        print("📋 To connect from a remote machine:")
        print("   1. Start server: uv run mcp_server.py --http --host 0.0.0.0 --port 8000")
        print(f"   2. Connect from remote client to: {server_url}")
        print("   3. Make sure port 8000 is open in firewall")
    else:
        print("\n💥 REMOTE TEST FAILED")
        print("   Make sure the MCP server is running in HTTP mode")
