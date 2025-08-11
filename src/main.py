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
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone

import fastmcp


# Configure logging to stderr (critical for MCP servers)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("domain-lookup-mcp")

# Create the MCP server
mcp = fastmcp.FastMCP("Domain Lookup MCP Server")


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
            'whois', query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "error": f"WHOIS query timed out after {timeout} seconds",
                "query": query,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='ignore').strip()
            return {
                "error": f"WHOIS command failed: {error_msg or 'Unknown error'}",
                "query": query,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        raw_output = stdout.decode('utf-8', errors='ignore')
        
        # Parse basic information from whois output
        lines = raw_output.split('\n')
        parsed_data = {
            "query": query,
            "raw_output": raw_output,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "parsed_fields": {}
        }
        
        # Extract common fields
        for line in lines:
            line = line.strip()
            if ':' in line and not line.startswith('%') and not line.startswith('#'):
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                if value and key:
                    if key in parsed_data["parsed_fields"]:
                        # Handle multiple values for same field
                        if isinstance(parsed_data["parsed_fields"][key], list):
                            parsed_data["parsed_fields"][key].append(value)
                        else:
                            parsed_data["parsed_fields"][key] = [parsed_data["parsed_fields"][key], value]
                    else:
                        parsed_data["parsed_fields"][key] = value
        
        return parsed_data
        
    except Exception as e:
        logger.error(f"Error running whois for {query}: {str(e)}")
        return {
            "error": f"Internal error: {str(e)}",
            "query": query,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def resolve_domain_ip(domain: str) -> Optional[str]:
    """Resolve domain to IP address."""
    try:
        # Remove protocol if present
        domain = domain.replace('http://', '').replace('https://', '')
        # Remove path if present
        domain = domain.split('/')[0]
        # Remove port if present
        domain = domain.split(':')[0]
        
        ip = socket.gethostbyname(domain)
        return ip
    except Exception as e:
        logger.debug(f"Could not resolve {domain} to IP: {str(e)}")
        return None


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
    domain = domain.replace('http://', '').replace('https://', '')
    # Remove path if present
    domain = domain.split('/')[0]
    # Remove port if present
    domain = domain.split(':')[0]
    
    logger.info(f"Looking up WHOIS for domain: {domain}")
    
    result = await run_whois_command(domain)
    
    # Add registration status analysis
    if "error" not in result:
        raw_output = result.get("raw_output", "").lower()
        parsed_fields = result.get("parsed_fields", {})
        
        # Determine if domain is registered
        is_registered = True
        if any(phrase in raw_output for phrase in [
            "no match", "not found", "no data found", "status: available",
            "no matching record", "not registered"
        ]):
            is_registered = False
        
        result["is_registered"] = is_registered
        result["analysis"] = {
            "registered": is_registered,
            "has_registrar": bool(parsed_fields.get("registrar")),
            "has_creation_date": bool(parsed_fields.get("creation_date") or parsed_fields.get("created")),
            "has_expiry_date": bool(parsed_fields.get("expiry_date") or parsed_fields.get("expires"))
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
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
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
    if not tld.startswith('.'):
        tld = '.' + tld
    
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
async def setup_domain_lookup_mcp_server() -> Dict[str, Any]:
    """
    Get helpful information about using the Domain Lookup MCP Server.
    
    Returns:
        Guide and examples for using the domain lookup tools effectively
    """
    return {
        "server_info": {
            "name": "Domain Lookup MCP Server",
            "version": "1.0.0",
            "description": "Provides efficient domain lookup tools for WHOIS and DNS information"
        },
        "available_tools": [
            {
                "name": "whois_domain",
                "description": "Look up WHOIS information for a single domain",
                "example": "whois_domain('example.com')",
                "use_case": "Check if a domain is registered, find registrar info"
            },
            {
                "name": "whois_domains",
                "description": "Look up WHOIS information for multiple domains efficiently",
                "example": "whois_domains(['example.com', 'test.org', 'demo.net'])",
                "use_case": "Bulk domain availability checking"
            },
            {
                "name": "whois_tld",
                "description": "Look up WHOIS information for a Top Level Domain",
                "example": "whois_tld('com')",
                "use_case": "Get information about TLD registry and policies"
            },
            {
                "name": "whois_ip",
                "description": "Look up WHOIS information for an IP address",
                "example": "whois_ip('8.8.8.8')",
                "use_case": "Find ISP, organization, and location info for an IP"
            },
            {
                "name": "whois_asn",
                "description": "Look up WHOIS information for an Autonomous System Number",
                "example": "whois_asn('AS15169')",
                "use_case": "Get organization info for network infrastructure"
            }
        ],
        "best_practices": [
            "Use whois_domains for bulk lookups to respect rate limits",
            "Results include 'is_registered' boolean for quick domain availability checks",
            "Raw WHOIS output is included for detailed analysis when needed",
            "All timestamps are in UTC ISO format",
            "Error handling provides actionable error messages for troubleshooting"
        ],
        "common_use_cases": [
            "Domain availability checking for registration",
            "Investigating domain ownership and registration history",
            "IP address and network infrastructure analysis",
            "Security investigations and threat intelligence",
            "Domain portfolio management and monitoring"
        ]
    }


if __name__ == "__main__":
    mcp.run()