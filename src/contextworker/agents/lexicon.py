"""
Lexicon Agent - The Researcher.

Background worker that enriches content by:
1. Detecting new Brands/Technologies without descriptions
2. Researching via external APIs (Perplexity, Web Search)
3. Drafting Wagtail CMS pages for review

Queue: Watches for new Brand/Technology entities in Commerce DB.
Output: Draft pages in Wagtail review queue.
"""

import time
import logging
from ..registry import register, BaseAgent

logger = logging.getLogger(__name__)


@register("lexicon")
class LexiconAgent(BaseAgent):
    """
    Background agent for content research and generation.

    Config:
        poll_interval: Seconds between checks (default: 300)
        perplexity_api_key: API key for research
    """

    name = "lexicon"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.poll_interval = self.config.get("poll_interval", 300)  # 5 min

    def run(self):
        """Main loop."""
        logger.info(f"Lexicon starting. Poll interval: {self.poll_interval}s")

        while self._running:
            try:
                count = self._process_new_entities()
                if count > 0:
                    logger.info(f"Drafted {count} new content pages")
            except Exception as e:
                logger.exception(f"Lexicon error: {e}")

            time.sleep(self.poll_interval)

    def _process_new_entities(self) -> int:
        """Find entities without descriptions and research them."""
        # TODO: Query Commerce DB for Brand/Technology with empty description
        # TODO: Call Perplexity API for research
        # TODO: Create draft Wagtail page
        return 0
