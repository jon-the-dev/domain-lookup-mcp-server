# Domain Lookup MCP Server

An efficient Model Context Protocol (MCP) server that provides domain lookup tools for WHOIS and DNS information. Designed specifically for LLM workflows with optimized performance and comprehensive error handling.

## Features

- **Efficient Bulk Operations**: Handle multiple domain lookups with rate limiting and concurrency control
- **Comprehensive Error Handling**: Actionable error messages to guide AI agents
- **Registration Status Analysis**: Quick boolean checks for domain availability
- **Multiple Query Types**: Support for domains, IPs, ASNs, and TLDs
- **Structured Output**: Clean JSON responses with parsed fields and raw output
- **Rate Limiting**: Respectful WHOIS server usage with built-in delays

## Tools

### Core Domain Tools
- **`whois_domain`** - Look up WHOIS information for a single domain with registration analysis
- **`whois_domains`** - Efficiently look up multiple domains with summary statistics
- **`whois_tld`** - Look up WHOIS information about Top Level Domains (TLDs)
- **`whois_ip`** - Look up WHOIS information for IP addresses (IPv4/IPv6)
- **`whois_asn`** - Look up WHOIS information for Autonomous System Numbers (ASNs)

### Helper Tools
- **`setup_domain_lookup_mcp_server`** - Get usage information and examples for all tools

## Installation

### Prerequisites
- Python 3.10 or higher
- Poetry for dependency management
- `whois` command-line tool (usually pre-installed on Unix systems)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd domain-lookup-mcp-server
   ```

2. **Install dependencies:**
   ```bash
   poetry install
   ```

3. **Test the installation:**
   ```bash
   poetry run python test_server.py
   ```

## Configuration

### MCP Client Configuration

Add to your Claude Desktop config file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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

### Alternative: Direct Python Execution

```json
{
  "mcpServers": {
    "domain-lookup": {
      "command": "python",
      "args": ["src/main.py"],
      "cwd": "/path/to/domain-lookup-mcp-server"
    }
  }
}
```

## Usage Examples

### Single Domain Lookup
```python
# Check if a domain is registered
result = await whois_domain("example.com")
print(f"Registered: {result['is_registered']}")
print(f"Registrar: {result['parsed_fields'].get('registrar')}")
```

### Bulk Domain Analysis
```python
# Check multiple domains at once
domains = ["example.com", "available-domain-123.com", "google.com"]
result = await whois_domains(domains)
print(f"Total: {result['summary']['total_domains']}")
print(f"Registered: {result['summary']['registered_domains']}")
print(f"Available: {result['summary']['available_domains']}")
```

### IP and Network Analysis
```python
# Look up IP information
ip_result = await whois_ip("8.8.8.8")
print(f"Organization: {ip_result['parsed_fields'].get('org')}")

# Look up ASN information
asn_result = await whois_asn("AS15169")
print(f"ASN Owner: {asn_result['parsed_fields'].get('as-name')}")
```

## API Response Format

All tools return structured JSON responses with:

- **`query`** - The original query string
- **`timestamp`** - ISO 8601 timestamp of the lookup
- **`raw_output`** - Complete WHOIS response text
- **`parsed_fields`** - Key-value pairs extracted from WHOIS data
- **`is_registered`** - Boolean registration status (domain queries only)
- **`analysis`** - Additional analysis metadata
- **`error`** - Error message if the lookup failed

### Example Response
```json
{
  "query": "example.com",
  "timestamp": "2024-01-20T10:30:00Z",
  "is_registered": true,
  "parsed_fields": {
    "registrar": "Example Registrar Inc.",
    "creation_date": "1995-08-14T04:00:00Z",
    "expiry_date": "2024-08-13T04:00:00Z"
  },
  "analysis": {
    "registered": true,
    "has_registrar": true,
    "has_creation_date": true,
    "has_expiry_date": true
  },
  "raw_output": "Domain Name: EXAMPLE.COM\n..."
}
```

## Performance Considerations

- **Rate Limiting**: Built-in delays between requests to respect WHOIS servers
- **Concurrency**: Limited to 5 concurrent requests for bulk operations
- **Timeouts**: 10-second timeout per WHOIS query to prevent hanging
- **Error Recovery**: Graceful handling of network issues and invalid queries

## Development

### Running Tests
```bash
poetry run python test_server.py
```

### Code Formatting
```bash
poetry run black src/ test_server.py
```

### Type Checking
```bash
poetry run mypy src/
```

## Security Considerations

- Input validation prevents command injection
- No sensitive data logging
- Proper error handling without exposing internals
- Rate limiting prevents abuse

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
1. Check existing issues in the repository
2. Run the test suite to verify installation
3. Review the setup guide in this README
