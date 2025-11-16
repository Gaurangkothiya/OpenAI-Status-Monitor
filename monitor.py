import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import hashlib
import aiohttp

from models import ComponentStatus, Incident, IncidentUpdate


class OpenAIStatusMonitor:
    BASE_URL = "https://status.openai.com"
    SUMMARY_ENDPOINT = "/api/v2/summary.json"
    INCIDENTS_ENDPOINT = "/api/v2/incidents.json"

    def __init__(self, poll_interval: int = 30):
        self.poll_interval = poll_interval
        self.session: Optional[aiohttp.ClientSession] = None
        self.etags: Dict[str, str] = {}
        self.last_known_state: Dict[str, str] = {}
        self.processed_incident_updates: Set[str] = set()

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        import ssl

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_content_hash(self, data: dict) -> str:
        content_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(content_str.encode()).hexdigest()

    async def _fetch_with_etag(self, endpoint: str) -> Optional[dict]:
        url = self.BASE_URL + endpoint
        headers = {}

        if endpoint in self.etags:
            headers["If-None-Match"] = self.etags[endpoint]

        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 304:
                    return None

                if response.status == 200:
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
        for component in components:
            state_key = f"component_{component.id}"
            current_state = f"{component.name}:{component.status}"

            if state_key not in self.last_known_state:
                self.last_known_state[state_key] = current_state
                self._log_component_event(component, "Initial Status")
            elif self.last_known_state[state_key] != current_state:
                old_state = self.last_known_state[state_key]
                self.last_known_state[state_key] = current_state
                self._log_component_event(component, f"Status changed from {old_state}")

    def _detect_incident_updates(self, incidents: List[Incident]) -> None:
        for incident in incidents:
            for update in incident.updates:
                if update.id not in self.processed_incident_updates:
                    self.processed_incident_updates.add(update.id)
                    self._log_incident_event(incident, update)

    def _log_component_event(self, component: ComponentStatus, event_type: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[{timestamp}] Product: {component.name} Status: {component.status} ({event_type})"
        )

    def _log_incident_event(self, incident: Incident, update: IncidentUpdate) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        affected_products = self._extract_products_from_incident(incident.name)

        print(f"[{timestamp}] Product: {affected_products} Status: {update.status}")
        print(f"    Incident: {incident.name}")
        if update.body:
            print(f"    Update: {update.body}")
        print(f"    Impact: {incident.impact}")
        print()

    def _extract_products_from_incident(self, incident_name: str) -> str:
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
        summary_data = await self._fetch_with_etag(self.SUMMARY_ENDPOINT)
        if summary_data:
            components = self._parse_components(summary_data)
            self._detect_component_changes(components)

        incidents_data = await self._fetch_with_etag(self.INCIDENTS_ENDPOINT)
        if incidents_data:
            incidents = self._parse_incidents(incidents_data)
            self._detect_incident_updates(incidents)

    async def start_monitoring(self) -> None:
        self.logger.info(
            f"Starting OpenAI Status Monitor (polling every {self.poll_interval}s)"
        )
        print("OpenAI Status Monitor Started")
        print("=" * 50)

        try:
            while True:
                await self.check_status_updates()
                await asyncio.sleep(self.poll_interval)
        except KeyboardInterrupt:
            self.logger.info("Monitoring stopped by user")
            print("\nMonitor stopped")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            print(f"\nError: {e}")
