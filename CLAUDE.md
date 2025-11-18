# Domain Lookup MCP Server - Development Guide

## Project Overview

This is a Model Context Protocol (MCP) server that provides domain lookup capabilities through WHOIS and DNS query tools. Built with FastMCP and Python 3.10+, it's designed specifically for AI agent workflows with intelligent caching, rate limiting, and comprehensive error handling.

## Architecture

### Core Components

- **MCP Server**: Built using `fastmcp` framework (v2.13.0+)
- **WHOIS Integration**: Uses system `whois` command via subprocess
- **DNS Resolution**: Uses `dnspython` library for DNS queries
- **Caching Layer**: File-based DNS cache with TTL support at `~/.cache/domain-lookup-mcp/`
- **Logging**: All logs to stderr (never stdout) to prevent JSON-RPC corruption

### Tool Categories

1. **WHOIS Tools** (5 tools):
   - `whois_domain` - Single domain lookup with registration analysis
   - `whois_domains` - Bulk domain lookups with concurrency control
   - `whois_tld` - Top Level Domain information
   - `whois_ip` - IP address ownership information
   - `whois_asn` - Autonomous System Number details

2. **DNS Record Tools** (7 tools):
   - `dns_lookup_mx` - Mail exchange records
   - `dns_lookup_spf` - Sender Policy Framework records
   - `dns_lookup_dkim` - DomainKeys Identified Mail records
   - `dns_lookup_dmarc` - DMARC policy records
   - `dns_lookup_txt` - All TXT records
   - `dns_lookup_records` - Any DNS record type (A, AAAA, NS, etc.)
   - `dns_clear_cache` - Cache management

3. **Helper Tools** (1 tool):
   - `setup_domain_lookup_mcp_server` - Usage guide and examples

## Development Guidelines

### Code Style

- **Formatting**: Black with 100 character line length
- **Type Hints**: Required on all function signatures (mypy strict mode)
- **Async/Await**: All tool functions are async
- **Error Handling**: Always provide actionable error messages for AI agents
- **Logging**: Use `logger` instance, never print to stdout

### Key Patterns

#### 1. Stateless Tool Design
Each tool call is self-contained. No server-level state beyond the cache.

```python
@mcp.tool()
async def whois_domain(domain: str) -> Dict[str, Any]:
    # Clean input
    domain = clean_domain(domain)
    # Execute query
    result = await run_whois_command(domain)
    # Return structured response
    return result
```

#### 2. Intelligent Caching
DNS queries use file-based cache with TTL from DNS records:

```python
# Check cache first
if use_cache:
    cached = dns_cache.get(domain, record_type)
    if cached:
        return cached

# Query and cache result
result = await query_dns_records(domain, "A")
dns_cache.set(domain, "A", result, ttl=timedelta(seconds=min_ttl))
```

#### 3. Input Sanitization
Always clean domain inputs to handle various formats:

```python
def clean_domain(domain: str) -> str:
    domain = domain.strip().lower()
    domain = domain.replace('http://', '').replace('https://', '')
    domain = domain.split('/')[0]  # Remove path
    domain = domain.split(':')[0]  # Remove port
    return domain
```

#### 4. Actionable Error Messages
Design errors to guide AI agents toward resolution:

```python
return {
    "error": f"No DKIM record found for selector '{selector}' at {domain}. Common selectors: default, google, s1, s2, k1",
    "domain": domain,
    "selector": selector
}
```

#### 5. Structured Responses
All responses follow consistent structure:

```python
{
    "domain": "example.com",
    "record_type": "MX",
    "records": [...],
    "record_count": 2,
    "ttl": 3600,
    "timestamp": "2024-01-20T10:30:00Z",
    "cached": false,
    "error": "optional error message"
}
```

### Concurrency and Rate Limiting

#### WHOIS Queries
- **Rate Limiting**: 0.1s delay between requests
- **Concurrency**: Limited to 5 simultaneous requests via Semaphore
- **Timeout**: 10 second timeout per query

```python
semaphore = asyncio.Semaphore(5)
async with semaphore:
    result = await whois_domain(domain)
    await asyncio.sleep(0.1)  # Rate limiting
```

#### DNS Queries
- **Timeout**: 5 second timeout per query
- **Nameservers**: Always use public DNS (8.8.8.8, 8.8.4.4, 1.1.1.1)
- **Caching**: Automatic with DNS TTL or 24-hour default

## Testing and Validation

### Running Tests
```bash
poetry run python test_server.py
```

### Testing Individual Tools
The test suite validates:
- WHOIS domain lookups (registered and unregistered)
- WHOIS bulk operations
- DNS record queries (MX, TXT, A, etc.)
- Email authentication records (SPF, DKIM, DMARC)
- Cache functionality
- Error handling

### Manual Testing
```bash
# Start server locally
poetry run python src/main.py

# Test with MCP client or inspector
poetry install
poetry run python test_server.py
```

## Common Development Tasks

### Adding a New DNS Record Type Tool

1. Create tool function with `@mcp.tool()` decorator
2. Use `query_dns_records()` helper with appropriate record type
3. Add special field parsing if needed (like MX preference)
4. Document in tool docstring for AI agent understanding
5. Add to `setup_domain_lookup_mcp_server()` examples

