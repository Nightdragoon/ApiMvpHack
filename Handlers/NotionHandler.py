import os
import dotenv
import requests


class NotionHandler:

    def __init__(self):
        dotenv.load_dotenv(".env.local")
        self.api_key = os.getenv("NOTION_API")
        self.version = os.getenv("NOTION_VERSION")
        self.base_url = "https://api.notion.com/v1"
        self.notion_page_id = os.getenv("NOTION_PAGE_ID")

    def create_page(self, title: str, content: str):
        url = f"{self.base_url}/pages"

        payload = {
            "parent": {
                "page_id": self.notion_page_id,
                "type": "page_id"
            },
            "properties": {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": content
                                }
                            }
                        ]
                    }
                }
            ]
        }

        headers = {
            "Notion-Version": self.version,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating Notion page: {e}")
            return None