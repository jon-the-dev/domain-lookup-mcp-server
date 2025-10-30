# Domain Lookup MCP Server

An efficient Model Context Protocol (MCP) server that provides domain lookup tools for WHOIS and DNS information. Designed specifically for LLM workflows with optimized performance, intelligent caching, and comprehensive error handling.

## Features

- **Efficient Bulk Operations**: Handle multiple domain lookups with rate limiting and concurrency control
- **Intelligent Caching**: File-based DNS cache with TTL support to minimize upstream DNS server load
- **Comprehensive Error Handling**: Actionable error messages to guide AI agents
- **Email Authentication Tools**: SPF, DKIM, DMARC record lookups for email security analysis
- **Registration Status Analysis**: Quick boolean checks for domain availability
- **Multiple Query Types**: Support for domains, IPs, ASNs, TLDs, and all DNS record types
- **Structured Output**: Clean JSON responses with parsed fields and raw output
- **Rate Limiting**: Respectful WHOIS server usage with built-in delays

## Tools

### WHOIS Tools
- **`whois_domain`** - Look up WHOIS information for a single domain with registration analysis
- **`whois_domains`** - Efficiently look up multiple domains with summary statistics
- **`whois_tld`** - Look up WHOIS information about Top Level Domains (TLDs)
- **`whois_ip`** - Look up WHOIS information for IP addresses (IPv4/IPv6)
- **`whois_asn`** - Look up WHOIS information for Autonomous System Numbers (ASNs)

### DNS Record Tools
- **`dns_lookup_mx`** - Look up MX (Mail Exchange) records for email servers
- **`dns_lookup_spf`** - Look up SPF (Sender Policy Framework) records for email authentication
- **`dns_lookup_dkim`** - Look up DKIM records with a specific selector
- **`dns_lookup_dmarc`** - Look up DMARC policy records for email authentication
- **`dns_lookup_txt`** - Look up all TXT records (includes SPF, verification codes, etc.)
- **`dns_lookup_records`** - Look up any DNS record type (A, AAAA, CNAME, NS, SOA, etc.)
- **`dns_clear_cache`** - Clear all cached DNS records to force fresh queries

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

### WHOIS Lookups

#### Single Domain Lookup
```python
# Check if a domain is registered
result = await whois_domain("example.com")
print(f"Registered: {result['is_registered']}")
print(f"Registrar: {result['parsed_fields'].get('registrar')}")
```

#### Bulk Domain Analysis
```python
# Check multiple domains at once
domains = ["example.com", "available-domain-123.com", "google.com"]
result = await whois_domains(domains)
print(f"Total: {result['summary']['total_domains']}")
print(f"Registered: {result['summary']['registered_domains']}")
print(f"Available: {result['summary']['available_domains']}")
```

#### IP and Network Analysis
```python
# Look up IP information
ip_result = await whois_ip("8.8.8.8")
print(f"Organization: {ip_result['parsed_fields'].get('org')}")

# Look up ASN information
asn_result = await whois_asn("AS15169")
print(f"ASN Owner: {asn_result['parsed_fields'].get('as-name')}")
```

### DNS Record Lookups

#### Email Server Configuration
```python
# Look up MX records to find mail servers
mx_result = await dns_lookup_mx("gmail.com")
for record in mx_result['records']:
    print(f"Mail server: {record['exchange']} (priority: {record['preference']})")
```

#### Email Authentication Records
```python
# Check SPF record
spf_result = await dns_lookup_spf("gmail.com")
print(f"SPF record: {spf_result['spf_records']}")

# Check DKIM record (requires knowing the selector)
dkim_result = await dns_lookup_dkim("gmail.com", selector="google")
print(f"DKIM record: {dkim_result['dkim_records']}")

# Check DMARC policy
dmarc_result = await dns_lookup_dmarc("gmail.com")
print(f"DMARC policy: {dmarc_result['dmarc_records']}")
```

#### General DNS Queries
```python
# Look up A records (IPv4 addresses)
a_result = await dns_lookup_records("example.com", record_type="A")
print(f"IP addresses: {[r['value'] for r in a_result['records']]}")

# Look up AAAA records (IPv6 addresses)
aaaa_result = await dns_lookup_records("example.com", record_type="AAAA")

# Look up nameservers
ns_result = await dns_lookup_records("example.com", record_type="NS")

# Look up all TXT records
txt_result = await dns_lookup_txt("example.com")
```

#### Cache Management
```python
# Clear cache to force fresh DNS queries
await dns_clear_cache()
```

## API Response Format

### WHOIS Response Format

WHOIS tools return structured JSON responses with:

- **`query`** - The original query string
- **`timestamp`** - ISO 8601 timestamp of the lookup
- **`raw_output`** - Complete WHOIS response text
- **`parsed_fields`** - Key-value pairs extracted from WHOIS data
- **`is_registered`** - Boolean registration status (domain queries only)
- **`analysis`** - Additional analysis metadata
- **`error`** - Error message if the lookup failed

#### Example WHOIS Response
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

### DNS Response Format

DNS tools return structured JSON responses with:

- **`domain`** - The queried domain
- **`record_type`** - Type of DNS record (MX, TXT, A, etc.)
- **`records`** - Array of DNS records found
- **`record_count`** - Number of records returned
- **`ttl`** - Time To Live from DNS response (in seconds)
- **`timestamp`** - ISO 8601 timestamp of the lookup
- **`cached`** - Boolean indicating if result came from cache
- **`error`** - Error message if the lookup failed

#### Example DNS Response
```json
{
  "domain": "gmail.com",
  "record_type": "MX",
  "records": [
    {
      "preference": 5,
      "exchange": "gmail-smtp-in.l.google.com.",
      "value": "5 gmail-smtp-in.l.google.com."
    },
    {
      "preference": 10,
      "exchange": "alt1.gmail-smtp-in.l.google.com.",
      "value": "10 alt1.gmail-smtp-in.l.google.com."
    }
  ],
  "record_count": 2,
  "ttl": 3600,
  "timestamp": "2024-01-20T10:30:00Z",
  "cached": false
}
```

## Performance Considerations

### WHOIS Queries
- **Rate Limiting**: Built-in delays between requests to respect WHOIS servers
- **Concurrency**: Limited to 5 concurrent requests for bulk operations
- **Timeouts**: 10-second timeout per WHOIS query to prevent hanging
- **Error Recovery**: Graceful handling of network issues and invalid queries

### DNS Queries with Caching
- **Intelligent Caching**: DNS records are automatically cached to reduce load on DNS servers
- **TTL Respect**: Cache duration respects DNS record TTL values (or 24 hours default)
- **Cache Location**: `~/.cache/domain-lookup-mcp/` (configurable)
- **Cache Benefits**:
  - Faster response times for repeated queries
  - Reduced load on upstream DNS servers
  - Respectful of DNS infrastructure
- **Cache Control**: Use `dns_clear_cache()` to force fresh queries when needed
- **Timeouts**: 5-second timeout per DNS query to prevent hanging

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
