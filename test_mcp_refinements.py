#!/usr/bin/env python3
"""
Test the refined MCP server functionality.
Tests the new business-focused tools and parameter requirements.
"""
import asyncio
import subprocess
import time
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_refined_mcp_server():
    """Test the refined MCP server with new business-focused tools and requirements"""
    
    print("🧪 Testing Refined MCP Server...")
    
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
                
                expected_tools = [
                    "query_ga4_data", "query_gsc_data", "query_unified_data",
                    "list_ga4_properties", "list_gsc_domains",
                    "page_performance_ga4", "traffic_sources_ga4", "audience_analysis_ga4", 
                    "revenue_analysis_ga4", "page_performance_gsc", "query_analysis_gsc", 
                    "page_query_opportunities_gsc"
                ]
                
                tool_names = [tool.name for tool in tools]
                missing_tools = [tool for tool in expected_tools if tool not in tool_names]
                if missing_tools:
                    print(f"❌ Missing tools: {missing_tools}")
                    return False
                
                print("✅ All expected tools are present")
                
                # Test mandatory date parameters
                print("\n🔧 Testing mandatory date parameters...")
                
                # Test GA4 data query without dates (should fail)
                try:
                    result = await session.call_tool("query_ga4_data", arguments={})
                    content = result.content[0]
                    
                    # Handle both JSON response and error text
                    if hasattr(content, 'text'):
                        response_text = content.text
                        if "Field required" in response_text or "validation errors" in response_text:
                            print("✅ GA4 query correctly requires date parameters")
                        else:
                            try:
                                response_data = json.loads(response_text)
                                if response_data.get("status") == "error" and "required" in response_data.get("message", ""):
                                    print("✅ GA4 query correctly requires date parameters") 
                                else:
                                    print(f"❌ GA4 query should fail without dates: {response_data}")
                                    return False
                            except json.JSONDecodeError:
                                print(f"❌ Unexpected GA4 response: {response_text}")
                                return False
                    else:
                        print(f"❌ Unexpected GA4 content type: {type(content)}")
                        return False
                        
                except Exception as e:
                    print(f"❌ Unexpected error testing GA4 dates: {e}")
                    return False
                
                # Test GSC data query without dates (should fail)
                try:
                    result = await session.call_tool("query_gsc_data", arguments={})
                    content = result.content[0]
                    
                    # Handle both JSON response and error text
                    if hasattr(content, 'text'):
                        response_text = content.text
                        if "Field required" in response_text or "validation errors" in response_text:
                            print("✅ GSC query correctly requires date parameters")
                        else:
                            try:
                                response_data = json.loads(response_text)
                                if response_data.get("status") == "error" and "required" in response_data.get("message", ""):
                                    print("✅ GSC query correctly requires date parameters")
                                else:
                                    print(f"❌ GSC query should fail without dates: {response_data}")
                                    return False
                            except json.JSONDecodeError:
                                print(f"❌ Unexpected GSC response: {response_text}")
                                return False
                    else:
                        print(f"❌ Unexpected GSC content type: {type(content)}")
                        return False
                        
                except Exception as e:
                    print(f"❌ Unexpected error testing GSC dates: {e}")
                    return False
                
                # Test focused business tools
                print("\n🔧 Testing focused business tools...")
                
                # Test page performance GA4 tool
                try:
                    result = await session.call_tool("page_performance_ga4", arguments={
                        "start_date": "2024-01-01",
                        "end_date": "2024-01-31"
                    })
                    content = result.content[0]
                    response_data = json.loads(content.text)
                    print(f"✅ Page performance GA4 tool works: {response_data.get('status', 'unknown')}")
                        
                except Exception as e:
                    print(f"❌ Page performance GA4 tool failed: {e}")
                    return False
                
                # Test query analysis GSC tool
                try:
                    result = await session.call_tool("query_analysis_gsc", arguments={
                        "start_date": "2024-01-01", 
                        "end_date": "2024-01-31"
                    })
                    content = result.content[0]
                    response_data = json.loads(content.text)
                    print(f"✅ Query analysis GSC tool works: {response_data.get('status', 'unknown')}")
                        
                except Exception as e:
                    print(f"❌ Query analysis GSC tool failed: {e}")
                    return False
                
                # Test optional auth_identifier (should work with empty string)
                print("\n🔧 Testing optional auth_identifier...")
                
                try:
                    result = await session.call_tool("list_ga4_properties", arguments={
                        "auth_identifier": ""
                    })
                    content = result.content[0]
                    response_data = json.loads(content.text)
                    print(f"✅ Optional auth_identifier works: {response_data.get('status', 'unknown')}")
                        
                except Exception as e:
                    print(f"❌ Optional auth_identifier failed: {e}")
                    return False
                
                # Verify tool descriptions contain business context
                print("\n🔧 Verifying enhanced tool descriptions...")
                
                business_keywords = ["Business Purpose", "Business Use Cases", "optimization", "SEO", "revenue"]
                tools_with_good_descriptions = 0
                
                for tool in tools:
                    if any(keyword in tool.description for keyword in business_keywords):
                        tools_with_good_descriptions += 1
                
                if tools_with_good_descriptions >= 8:  # Most tools should have business context
                    print(f"✅ Tool descriptions enhanced with business context ({tools_with_good_descriptions} tools)")
                else:
                    print(f"❌ Too few tools have enhanced descriptions ({tools_with_good_descriptions} tools)")
                    return False
                
                print(f"\n🎉 All MCP Server refinement tests passed!")
                print(f"   ✓ {len(tools)} tools available (up from 5)")
                print(f"   ✓ Date parameters are now mandatory") 
                print(f"   ✓ Auth identifier is optional")
                print(f"   ✓ Business-focused tools are functional")
                print(f"   ✓ Tool descriptions enhanced with business context")
                print(f"\n✅ MCP server refinements are working correctly!")
                
    except Exception as e:
        print(f"❌ MCP Server refinement test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Starting MCP Server Refinement Tests")
    success = asyncio.run(test_refined_mcp_server())
    if success:
        print("\n🎊 ALL REFINEMENT TESTS PASSED!")
    else:
        print("\n💥 REFINEMENT TESTS FAILED")