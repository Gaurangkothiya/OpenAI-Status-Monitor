"""
OpenAI Status Page Monitor
Automatically tracks and logs service updates from the OpenAI Status Page.
Uses efficient polling with change detection to minimize API calls.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import hashlib
import aiohttp
from dataclasses import dataclass, asdict


@dataclass
class ComponentStatus:
    """Represents the status of a single component"""

    id: str
    name: str
    status: str
    updated_at: str
    position: int


@dataclass
class IncidentUpdate:
    """Represents an update to an incident"""

    id: str
    body: str
    created_at: str
    display_at: str
    status: str
    incident_id: str


@dataclass
class Incident:
    """Represents an incident with its updates"""

    id: str
    name: str
    status: str
    created_at: str
    updated_at: str
    resolved_at: Optional[str]
    impact: str
    updates: List[IncidentUpdate]


class OpenAIStatusMonitor:
    """Efficient event-based OpenAI Status Page monitor"""

    BASE_URL = "https://status.openai.com"
    SUMMARY_ENDPOINT = "/api/v2/summary.json"
    INCIDENTS_ENDPOINT = "/api/v2/incidents.json"

    def __init__(self, poll_interval: int = 30):
        self.poll_interval = poll_interval
        self.session: Optional[aiohttp.ClientSession] = None
        self.etags: Dict[str, str] = {}
        self.last_known_state: Dict[str, str] = {}
        self.processed_incident_updates: Set[str] = set()

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    def _get_content_hash(self, data: dict) -> str:
        """Generate hash of content for change detection"""
        content_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(content_str.encode()).hexdigest()

    async def _fetch_with_etag(self, endpoint: str) -> Optional[dict]:
        """Fetch data with ETag support for efficient polling"""
        url = self.BASE_URL + endpoint
        headers = {}

        # Add If-None-Match header if we have an ETag
        if endpoint in self.etags:
            headers["If-None-Match"] = self.etags[endpoint]

        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 304:
                    # No changes since last request
                    return None

                if response.status == 200:
                    # Store new ETag if available
                    etag = response.headers.get("ETag")
                    if etag:
                        self.etags[endpoint] = etag.strip('"')

                    return await response.json()
                else:
                    self.logger.warning(f"HTTP {response.status} for {endpoint}")
                    return None

        except aiohttp.ClientError as e:
            self.logger.error(f"Network error fetching {endpoint}: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error for {endpoint}: {e}")
            return None

    def _parse_components(self, data: dict) -> List[ComponentStatus]:
        """Parse components from summary data"""
        components = []
        for comp_data in data.get("components", []):
            components.append(
                ComponentStatus(
                    id=comp_data["id"],
                    name=comp_data["name"],
                    status=comp_data["status"],
                    updated_at=comp_data["updated_at"],
                    position=comp_data["position"],
                )
            )
        return components

    def _parse_incidents(self, data: dict) -> List[Incident]:
        """Parse incidents from incidents data"""
        incidents = []
        for inc_data in data.get("incidents", []):
            updates = []
            for update_data in inc_data.get("incident_updates", []):
                updates.append(
                    IncidentUpdate(
                        id=update_data["id"],
                        body=update_data["body"],
                        created_at=update_data["created_at"],
                        display_at=update_data["display_at"],
                        status=update_data["status"],
                        incident_id=update_data["incident_id"],
                    )
                )

            incidents.append(
                Incident(
                    id=inc_data["id"],
                    name=inc_data["name"],
                    status=inc_data["status"],
                    created_at=inc_data["created_at"],
                    updated_at=inc_data["updated_at"],
                    resolved_at=inc_data.get("resolved_at"),
                    impact=inc_data["impact"],
                    updates=updates,
                )
            )
        return incidents

    def _detect_component_changes(self, components: List[ComponentStatus]) -> None:
        """Detect and report component status changes"""
        for component in components:
            state_key = f"component_{component.id}"
            current_state = f"{component.name}:{component.status}"

            if state_key not in self.last_known_state:
                # New component detected
                self.last_known_state[state_key] = current_state
                self._log_component_event(component, "Initial Status")
            elif self.last_known_state[state_key] != current_state:
                # Component status changed
                old_state = self.last_known_state[state_key]
                self.last_known_state[state_key] = current_state
                self._log_component_event(component, f"Status changed from {old_state}")

    def _detect_incident_updates(self, incidents: List[Incident]) -> None:
        """Detect and report new incident updates"""
        for incident in incidents:
            for update in incident.updates:
                if update.id not in self.processed_incident_updates:
                    self.processed_incident_updates.add(update.id)
                    self._log_incident_event(incident, update)

    def _log_component_event(self, component: ComponentStatus, event_type: str) -> None:
        """Log component status events"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        status_emoji = self._get_status_emoji(component.status)

        print(
            f"[{timestamp}] Product: {component.name} Status: {component.status} {status_emoji} ({event_type})"
        )

    def _log_incident_event(self, incident: Incident, update: IncidentUpdate) -> None:
        """Log incident update events"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        status_emoji = self._get_status_emoji(update.status)
        impact_emoji = self._get_impact_emoji(incident.impact)

        # Extract affected products from incident name
        affected_products = self._extract_products_from_incident(incident.name)

        print(
            f"[{timestamp}] Product: {affected_products} Status: {update.status} {status_emoji} {impact_emoji}"
        )
        print(f"    Incident: {incident.name}")
        if update.body:
            print(f"    Update: {update.body}")
        print(f"    Impact: {incident.impact}")
        print()

    def _get_status_emoji(self, status: str) -> str:
        """Get emoji for status"""
        status_emojis = {
            "operational": "✅",
            "degraded_performance": "⚠️",
            "partial_outage": "🟡",
            "major_outage": "🔴",
            "under_maintenance": "🔧",
            "investigating": "🔍",
            "identified": "📍",
            "monitoring": "👁️",
            "resolved": "✅",
        }
        return status_emojis.get(status.lower(), "📋")

    def _get_impact_emoji(self, impact: str) -> str:
        """Get emoji for impact level"""
        impact_emojis = {"none": "", "minor": "🟡", "major": "🔴", "critical": "🚨"}
        return impact_emojis.get(impact.lower(), "")

    def _extract_products_from_incident(self, incident_name: str) -> str:
        """Extract affected products from incident name"""
        # Common OpenAI product keywords
        products = [
            "Chat Completions",
            "Responses",
            "Batch",
            "Files",
            "Fine-tuning",
            "Embeddings",
            "Audio",
            "Images",
            "Realtime",
            "ChatGPT",
            "Sora",
            "Vector stores",
            "Moderation",
            "Assistants",
            "Codex",
            "Login",
            "File uploads",
            "Compliance API",
        ]

        found_products = []
        incident_lower = incident_name.lower()

        for product in products:
            if product.lower() in incident_lower:
                found_products.append(product)

        return ", ".join(found_products) if found_products else "OpenAI Services"

    async def check_status_updates(self) -> None:
        """Check for status updates and log changes"""
        # Fetch summary for component status
        summary_data = await self._fetch_with_etag(self.SUMMARY_ENDPOINT)
        if summary_data:
            components = self._parse_components(summary_data)
            self._detect_component_changes(components)

        # Fetch incidents for incident updates
        incidents_data = await self._fetch_with_etag(self.INCIDENTS_ENDPOINT)
        if incidents_data:
            incidents = self._parse_incidents(incidents_data)
            self._detect_incident_updates(incidents)

    async def start_monitoring(self) -> None:
        """Start the monitoring loop"""
        self.logger.info(
            f"Starting OpenAI Status Monitor (polling every {self.poll_interval}s)"
        )
        print("🤖 OpenAI Status Monitor Started")
        print("=" * 50)

        try:
            while True:
                await self.check_status_updates()
                await asyncio.sleep(self.poll_interval)
        except KeyboardInterrupt:
            self.logger.info("Monitoring stopped by user")
            print("\n👋 Monitor stopped")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            print(f"\n❌ Error: {e}")


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="OpenAI Status Page Monitor")
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Polling interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--test", action="store_true", help="Run once and exit (for testing)"
    )

    args = parser.parse_args()

    async with OpenAIStatusMonitor(poll_interval=args.interval) as monitor:
        if args.test:
            print("🧪 Testing mode - running once...")
            await monitor.check_status_updates()
        else:
            await monitor.start_monitoring()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
