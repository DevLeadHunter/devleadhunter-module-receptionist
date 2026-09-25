"""The line a business pastes on its website to show its receptionist (the dashboard and the welcome email give it)."""

from core.config import settings


class AiAssistantEmbedSnippet:
    """Renders the loader tag of an assistant's widget."""

    @staticmethod
    def render(slug: str) -> str:
        """
        The script tag to paste before the site's closing body tag.

        Args:
            slug: The assistant's public slug.

        Returns:
            The tag, pointing at the demo host's loader.
        """
        base = settings.demo_host_base_url.rstrip("/")
        return f'<script src="{base}/ai-assistant.js" data-slug="{slug}" defer></script>'