Example:
```python
@mcp.tool()
async def dns_lookup_caa(domain: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Look up CAA (Certification Authority Authorization) records.

    CAA records specify which certificate authorities can issue certificates.

    Args:
        domain: Domain to query
        use_cache: Use cached results if available

    Returns:
        CAA records for the domain
    """
    logger.info(f"Looking up CAA records for: {domain}")
    return await query_dns_records(domain, "CAA", use_cache)
```

### Adding a New WHOIS Tool

1. Create async tool function
2. Use `run_whois_command()` helper
3. Add custom parsing if needed
4. Include analysis fields for AI agents
5. Add appropriate error handling

### Modifying Cache Behavior

Cache configuration is in `DNSCache` class:
- Default TTL: `DEFAULT_CACHE_TTL = timedelta(hours=24)`
- Cache directory: `CACHE_DIR = Path.home() / ".cache" / "domain-lookup-mcp"`
- Cache keys: SHA256 hash of `domain:record_type:extra`

### Improving Error Messages

Error messages should:
1. State what went wrong clearly
2. Provide context (domain, record type, etc.)
3. Suggest solutions or common selectors/options
4. Include timestamp for debugging

## Security Considerations

### Input Validation
- All domain inputs sanitized via `clean_domain()`
- No shell command injection risk (subprocess with args list)
- TLD inputs normalized and validated
- IP/ASN inputs passed directly to whois (validated by command)

### DNS Security
- Always use trusted public DNS servers
- Timeout protection on all queries
- No recursive resolution beyond dnspython library
- Cache prevents DNS amplification attacks

### Logging Security
- No sensitive data logged
- All logs to stderr only
- Log level INFO by default
- Error messages don't expose internals

## Performance Optimization

### DNS Caching Strategy
- File-based cache survives server restarts
- TTL from DNS records prevents stale data
- Cache hit reduces query time by ~95%
- Cache directory automatically created

### WHOIS Optimization
- Bulk operations use controlled concurrency
- Rate limiting prevents server blocks
- Timeout prevents hanging on slow servers
- Minimal parsing for faster responses

### Memory Management
- No in-memory caches (file-based only)
- Subprocess cleanup automatic
- No persistent connections
- Stateless design prevents leaks

## Dependencies

### Production
- `python = "^3.10"` - Minimum Python version
- `fastmcp = "^2.13.0"` - MCP framework
- `dnspython = "^2.4.0"` - DNS resolution

### Development
- `pytest = "^7.0.0"` - Test framework
- `pytest-asyncio = "^0.21.0"` - Async test support
- `black = "^24.3.0"` - Code formatting
- `mypy = "^1.0.0"` - Type checking

### System Requirements
- `whois` command-line tool (pre-installed on most Unix systems)
- Internet connectivity for DNS/WHOIS queries
- File system access for cache directory

## MCP Integration

### Configuration Example
```json
{
  "mcpServers": {
    "domain-lookup": {
      "command": "poetry",
      "args": ["run", "python", "src/main.py"],
      "cwd": "/path/to/domain-lookup-mcp-server",
      "env": {
        "PYTHONPATH": "."
      }
    }
  }
}
```

### Server Capabilities
- **Tools Only**: This server provides tools, no resources or prompts
- **Stateless**: Each request is independent
- **Stdio Transport**: Standard MCP stdio communication
- **No Authentication**: Local execution only

## Troubleshooting

### Common Issues

**DNS queries fail with "No nameservers configured"**
- Server explicitly sets public DNS servers (8.8.8.8, etc.)
- Uses `configure=False` for restricted environments

**WHOIS timeout errors**
- 10 second timeout is intentional for unresponsive servers
- Some WHOIS servers are slow or rate-limited
- Retry with delay if needed

**Cache not clearing**
- Check file permissions on `~/.cache/domain-lookup-mcp/`
- Verify cache directory exists and is writable

**Import errors**
- Run `poetry install` to ensure dependencies installed
- Check Python version is 3.10+
- Verify PYTHONPATH if running outside poetry

## Best Practices for Contributors

1. **Always async**: New tools must be async functions
2. **Type everything**: Use comprehensive type hints
3. **Test thoroughly**: Add tests for new functionality
4. **Document for agents**: Docstrings should guide AI usage
5. **Error messages matter**: Make them actionable
6. **Log to stderr**: Never print or log to stdout
7. **Cache wisely**: Use cache for DNS, not WHOIS
8. **Respect rate limits**: Add delays for external services
9. **Clean inputs**: Always sanitize user-provided data
10. **Structured responses**: Follow established JSON formats

## Version History

- **v2.0.0**: Added DNS caching, email auth tools, improved error handling
- **v1.0.0**: Initial release with WHOIS and basic DNS tools

## Support and Contributions

This MCP server is designed to be:
- **Efficient**: Minimal overhead, intelligent caching
- **Reliable**: Comprehensive error handling, timeouts
- **Agent-friendly**: Clear responses, actionable errors
- **Maintainable**: Clean code, strong typing, good tests

When contributing, prioritize the AI agent experience above all else.
