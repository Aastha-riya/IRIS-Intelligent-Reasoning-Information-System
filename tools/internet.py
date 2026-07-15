"""
tools/internet.py

Web search tool using DuckDuckGo.
Returns the top search results for a given query.
"""

from duckduckgo_search import DDGS

from utils.logger import logger


class Internet:
    """Searches the web using DuckDuckGo and returns formatted results."""

    MAX_RESULTS: int = 3

    def search(self, query: str) -> str:
        """
        Perform a web search for the query and return
        a formatted string of the top results.
        """
        logger.info(f"Internet search: {query}")

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=self.MAX_RESULTS))

            if not results:
                logger.warning(f"No results found for: {query}")
                return "No results found."

            lines: list[str] = []
            for i, result in enumerate(results, start=1):
                lines.append(
                    f"{i}. {result['title']}\n"
                    f"{result['body']}\n"
                    f"{result['href']}\n"
                )

            logger.info(f"Internet search returned {len(results)} results.")
            return "\n".join(lines)

        except Exception as e:
            logger.exception(f"Internet search failed: {e}")
            return "Internet connection failed."
