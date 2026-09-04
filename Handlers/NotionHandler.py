import os
import dotenv
import requests
from urllib.parse import quote


class NotionHandler:

    def __init__(self):
        dotenv.load_dotenv(".env.local")
        self.api_key = os.getenv("NOTION_API")
        self.version = os.getenv("NOTION_VERSION")
        self.base_url = "https://api.notion.com/v1"
        self.notion_page_id = os.getenv("NOTION_PAGE_ID")

    def _headers(self):
        return {
            "Notion-Version": self.version,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def create_page(self, title: str, content: str):
        """Crea una sub-página hija de la página padre con el contenido dado (compat: sin cuerpo)."""
        return self.create_subpage(title, content, parent_page_id=self.notion_page_id)

    def create_subpage(self, title: str, content: str, parent_page_id: str = None) -> dict | None:
        """Crea una nueva sub-página hija de la página padre (o del parent indicado) con título y contenido."""
        parent_page_id = parent_page_id or self.notion_page_id
        url = f"{self.base_url}/pages"

        payload = {
            "parent": {
                "page_id": parent_page_id,
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

        try:
            response = requests.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating Notion subpage: {e}")
            return None

    def get_page(self, page_id: str) -> dict | None:
        """Obtiene las propiedades y metadatos de una página concreta (id -> título)."""
        url = f"{self.base_url}/pages/{page_id}"
        try:
            response = requests.get(url, headers=self._headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting Notion page: {e}")
            return None

    def get_page_children(self, page_id: str) -> list | None:
        """Obtiene los bloques hijos (contenido) de una página."""
        url = f"{self.base_url}/blocks/{page_id}/children"
        try:
            response = requests.get(url, headers=self._headers())
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except requests.exceptions.RequestException as e:
            print(f"Error getting Notion page children: {e}")
            return None

    def _page_title(self, page: dict) -> str:
        """Extrae el título de un objeto page de Notion (maneja varios formatos)."""
        try:
            props = page.get("properties", {}) or {}
            for val in props.values():
                if isinstance(val, dict) and val.get("type") == "title":
                    items = val.get("title", []) or []
                    return "".join(item.get("plain_text", "") for item in items)
                if isinstance(val, dict) and "title" in val:
                    items = val.get("title", []) or []
                    return "".join(item.get("plain_text", "") for item in items)
        except Exception:
            pass
        return page.get("id", "")

    @staticmethod
    def _norm_id(page_id: str) -> str:
        """Normaliza un id de Notion a su forma compacta (sin guiones) para comparar de forma fiable."""
        return (page_id or "").replace("-", "")

    def search_subpages(self, query: str = None, parent_id: str = None) -> list:
        """Busca páginas bajo la página padre (o parent indicado). Filtra sub-páginas directas.
        Si query no es None, busca páginas cuyo título coincida (búsqueda parcial)."""
        parent_id = self._norm_id(parent_id or self.notion_page_id)
        url = f"{self.base_url}/search"
        payload = {
            "filter": {
                "value": "page",
                "property": "object",
            },
            "sort": {
                "direction": "ascending",
                "timestamp": "last_edited_time",
            },
        }
        if query:
            payload["query"] = query

        results = []
        start_cursor = None
        try:
            while True:
                body = dict(payload)
                if start_cursor:
                    body["start_cursor"] = start_cursor
                response = requests.post(url, json=body, headers=self._headers())
                response.raise_for_status()
                data = response.json()
                pages = data.get("results", [])
                for p in pages:
                    parent = p.get("parent", {}) or {}
                    if parent.get("type") == "page_id" and self._norm_id(parent.get("page_id")) == parent_id:
                        results.append({
                            "id": p.get("id"),
                            "title": self._page_title(p),
                            "url": p.get("url", ""),
                            "created": p.get("created_time", ""),
                            "last_edited": p.get("last_edited_time", ""),
                        })
                if not data.get("has_more"):
                    break
                start_cursor = data.get("next_cursor")
            return results
        except requests.exceptions.RequestException as e:
            print(f"Error searching Notion pages: {e}")
            return []

    def search_by_content(self, keyword: str, parent_id: str = None) -> list:
        """Busca sub-páginas por palabras clave en el CONTENIDO (lee bloques hijos de cada una)."""
        parent_id = parent_id or self.notion_page_id
        matches = []
        keyword_l = keyword.lower()
        pages = self.search_subpages(parent_id=parent_id)
        for page in pages:
            children = self.get_page_children(page["id"]) or []
            contenido = ""
            for blk in children:
                for key in ("paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item",
                            "numbered_list_item", "to_do", "quote", "code"):
                    b = blk.get(key)
                    if not b:
                        continue
                    for rt in (b.get("rich_text") or []):
                        contenido += " " + rt.get("plain_text", "")
            if keyword_l in contenido.lower():
                page["match"] = "contenido"
                matches.append(page)
        return matches

    def update_page_title(self, page_id: str, nuevo_titulo: str) -> dict | None:
        """Actualiza el título de una página existente."""
        url = f"{self.base_url}/pages/{page_id}"
        payload = {
            "properties": {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": nuevo_titulo
                            }
                        }
                    ]
                }
            }
        }
        try:
            response = requests.patch(url, json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error updating Notion page: {e}")
            return None

    def archive_page(self, page_id: str) -> dict | None:
        """Mueve una página a la papelera (archiva / oculta de la vista) en Notion. No la borra definitivamente."""
        url = f"{self.base_url}/pages/{page_id}"
        payload = {"in_trash": True}
        try:
            response = requests.patch(url, json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error archiving Notion page: {e}")
            return None
