# AtomToPubsub v2.0

A modern Python refactor of the original AtomToPubsub script that parses Atom/RSS feeds and publishes them to XMPP Pubsub nodes.

## Features

- **Modern Python 3.10+**: Type hints, dataclasses, and async/await
- **Type-safe configuration**: Uses Pydantic for validation
- **Proper scheduling**: Async scheduler with cache management
- **Error handling**: Comprehensive logging and error recovery
- **Systemd integration**: Ready-to-use systemd service file
- **Testing**: pytest setup with async support

## Installation

```bash
# Clone and install
cd atomtopubsub-refactor
pip install -e .
```

## Configuration

Create a configuration file:

```bash
cp config.example.json /etc/atomtopubsub/config.json
nano /etc/atomtopubsub/config.json
```

Example configuration:

```json
{
  "jid": "user@xmpp-server.tld",
  "secret": "your-xmpp-password",
  "resource": "atomtopubsub",
  "refresh_time": 60,
  "log_level": "INFO",
  "feeds": {
    "MovimNews": {
      "url": "https://movim.eu/feed",
      "server": "pubsub.movim.eu"
    }
  }
}
```

## Running

### Command line

```bash
atomtopubsub --config /etc/atomtopubsub/config.json
```

### Environment variables

```bash
export XMPP_JID="user@server.tld"
export XMPP_SECRET="password"
atomtopubsub --refresh 60
```

### As a systemd service

```bash
# Install service
sudo cp atomtopubsub.service /etc/systemd/system/
sudo cp config.example.json /etc/atomtopubsub/config.json
sudo nano /etc/atomtopubsub/config.json

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable atomtopubsub
sudo systemctl start atomtopubsub
```

## Development

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/atomtopubsub

# Code formatting
ruff check src/atomtopubsub
ruff format src/atomtopubsub
```

### Project Structure

```
atomtopubsub/
├── pyproject.toml          # Project configuration
├── src/atomtopubsub/
│   ├── __init__.py
│   ├── __main__.py         # Entry point
│   ├── config.py           # Configuration (Pydantic)
│   ├── feedparser.py       # Feed parsing logic
│   ├── scheduler.py        # Feed scheduling
│   └── xmpp.py             # XMPP Pubsub client
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   └── test_feedparser.py
├── atomtopubsub.service    # Systemd service file
└── config.example.json
```

## Dependencies

- `feedparser` - Atom/RSS feed parsing
- `slixmpp` - XMPP client
- `apscheduler` - Async scheduling
- `beautifulsoup4` - HTML parsing
- `pydantic` - Configuration validation
- `python-dotenv` - Environment variable support

## License

MIT License - See LICENSE file for details.

## Original

Based on [atomtopubsub](https://github.com/edhelas/atomtopubsub) by edhelas.
