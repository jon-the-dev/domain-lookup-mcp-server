#!/usr/bin/env python3

"""
Domain Lookup MCP Server

An MCP server that provides domain lookup tools for WHOIS and DNS information.
Designed to be efficient for LLM workflows.
"""

import asyncio
import logging
import subprocess
import json
import socket
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone, timedelta

import fastmcp
import dns.resolver
import dns.exception
from dns.resolver import NoResolverConfiguration

# Configure logging to stderr (critical for MCP servers)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("domain-lookup-mcp")

# Create the MCP server
mcp = fastmcp.FastMCP("Domain Lookup MCP Server")


# Cache configuration
CACHE_DIR = Path.home() / ".cache" / "domain-lookup-mcp"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_CACHE_TTL = timedelta(hours=24)  # Default 24 hour cache


class DNSCache:
    """File-based cache for DNS records with TTL support."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, domain: str, record_type: str, extra: str = "") -> str:
        """Generate cache key from domain and record type."""
        key_data = f"{domain.lower()}:{record_type}:{extra}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key."""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, domain: str, record_type: str, extra: str = "") -> Optional[Dict[str, Any]]:
        """Get cached DNS record if not expired."""
        cache_key = self._get_cache_key(domain, record_type, extra)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                cached_data = json.load(f)

            # Check if cache is expired
            cached_time = datetime.fromisoformat(cached_data["cached_at"])
            ttl = timedelta(seconds=cached_data.get("ttl", DEFAULT_CACHE_TTL.total_seconds()))

            if datetime.now(timezone.utc) - cached_time > ttl:
                # Cache expired, remove it
                cache_path.unlink()
                return None

            logger.debug(f"Cache hit for {domain} {record_type}")
            return cached_data["data"]

        except Exception as e:
            logger.warning(f"Error reading cache for {domain} {record_type}: {str(e)}")
            return None

    def set(
        self,
        domain: str,
        record_type: str,
        data: Dict[str, Any],
        ttl: Optional[timedelta] = None,
        extra: str = "",
    ):
        """Cache DNS record with TTL."""
        if ttl is None:
            ttl = DEFAULT_CACHE_TTL

        cache_key = self._get_cache_key(domain, record_type, extra)
        cache_path = self._get_cache_path(cache_key)

        cached_data = {
            "domain": domain,
            "record_type": record_type,
            "data": data,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "ttl": int(ttl.total_seconds()),
        }

        try:
            with open(cache_path, "w") as f:
                json.dump(cached_data, f, indent=2)
            logger.debug(f"Cached {domain} {record_type} for {ttl}")
        except Exception as e:
            logger.warning(f"Error writing cache for {domain} {record_type}: {str(e)}")

    def clear(self):
        """Clear all cached entries."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")


# Initialize DNS cache
dns_cache = DNSCache()


async def run_whois_command(query: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Run whois command and parse output.

    Args:
        query: Domain, IP, or ASN to query
        timeout: Command timeout in seconds

    Returns:
        Parsed whois information
    """
    try:
        # Run whois command with timeout
        process = await asyncio.create_subprocess_exec(
            "whois", query, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "error": f"WHOIS query timed out after {timeout} seconds",
                "query": query,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="ignore").strip()
            return {
                "error": f"WHOIS command failed: {error_msg or 'Unknown error'}",
                "query": query,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        raw_output = stdout.decode("utf-8", errors="ignore")

        # Parse basic information from whois output
        lines = raw_output.split("\n")
        parsed_data = {
            "query": query,
            "raw_output": raw_output,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "parsed_fields": {},
        }

        # Extract common fields
        for line in lines:
            line = line.strip()
            if ":" in line and not line.startswith("%") and not line.startswith("#"):
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                if value and key:
                    if key in parsed_data["parsed_fields"]:
                        # Handle multiple values for same field
                        if isinstance(parsed_data["parsed_fields"][key], list):
                            parsed_data["parsed_fields"][key].append(value)
                        else:
                            parsed_data["parsed_fields"][key] = [
                                parsed_data["parsed_fields"][key],
                                value,
                            ]
                    else:
                        parsed_data["parsed_fields"][key] = value

        return parsed_data

    except Exception as e:
        logger.error(f"Error running whois for {query}: {str(e)}")
        return {
            "error": f"Internal error: {str(e)}",
            "query": query,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def resolve_domain_ip(domain: str) -> Optional[str]:
    """Resolve domain to IP address."""
    try:
        # Remove protocol if present
        domain = domain.replace("http://", "").replace("https://", "")
        # Remove path if present
        domain = domain.split("/")[0]
        # Remove port if present
        domain = domain.split(":")[0]

        ip = socket.gethostbyname(domain)
        return ip
    except Exception as e:
        logger.debug(f"Could not resolve {domain} to IP: {str(e)}")
        return None


def clean_domain(domain: str) -> str:
    """Clean and normalize domain input."""
    domain = domain.strip().lower()
    # Remove protocol if present
    domain = domain.replace("http://", "").replace("https://", "")
    # Remove path if present
    domain = domain.split("/")[0]
    # Remove port if present
    domain = domain.split(":")[0]
    return domain


async def query_dns_records(
    domain: str, record_type: str, use_cache: bool = True
) -> Dict[str, Any]:
    """
    Query DNS records with caching support.

    Args:
        domain: Domain to query
        record_type: DNS record type (MX, TXT, A, AAAA, NS, CNAME, etc.)
        use_cache: Whether to use cached results

    Returns:
        DNS query results with records and metadata
    """
    domain = clean_domain(domain)

    # Check cache first
    if use_cache:
        cached = dns_cache.get(domain, record_type)
        if cached:
            return cached

    try:
        # Perform DNS query
        # Use configure=False to avoid reading /etc/resolv.conf which may not exist
        # in Docker/restricted environments
        try:
            resolver = dns.resolver.Resolver()
        except dns.resolver.NoResolverConfiguration:
            resolver = dns.resolver.Resolver(configure=False)

        resolver.timeout = 5
        resolver.lifetime = 10

        # Always use public DNS servers to ensure reliability
        resolver.nameservers = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]

        answers = resolver.resolve(domain, record_type)

        # Extract records
        records = []
        min_ttl = None

        for rdata in answers:
            record_data = {"value": str(rdata)}

            # Add specific fields based on record type
            if record_type == "MX":
                record_data["preference"] = rdata.preference
                record_data["exchange"] = str(rdata.exchange)
                record_data["value"] = f"{rdata.preference} {rdata.exchange}"
            elif record_type == "SOA":
                record_data["mname"] = str(rdata.mname)
                record_data["rname"] = str(rdata.rname)
                record_data["serial"] = rdata.serial
            elif record_type == "SRV":
                record_data["priority"] = rdata.priority
                record_data["weight"] = rdata.weight
                record_data["port"] = rdata.port
                record_data["target"] = str(rdata.target)

            records.append(record_data)

        # Get TTL from response
        if answers.rrset:
            min_ttl = answers.rrset.ttl

        result = {
            "domain": domain,
            "record_type": record_type,
            "records": records,
            "record_count": len(records),
            "ttl": min_ttl,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cached": False,
        }

        # Cache the result using DNS TTL or default
        cache_ttl = timedelta(seconds=min_ttl) if min_ttl else DEFAULT_CACHE_TTL
        dns_cache.set(domain, record_type, result, cache_ttl)

        return result

    except dns.resolver.NXDOMAIN:
        result = {
            "error": f"Domain {domain} does not exist (NXDOMAIN)",
            "domain": domain,
            "record_type": record_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result
    except dns.resolver.NoAnswer:
        result = {
            "error": f"No {record_type} records found for {domain}",
            "domain": domain,
            "record_type": record_type,
            "records": [],
            "record_count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result
    except dns.resolver.Timeout:
        result = {
            "error": f"DNS query timeout for {domain} {record_type} records",
            "domain": domain,
            "record_type": record_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result
    except Exception as e:
        logger.error(f"Error querying DNS for {domain} {record_type}: {str(e)}")
        result = {
            "error": f"DNS query failed: {str(e)}",
            "domain": domain,
            "record_type": record_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result


async def extract_spf_record(domain: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Extract SPF record from TXT records.

    Args:
        domain: Domain to query
        use_cache: Whether to use cached results

    Returns:
        SPF record information
    """
    txt_result = await query_dns_records(domain, "TXT", use_cache)

    if "error" in txt_result:
        return txt_result

    # Find SPF record
    spf_records = []
    for record in txt_result.get("records", []):
        value = record.get("value", "")
        if value.startswith('"v=spf1') or value.startswith("v=spf1"):
            # Clean quotes
            spf_value = value.strip('"')
            spf_records.append(spf_value)

    result = {
        "domain": domain,
        "record_type": "SPF",
        "spf_records": spf_records,
        "record_count": len(spf_records),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cached": txt_result.get("cached", False),
    }

    if not spf_records:
        result["error"] = f"No SPF record found for {domain}"

    return result


async def query_dkim_record(domain: str, selector: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Query DKIM record for a domain with a specific selector.

    Args:
        domain: Domain to query
        selector: DKIM selector (e.g., 'default', 'google', 's1')
        use_cache: Whether to use cached results

    Returns:
        DKIM record information
    """
    # DKIM records are at selector._domainkey.domain
    dkim_domain = f"{selector}._domainkey.{clean_domain(domain)}"

    # Check cache with selector as extra key
    if use_cache:
        cached = dns_cache.get(domain, "DKIM", selector)
        if cached:
            return cached

    txt_result = await query_dns_records(dkim_domain, "TXT", use_cache=False)

    if "error" in txt_result:
        result = {
            "error": f"No DKIM record found for selector '{selector}' at {domain}. Common selectors: default, google, s1, s2, k1",
            "domain": domain,
            "selector": selector,
            "dkim_domain": dkim_domain,
            "record_type": "DKIM",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result

    # Extract DKIM records (they start with v=DKIM1)
    dkim_records = []
    for record in txt_result.get("records", []):
        value = record.get("value", "").strip('"')
        # DKIM records might be split across multiple strings
        if "v=DKIM1" in value or "p=" in value:
            dkim_records.append(value)

    result = {
        "domain": domain,
        "selector": selector,
        "dkim_domain": dkim_domain,
        "record_type": "DKIM",
        "dkim_records": dkim_records,
        "record_count": len(dkim_records),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }

    if not dkim_records:
        result["error"] = f"No DKIM record found for selector '{selector}' at {domain}"

    # Cache with selector as extra key
    if dkim_records:
        dns_cache.set(domain, "DKIM", result, extra=selector)

    return result


@mcp.tool()
async def whois_domain(domain: str) -> Dict[str, Any]:
    """
    Look up WHOIS information for a single domain.

    Args:
        domain: The domain name to look up (e.g., 'example.com')

    Returns:
        WHOIS information including registration status, registrar, creation date, etc.
    """
    # Clean domain input
    domain = domain.strip().lower()
    # Remove protocol if present
    domain = domain.replace("http://", "").replace("https://", "")
    # Remove path if present
    domain = domain.split("/")[0]
    # Remove port if present
    domain = domain.split(":")[0]

    logger.info(f"Looking up WHOIS for domain: {domain}")

    result = await run_whois_command(domain)

    # Add registration status analysis
    if "error" not in result:
        raw_output = result.get("raw_output", "").lower()
        parsed_fields = result.get("parsed_fields", {})

        # Determine if domain is registered
        is_registered = True
        if any(
            phrase in raw_output
            for phrase in [
                "no match",
                "not found",
                "no data found",
                "status: available",
                "no matching record",
                "not registered",
            ]
        ):
            is_registered = False

        result["is_registered"] = is_registered
        result["analysis"] = {
            "registered": is_registered,
            "has_registrar": bool(parsed_fields.get("registrar")),
            "has_creation_date": bool(
                parsed_fields.get("creation_date") or parsed_fields.get("created")
            ),
            "has_expiry_date": bool(
                parsed_fields.get("expiry_date") or parsed_fields.get("expires")
            ),
        }

    return result


@mcp.tool()
async def whois_domains(domains: List[str]) -> Dict[str, Any]:
    """
    Look up WHOIS information for multiple domains efficiently.

    Args:
        domains: List of domain names to look up

    Returns:
        Dictionary with results for each domain and summary statistics
    """
    logger.info(f"Looking up WHOIS for {len(domains)} domains")

    # Limit concurrent requests to avoid overwhelming WHOIS servers
    semaphore = asyncio.Semaphore(5)

    async def lookup_single(domain: str) -> tuple[str, Dict[str, Any]]:
        async with semaphore:
            result = await whois_domain(domain)
            # Add small delay to be respectful to WHOIS servers
            await asyncio.sleep(0.1)
            return domain, result

    # Execute all lookups concurrently
    tasks = [lookup_single(domain) for domain in domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    domain_results = {}
    registered_count = 0
    error_count = 0

    for result in results:
        if isinstance(result, Exception):
            error_count += 1
            continue

        domain, whois_result = result
        domain_results[domain] = whois_result

        if whois_result.get("is_registered", False):
            registered_count += 1
        if "error" in whois_result:
            error_count += 1

    return {
        "results": domain_results,
        "summary": {
            "total_domains": len(domains),
            "registered_domains": registered_count,
            "available_domains": len(domains) - registered_count - error_count,
            "errors": error_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


@mcp.tool()
async def whois_tld(tld: str) -> Dict[str, Any]:
    """
    Look up WHOIS information for a Top Level Domain (TLD).

    Args:
        tld: The TLD to look up (e.g., 'com', '.org', 'net')

    Returns:
        WHOIS information about the TLD registry
    """
    # Clean TLD input
    tld = tld.strip().lower()
    if not tld.startswith("."):
        tld = "." + tld

    logger.info(f"Looking up WHOIS for TLD: {tld}")

    # For TLDs, we query the TLD directly
    result = await run_whois_command(tld)

    return result


@mcp.tool()
async def whois_ip(ip_address: str) -> Dict[str, Any]:
    """
    Look up WHOIS information for an IP address.

    Args:
        ip_address: The IP address to look up (IPv4 or IPv6)

    Returns:
        WHOIS information including ISP, organization, country, etc.
    """
    ip_address = ip_address.strip()
    logger.info(f"Looking up WHOIS for IP: {ip_address}")

    result = await run_whois_command(ip_address)

    return result


@mcp.tool()
async def whois_asn(asn: Union[str, int]) -> Dict[str, Any]:
    """
    Look up WHOIS information for an Autonomous System Number (ASN).

    Args:
        asn: The ASN to look up (e.g., 'AS15169' or 15169)

    Returns:
        WHOIS information about the ASN including organization and description
    """
    # Convert ASN to proper format
    if isinstance(asn, int):
        asn = f"AS{asn}"
    elif isinstance(asn, str):
        asn = asn.strip().upper()
        if asn.isdigit():
            asn = f"AS{asn}"

    logger.info(f"Looking up WHOIS for ASN: {asn}")

    result = await run_whois_command(asn)

    return result


@mcp.tool()
async def dns_lookup_mx(domain: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Look up MX (Mail Exchange) records for a domain.

    Args:
        domain: Domain to query (e.g., 'gmail.com')
        use_cache: Use cached results if available (default: True)

    Returns:
        MX records with mail server priorities and names
    """
    logger.info(f"Looking up MX records for: {domain}")
    return await query_dns_records(domain, "MX", use_cache)


@mcp.tool()
async def dns_lookup_spf(domain: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Look up SPF (Sender Policy Framework) record for a domain.

    SPF records define which mail servers are authorized to send email for the domain.

    Args:
        domain: Domain to query (e.g., 'gmail.com')
        use_cache: Use cached results if available (default: True)

    Returns:
        SPF record information extracted from TXT records
    """
    logger.info(f"Looking up SPF record for: {domain}")
    return await extract_spf_record(domain, use_cache)


@mcp.tool()
async def dns_lookup_dkim(
    domain: str, selector: str = "default", use_cache: bool = True
) -> Dict[str, Any]:
    """
    Look up DKIM (DomainKeys Identified Mail) record for a domain with a specific selector.

    DKIM records are used to verify email authenticity. You need to know the selector used by the domain.
    Common selectors: 'default', 'google', 's1', 's2', 'k1', 'selector1', 'selector2'

    Args:
        domain: Domain to query (e.g., 'gmail.com')
        selector: DKIM selector to use (default: 'default'). Try 'google' for Google Workspace
        use_cache: Use cached results if available (default: True)

    Returns:
        DKIM public key record for email verification
    """
    logger.info(f"Looking up DKIM record for: {domain} with selector: {selector}")
    return await query_dkim_record(domain, selector, use_cache)


@mcp.tool()
async def dns_lookup_txt(domain: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Look up TXT (Text) records for a domain.

    TXT records contain various text information including SPF, DKIM, DMARC, domain verification, etc.

    Args:
        domain: Domain to query (e.g., 'gmail.com')
        use_cache: Use cached results if available (default: True)

    Returns:
        All TXT records for the domain
    """
    logger.info(f"Looking up TXT records for: {domain}")
    return await query_dns_records(domain, "TXT", use_cache)


@mcp.tool()
async def dns_lookup_records(
    domain: str, record_type: str = "A", use_cache: bool = True
) -> Dict[str, Any]:
    """
    Look up DNS records of any type for a domain.

    Supports common record types: A, AAAA, CNAME, NS, SOA, PTR, SRV, CAA, etc.

    Args:
        domain: Domain to query (e.g., 'example.com')
        record_type: DNS record type to query (default: 'A'). Common types: A, AAAA, CNAME, NS, SOA, TXT, MX
        use_cache: Use cached results if available (default: True)

    Returns:
        DNS records of the specified type
    """
    logger.info(f"Looking up {record_type} records for: {domain}")
    return await query_dns_records(domain, record_type.upper(), use_cache)


@mcp.tool()
async def dns_lookup_dmarc(domain: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Look up DMARC (Domain-based Message Authentication) policy for a domain.

    DMARC records specify how to handle emails that fail SPF or DKIM checks.

    Args:
        domain: Domain to query (e.g., 'gmail.com')
        use_cache: Use cached results if available (default: True)

    Returns:
        DMARC policy record
    """
    dmarc_domain = f"_dmarc.{clean_domain(domain)}"
    logger.info(f"Looking up DMARC record for: {domain}")

    txt_result = await query_dns_records(dmarc_domain, "TXT", use_cache)

    if "error" in txt_result:
        return {
            "error": f"No DMARC record found for {domain}",
            "domain": domain,
            "dmarc_domain": dmarc_domain,
            "record_type": "DMARC",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Extract DMARC records (they start with v=DMARC1)
    dmarc_records = []
    for record in txt_result.get("records", []):
        value = record.get("value", "").strip('"')
        if value.startswith("v=DMARC1"):
            dmarc_records.append(value)

    result = {
        "domain": domain,
        "dmarc_domain": dmarc_domain,
        "record_type": "DMARC",
        "dmarc_records": dmarc_records,
        "record_count": len(dmarc_records),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cached": txt_result.get("cached", False),
    }

    if not dmarc_records:
        result["error"] = f"No DMARC record found for {domain}"

    return result


@mcp.tool()
async def dns_clear_cache() -> Dict[str, Any]:
    """
    Clear all cached DNS records.

    Use this to force fresh DNS queries or when you suspect cached data is stale.

    Returns:
        Status message confirming cache clearance
    """
    logger.info("Clearing DNS cache")
    dns_cache.clear()
    return {
        "status": "success",
        "message": "DNS cache cleared successfully",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def setup_domain_lookup_mcp_server() -> Dict[str, Any]:
    """
    Get helpful information about using the Domain Lookup MCP Server.

    Returns:
        Guide and examples for using the domain lookup tools effectively
    """
    return {
        "server_info": {
            "name": "Domain Lookup MCP Server",
            "version": "2.0.0",
            "description": "Provides efficient domain lookup tools for WHOIS and DNS information with intelligent caching",
        },
        "whois_tools": [
            {
                "name": "whois_domain",
                "description": "Look up WHOIS information for a single domain",
                "example": "whois_domain('example.com')",
                "use_case": "Check if a domain is registered, find registrar info",
            },
            {
                "name": "whois_domains",
                "description": "Look up WHOIS information for multiple domains efficiently",
                "example": "whois_domains(['example.com', 'test.org', 'demo.net'])",
                "use_case": "Bulk domain availability checking",
            },
            {
                "name": "whois_tld",
                "description": "Look up WHOIS information for a Top Level Domain",
                "example": "whois_tld('com')",
                "use_case": "Get information about TLD registry and policies",
            },
            {
                "name": "whois_ip",
                "description": "Look up WHOIS information for an IP address",
                "example": "whois_ip('8.8.8.8')",
                "use_case": "Find ISP, organization, and location info for an IP",
            },
            {
                "name": "whois_asn",
                "description": "Look up WHOIS information for an Autonomous System Number",
                "example": "whois_asn('AS15169')",
                "use_case": "Get organization info for network infrastructure",
            },
        ],
        "dns_tools": [
            {
                "name": "dns_lookup_mx",
                "description": "Look up MX (Mail Exchange) records",
                "example": "dns_lookup_mx('gmail.com')",
                "use_case": "Find mail servers for a domain",
            },
            {
                "name": "dns_lookup_spf",
                "description": "Look up SPF (Sender Policy Framework) records",
                "example": "dns_lookup_spf('gmail.com')",
                "use_case": "Check which servers are authorized to send email",
            },
            {
                "name": "dns_lookup_dkim",
                "description": "Look up DKIM records with a selector",
                "example": "dns_lookup_dkim('gmail.com', selector='google')",
                "use_case": "Verify email authentication configuration",
            },
            {
                "name": "dns_lookup_dmarc",
                "description": "Look up DMARC policy records",
                "example": "dns_lookup_dmarc('gmail.com')",
                "use_case": "Check email authentication and reporting policies",
            },
            {
                "name": "dns_lookup_txt",
                "description": "Look up all TXT records",
                "example": "dns_lookup_txt('example.com')",
                "use_case": "Find domain verification, SPF, and other text records",
            },
            {
                "name": "dns_lookup_records",
                "description": "Look up any DNS record type",
                "example": "dns_lookup_records('example.com', record_type='A')",
                "use_case": "Query A, AAAA, CNAME, NS, SOA, or any other DNS record type",
            },
            {
                "name": "dns_clear_cache",
                "description": "Clear all cached DNS records",
                "example": "dns_clear_cache()",
                "use_case": "Force fresh DNS queries when cached data may be stale",
            },
        ],
        "caching_info": {
            "description": "DNS queries are automatically cached to reduce load on DNS servers",
            "default_ttl": "24 hours or DNS record TTL (whichever is appropriate)",
            "cache_location": str(CACHE_DIR),
            "benefits": [
                "Faster response times for repeated queries",
                "Reduced load on upstream DNS servers",
                "Respectful of DNS infrastructure",
            ],
        },
        "best_practices": [
            "Use whois_domains for bulk lookups to respect rate limits",
            "DNS queries are cached automatically - use dns_clear_cache() to force refresh",
            "For DKIM lookups, you need to know the selector (common: 'default', 'google', 's1')",
            "Results include 'cached' field to indicate if data came from cache",
            "All timestamps are in UTC ISO format",
            "Error messages provide actionable guidance for troubleshooting",
        ],
        "common_use_cases": [
            "Domain availability checking for registration",
            "Email server and authentication configuration analysis",
            "DNS record auditing and validation",
            "Security investigations and threat intelligence",
            "Domain portfolio management and monitoring",
            "Email deliverability troubleshooting",
        ],
    }


if __name__ == "__main__":
    mcp.run()
