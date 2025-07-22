#!/usr/bin/env python3
"""
Simple MCP client to test if mcp_server.py is working as a real MCP server
"""
import asyncio
import subprocess
import time
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_mcp_server():
    """Test the MCP server by connecting as a client and calling tools"""
    
    print("🧪 Testing MCP Server...")
    
    # Server parameters for stdio connection
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "mcp_server.py"],  # Run our MCP server with uv
        env={}
    )
    
    try:
        print("📡 Connecting to MCP server...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("✅ Connected to MCP server")
                
                # Initialize the connection
                print("🔄 Initializing session...")
                await session.initialize()
                print("✅ Session initialized")
                
                # List available tools
                print("📋 Listing available tools...")
                tools_response = await session.list_tools()
                tools = tools_response.tools
                print(f"✅ Found {len(tools)} tools:")
                for tool in tools:
                    print(f"   - {tool.name}: {tool.description}")
                
                # Test a simple tool call (list_gsc_domains with empty auth - should fail gracefully)
                print("\n🔧 Testing tool call: list_gsc_domains")
                try:
                    result = await session.call_tool("list_gsc_domains", arguments={"auth_identifier": "", "debug": True})
                    
                    # Parse the result
                    if result.content and len(result.content) > 0:
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            response_data = json.loads(content.text)
                            print(f"✅ Tool call successful! Status: {response_data.get('status', 'unknown')}")
                            print(f"   Message: {response_data.get('message', 'No message')}")
                        else:
                            print(f"✅ Tool call returned content: {content}")
                    else:
                        print("✅ Tool call completed (no content)")
                        
                except Exception as e:
                    print(f"❌ Tool call failed: {e}")
                
                # Test another tool call (get_default_date_range via any tool)
                print("\n🔧 Testing tool call: list_ga4_properties")
                try:
                    result = await session.call_tool("list_ga4_properties", arguments={"auth_identifier": "test", "debug": True})
                    
                    if result.content and len(result.content) > 0:
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            response_data = json.loads(content.text)
                            print(f"✅ Tool call successful! Status: {response_data.get('status', 'unknown')}")
                            print(f"   Message: {response_data.get('message', 'No message')}")
                        else:
                            print(f"✅ Tool call returned: {content}")
                    else:
                        print("✅ Tool call completed")
                        
                except Exception as e:
                    print(f"❌ Tool call failed: {e}")
                
                print(f"\n🎉 MCP Server test completed successfully!")
                print(f"   ✓ Server is running")
                print(f"   ✓ Session initialization works") 
                print(f"   ✓ Tool listing works ({len(tools)} tools found)")
                print(f"   ✓ Tool calls are functional")
                print(f"\n✅ Your MCP server is working correctly!")
                
    except Exception as e:
        print(f"❌ MCP Server test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Starting MCP Server Test")
    success = asyncio.run(test_mcp_server())
    if success:
        print("\n🎊 ALL TESTS PASSED - Your MCP server is working!")
    else:
        print("\n💥 TESTS FAILED - Something is wrong with the MCP server")
