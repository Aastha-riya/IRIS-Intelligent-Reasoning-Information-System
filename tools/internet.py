from duckduckgo_search import DDGS


class Internet:

    def search(self, query):

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))

        if not results:
            return "No results found."

        answer = ""

        for i, result in enumerate(results, start=1):
            answer += (
                f"{i}. {result['title']}\n"
                f"{result['body']}\n"
                f"{result['href']}\n\n"
            )

        return answer