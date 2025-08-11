#!/usr/bin/env python3

"""
Test script for the Domain Lookup MCP Server
"""

import asyncio
import json
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main import (
    whois_domain, whois_domains, whois_tld, whois_ip, whois_asn,
    setup_domain_lookup_mcp_server
)


async def test_setup_info():
    """Test the setup information tool."""
    print("Testing setup_domain_lookup_mcp_server...")
    try:
        result = await setup_domain_lookup_mcp_server()
        print("✅ Setup info retrieved successfully")
        print(f"Server: {result['server_info']['name']}")
        print(f"Tools available: {len(result['available_tools'])}")
        return True
    except Exception as e:
        print(f"❌ Setup info failed: {str(e)}")
        return False


async def test_single_domain():
    """Test single domain lookup."""
    print("\nTesting whois_domain...")
    try:
        # Test with a known registered domain
        result = await whois_domain("google.com")
        print("✅ Single domain lookup successful")
        print(f"Domain: google.com")
        print(f"Registered: {result.get('is_registered', 'unknown')}")
        if 'parsed_fields' in result and result['parsed_fields']:
            print(f"Registrar: {result['parsed_fields'].get('registrar', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ Single domain lookup failed: {str(e)}")
        return False


async def test_multiple_domains():
    """Test multiple domain lookup."""
    print("\nTesting whois_domains...")
    try:
        test_domains = ["google.com", "thisshouldnotexist999.com", "github.com"]
        result = await whois_domains(test_domains)
        print("✅ Multiple domain lookup successful")
        summary = result.get('summary', {})
        print(f"Total domains: {summary.get('total_domains', 0)}")
        print(f"Registered: {summary.get('registered_domains', 0)}")
        print(f"Available: {summary.get('available_domains', 0)}")
        print(f"Errors: {summary.get('errors', 0)}")
        return True
    except Exception as e:
        print(f"❌ Multiple domain lookup failed: {str(e)}")
        return False


async def test_ip_lookup():
    """Test IP address lookup."""
    print("\nTesting whois_ip...")
    try:
        # Test with Google's public DNS
        result = await whois_ip("8.8.8.8")
        print("✅ IP lookup successful")
        print(f"IP: 8.8.8.8")
        if 'error' not in result:
            parsed = result.get('parsed_fields', {})
            org = parsed.get('org') or parsed.get('organization') or parsed.get('orgname')
            if org:
                print(f"Organization: {org}")
        return True
    except Exception as e:
        print(f"❌ IP lookup failed: {str(e)}")
        return False


async def test_tld_lookup():
    """Test TLD lookup."""
    print("\nTesting whois_tld...")
    try:
        result = await whois_tld("com")
        print("✅ TLD lookup successful")
        print("TLD: .com")
        if 'error' not in result:
            parsed = result.get('parsed_fields', {})
            if parsed:
                print(f"Registry info available: {len(parsed)} fields")
        return True
    except Exception as e:
        print(f"❌ TLD lookup failed: {str(e)}")
        return False


async def test_asn_lookup():
    """Test ASN lookup."""
    print("\nTesting whois_asn...")
    try:
        # Test with Google's ASN
        result = await whois_asn("15169")
        print("✅ ASN lookup successful")
        print("ASN: AS15169")
        if 'error' not in result:
            parsed = result.get('parsed_fields', {})
            org = parsed.get('org') or parsed.get('organization') or parsed.get('as-name')
            if org:
                print(f"Organization: {org}")
        return True
    except Exception as e:
        print(f"❌ ASN lookup failed: {str(e)}")
        return False


async def main():
    """Run all tests."""
    print("Domain Lookup MCP Server Test Suite")
    print("=" * 40)
    
    tests = [
        test_setup_info,
        test_single_domain,
        test_multiple_domains,
        test_ip_lookup,
        test_tld_lookup,
        test_asn_lookup
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if await test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {str(e)}")
    
    print(f"\n{'=' * 40}")
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {total - passed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))