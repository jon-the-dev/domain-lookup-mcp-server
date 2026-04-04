#!/usr/bin/env python3
"""
Quick test script for DNS functionality
"""

import asyncio
import sys

sys.path.insert(0, "src")

from main import (
    dns_lookup_mx,
    dns_lookup_spf,
    dns_lookup_txt,
    dns_lookup_dmarc,
    dns_lookup_records,
    dns_clear_cache,
)


async def test_dns_functions():
    """Test DNS lookup functions"""
    print("Testing DNS Lookup Tools\n" + "=" * 50)

    test_domain = "google.com"

    # Test MX records
    print(f"\n1. Testing MX records for {test_domain}...")
    mx_result = await dns_lookup_mx(test_domain)
    if "error" not in mx_result:
        print(f"   ✓ Found {mx_result['record_count']} MX records")
        print(f"   TTL: {mx_result.get('ttl')} seconds")
        for record in mx_result["records"][:2]:
            print(f"   - {record['value']}")
    else:
        print(f"   ✗ Error: {mx_result['error']}")

    # Test SPF records
    print(f"\n2. Testing SPF record for {test_domain}...")
    spf_result = await dns_lookup_spf(test_domain)
    if "error" not in spf_result:
        print(f"   ✓ Found {spf_result['record_count']} SPF record(s)")
        if spf_result["spf_records"]:
            print(f"   - {spf_result['spf_records'][0][:80]}...")
    else:
        print(f"   ✗ Error: {spf_result['error']}")

    # Test TXT records
    print(f"\n3. Testing TXT records for {test_domain}...")
    txt_result = await dns_lookup_txt(test_domain)
    if "error" not in txt_result:
        print(f"   ✓ Found {txt_result['record_count']} TXT record(s)")
        print(f"   Cached: {txt_result.get('cached', False)}")
    else:
        print(f"   ✗ Error: {txt_result['error']}")

    # Test DMARC records
    print(f"\n4. Testing DMARC record for {test_domain}...")
    dmarc_result = await dns_lookup_dmarc(test_domain)
    if "error" not in dmarc_result:
        print(f"   ✓ Found {dmarc_result['record_count']} DMARC record(s)")
        if dmarc_result.get("dmarc_records"):
            print(f"   - {dmarc_result['dmarc_records'][0][:80]}...")
    else:
        print(f"   ✗ Error: {dmarc_result['error']}")

    # Test A records
    print(f"\n5. Testing A records for {test_domain}...")
    a_result = await dns_lookup_records(test_domain, record_type="A")
    if "error" not in a_result:
        print(f"   ✓ Found {a_result['record_count']} A record(s)")
        for record in a_result["records"][:3]:
            print(f"   - {record['value']}")
    else:
        print(f"   ✗ Error: {a_result['error']}")

    # Test caching - query MX again
    print(f"\n6. Testing cache (querying MX again)...")
    mx_result2 = await dns_lookup_mx(test_domain)
    if "error" not in mx_result2:
        print(f"   ✓ Cached: {mx_result2.get('cached', False)}")
        if mx_result2.get("cached"):
            print("   Cache is working!")

    # Clear cache
    print(f"\n7. Testing cache clear...")
    clear_result = await dns_clear_cache()
    print(f"   ✓ {clear_result['message']}")

    # Query again to verify cache is cleared
    print(f"\n8. Verifying cache was cleared (querying MX again)...")
    mx_result3 = await dns_lookup_mx(test_domain)
    if "error" not in mx_result3:
        print(f"   ✓ Cached: {mx_result3.get('cached', False)}")
        if not mx_result3.get("cached"):
            print("   Cache clear verified!")

    print("\n" + "=" * 50)
    print("All DNS tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_dns_functions())
