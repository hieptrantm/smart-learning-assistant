"""
calendar_tool.py -- MCP tool for creating Google Calendar events.
Singleton pattern. Accepts event JSON + OAuth tokens per request.
"""

from asyncio import events
import json
import logging
from typing import Annotated

from pydantic import Field
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BuildScheduleTool:
    """Google Calendar event creation tool (singleton)."""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.__class__._initialized = True
            logger.info("Initialized BuildScheduleTool")

    def _build_credentials(self, access_token: str, refresh_token: str) -> Credentials:
        """Build Google OAuth credentials from tokens."""
        if not access_token and not refresh_token:
            raise ValueError("access_token or refresh_token is required")

        creds = Credentials(
            token=access_token or None,
            refresh_token=refresh_token or None,
            token_uri=config.TOKEN_URI if refresh_token else None,
            client_id=config.GOOGLE_CLIENT_ID if refresh_token else None,
            client_secret=config.GOOGLE_CLIENT_SECRET if refresh_token else None,
            scopes=config.CALENDAR_SCOPES,
        )

        if refresh_token:
            creds.refresh(Request())

        return creds

    async def build_one_schedule(
        self,
        event_json: Annotated[str, Field(description=(
            "JSON string of Google Calendar event. Required fields: "
            "summary, description, start.dateTime, start.timeZone, end.dateTime, end.timeZone. "
            "Example: {\"summary\":\"Bai hoc 1\",\"description\":\"Noi dung\","
            "\"start\":{\"dateTime\":\"2026-03-26T10:00:00+07:00\",\"timeZone\":\"Asia/Ho_Chi_Minh\"},"
            "\"end\":{\"dateTime\":\"2026-03-26T11:00:00+07:00\",\"timeZone\":\"Asia/Ho_Chi_Minh\"}}"
        ))],
        google_access_token: Annotated[str, Field(description="Google OAuth2 access token")] = "",
        google_refresh_token: Annotated[str, Field(description="Google OAuth2 refresh token")] = "",
    ) -> str:
        """Create a Google Calendar event from event JSON. Returns result with event_id."""
        try:
            logger.info(f"Received event_json: {event_json}")
            logger.info(f"Google access token: {google_access_token}")
            logger.info(f"Google refresh token: {google_refresh_token}")
            event_body = json.loads(event_json) if isinstance(event_json, str) else event_json

            # Validate required fields
            for key in ("summary", "start", "end"):
                if key not in event_body:
                    return json.dumps({
                        "success": False,
                        "content": "",
                        "event_id": "",
                        "error": f"Missing required field: {key}",
                    })

            creds = self._build_credentials(google_access_token, google_refresh_token)
            
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)

            # Add default reminders if not specified
            if "reminders" not in event_body:
                event_body["reminders"] = {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 720},
                        {"method": "email", "minutes": 720},
                    ],
                }

            event = service.events().insert(calendarId="primary", body=event_body).execute()
            event_id = event.get("id", "")
            html_link = event.get("htmlLink", "")

            logger.info(f"Calendar event created: {event_id}")
            return json.dumps({
                "success": True,
                "content": f"Event created: {html_link}",
                "event_id": event_id,
                "error": None,
            })

        except json.JSONDecodeError as e:
            logger.info(f"Invalid event_json: {e}")
            return json.dumps({
                "success": False, 
                "content": "", 
                "event_id": "",
                "error": f"Invalid event_json: {e}",
            })
        except Exception as e:
            logger.error(f"build_schedule error: {e}")
            return json.dumps({
                "success": False, "content": "", "event_id": "",
                "error": str(e),
            })



# script test
if __name__ == "__main__":
    tool = BuildScheduleTool()
    test_event_json = json.dumps({
        "summary": "Bai hoc 1",
        "description": "Noi dung",
        "start": {"dateTime": "2026-03-26T10:00:00+07:00", "timeZone": "Asia/Ho_Chi_Minh"},
        "end": {"dateTime": "2026-03-26T11:00:00+07:00", "timeZone": "Asia/Ho_Chi_Minh"},
    })
    
    with open("tools/raw_chunk.json", 'r', encoding='utf-8') as f:
        raw_chunks = json.load(f)
        
    import asyncio    
        
    for chunk in raw_chunks:
        event = json.dumps(chunk)
            
        result = asyncio.run(tool.build_one_schedule(event))
        
    

    

    print(result)