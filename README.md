# OpenAI Status Page Monitor

A lightweight Python application that automatically tracks and logs service updates from the OpenAI Status Page. The monitor detects new incidents, outages, or degradation updates related to any OpenAI API product and provides real-time console notifications.

## Features

- **Event-based Monitoring**: Efficient ETag-based polling to minimize network traffic
- **Real-time Detection**: Instantly detects component status changes and incident updates
- **Product-specific Notifications**: Identifies affected OpenAI services (Chat Completions, Responses, Batch, etc.)
- **Clean Console Output**: Simple, readable logging without unnecessary visual clutter
- **SSL Certificate Bypass**: Handles SSL verification issues for reliable connectivity
- **Modular Architecture**: Clean separation of concerns with dedicated modules

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd openai-status-monitor
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Monitoring

Start continuous monitoring with default 30-second intervals:

```bash
python main.py
```

### Test Mode

Run once and exit to verify connectivity:

```bash
python main.py --test
```

### Custom Polling Interval

Specify custom polling interval in seconds:

```bash
python main.py --interval 60
```

## Output Format

The monitor provides clear, timestamped console output:

```
[2025-11-16 17:26:35] Product: Chat Completions Status: operational (Initial Status)
[2025-11-16 17:26:35] Product: Login Status: investigating
    Incident: Current and new users facing login issue
    Update: We are investigating reports of users experiencing login issues
    Impact: major
```

## Architecture

The application is organized into three main modules:

- **`models.py`**: Data classes for status components and incidents
- **`monitor.py`**: Core monitoring logic with ETag-based efficient polling
- **`main.py`**: CLI interface and application entry point

## Supported OpenAI Services

The monitor automatically detects and reports status for these OpenAI products:

- Chat Completions
- Responses API
- Batch API
- Files API
- Fine-tuning
- Embeddings
- Audio API
- Images API
- Realtime API
- ChatGPT
- Sora
- Vector stores
- Moderation API
- Assistants API
- Codex
- Login services
- File uploads
- Compliance API

## Technical Details

- **Polling Method**: HTTP GET with ETag conditional requests
- **Endpoints**:
  - Summary: `https://status.openai.com/api/v2/summary.json`
  - Incidents: `https://status.openai.com/api/v2/incidents.json`
- **Change Detection**: Content hashing and state tracking
- **SSL Handling**: Configured to bypass certificate verification issues
- **Async Architecture**: Built on asyncio for efficient concurrent operations

## Requirements

- Python 3.7+
- aiohttp >= 3.8.0

## License

This project is provided as-is for monitoring OpenAI service status.

## Contributing

Feel free to submit issues or enhancement requests to improve the monitoring capabilities.
