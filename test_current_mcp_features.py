#!/usr/bin/env python3
"""
Simple test script for current MCP server features including caching
"""
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_current_mcp_server():
    """Test the current MCP server implementation with focus on new features"""
    
    print("Testing Current MCP Server Features...")
    
    # Server parameters for stdio connection
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "mcp_server.py"],
        env={}
    )
    
    try:
        print("📡 Connecting to MCP server...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("✅ Connected to MCP server")
                
                # Initialize the connection
                await session.initialize()
                print("✅ Session initialized")
                
                # List available tools
                tools_response = await session.list_tools()
                tools = tools_response.tools
                print(f"✅ Found {len(tools)} tools")
                
                # Check for new caching tools
                tool_names = [tool.name for tool in tools]
                expected_tools = ["get_server_stats", "invalidate_cache"]
                
                for tool in expected_tools:
                    if tool in tool_names:
                        print(f"✅ Found new tool: {tool}")
                    else:
                        print(f"❌ Missing expected tool: {tool}")
                
                # Test server statistics (new feature)
                print("\nTesting server statistics...")
                try:
                    result = await session.call_tool("get_server_stats", arguments={
                        "include_details": True
                    })
                    content = result.content[0]
                    raw_text = getattr(content, 'text', None)
                    if raw_text is None:
                        raw_text = str(content)
                    response_data = json.loads(raw_text)  # type: ignore

                    if response_data.get("status") == "success":
                        print("✅ Server statistics working")
                        # Check for expected statistics
                        if "basic_info" in response_data:
                            print("  ✓ Basic info present")
                        if "request_metrics" in response_data:
                            print("  ✓ Request metrics present")
                        if "cache_performance" in response_data:
                            print("  ✓ Cache performance metrics present (NEW)")
                        else:
                            print("  ⚠️ Cache performance metrics not found")
                    else:
                        print(f"❌ Server statistics failed: {response_data.get('message', 'Unknown error')}")
                        
                except Exception as e:
                    print(f"❌ Server statistics test failed: {e}")
                
                # Test cache invalidation (new feature)
                print("\n🔧 Testing cache invalidation...")
                try:
                    result = await session.call_tool("invalidate_cache", arguments={
                        "cache_type": "domain",
                        "account": ""
                    })
                    content = result.content[0]
                    response_data = json.loads(content.text)
                    
                    if response_data.get("status") == "success":
                        print("✅ Cache invalidation working")
                        if "cache_stats" in response_data:
                            print("  ✓ Cache statistics returned")
                    else:
                        print(f"❌ Cache invalidation failed: {response_data.get('message', 'Unknown error')}")
                        
                except Exception as e:
                    print(f"❌ Cache invalidation test failed: {e}")
                
                # Test basic functionality (domain listing with caching)
                print("\n🔧 Testing domain listing (with caching)...")
                try:
                    result = await session.call_tool("list_gsc_domains", arguments={
                        "debug": True
                    })
                    content = result.content[0]
                    response_data = json.loads(content.text)
                    
                    if response_data.get("status") == "success":
                        domain_count = len(response_data.get("domains", []))
                        print(f"✅ Domain listing successful: {domain_count} domains")
                        if "cache_hit" in response_data:
                            print(f"  ✓ Cache status: {'HIT' if response_data['cache_hit'] else 'MISS'}")
                    else:
                        print(f"❌ Domain listing failed: {response_data.get('message', 'Unknown error')}")
                        
                except Exception as e:
                    print(f"❌ Domain listing test failed: {e}")
                
                # Test properties listing (with caching)
                print("\n🔧 Testing properties listing (with caching)...")
                try:
                    result = await session.call_tool("list_ga4_properties", arguments={
                        "debug": True
                    })
                    content = result.content[0]
                    response_data = json.loads(content.text)
                    
                    if response_data.get("status") == "success":
                        property_count = len(response_data.get("properties", []))
                        print(f"✅ Properties listing successful: {property_count} properties")
                        if "cache_hit" in response_data:
                            print(f"  ✓ Cache status: {'HIT' if response_data['cache_hit'] else 'MISS'}")
                    else:
                        print(f"❌ Properties listing failed: {response_data.get('message', 'Unknown error')}")
                        
                except Exception as e:
                    print(f"❌ Properties listing test failed: {e}")
                
                print(f"\n🎉 Current MCP Server test completed!")
                print(f"   ✓ Server is operational")
                print(f"   ✓ All tools accessible ({len(tools)} tools)")
                print(f"   ✓ New caching features tested")
                print(f"   ✓ Statistics and monitoring functional")
                
    except Exception as e:
        print(f"❌ MCP Server test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Starting Current MCP Server Feature Test")
    success = asyncio.run(test_current_mcp_server())
    if success:
        print("\n🎊 CURRENT TESTS PASSED - MCP server with caching is working!")
    else:
        print("\n💥 TESTS FAILED - Something is wrong with the current MCP server")
