import json
import os
import urllib.request
import logging
import boto3

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

session = boto3.session.Session()

FUNCTION_NAMES = ["tavily_search"]

TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')

def tavily_search(
    search_query: str
) -> str:
    logger.info(f"executing Tavily AI search with {search_query=}")

    base_url = "https://api.tavily.com/search"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": search_query,
        "search_depth": "advanced",
        "include_images": False,
        "include_answer": False,
        "include_raw_content": False,
        "max_results": 3,
        "exclude_domains": [],
    }

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(base_url, data=data, headers=headers)

    try:
        response = urllib.request.urlopen(request) # nosec B310
        response_data: str = response.read().decode("utf-8")
        logger.debug(f"response from Tavily AI search {response_data=}")
        return response_data
    except urllib.error.HTTPError as e:
        logger.error(
            f"failed to retrieve search results from Tavily AI Search, error: {e.code}"
        )

    return ""

def handler(event, context):
    logging.debug(f"{event=}")

    agent = event["agent"]
    actionGroup = event["actionGroup"]
    function = event["function"]
    parameters = event.get("parameters", [])
    responseBody = {"TEXT": {"body": "Error, no function was called"}}

    logger.info(f"{actionGroup=}, {function=}")

    if function in FUNCTION_NAMES:
        if function == "tavily_search":
            search_query = None

            for param in parameters:
                if param["name"] == "search_query":
                    search_query = param["value"]

            if not search_query:
                responseBody = {
                    "TEXT": {"body": "Missing mandatory parameter: search_query"}
                }
            else:
                search_results = tavily_search(search_query)
                responseBody = {
                    "TEXT": {
                        "body": f"Here are the top search results for the query '{search_query}': {search_results} "
                    }
                }

                logger.debug(f"query results {search_results=}")
    else:
        responseBody = {"TEXT": {"body": f"Unable to process function: {function}"}}

    action_response = {
        "actionGroup": actionGroup,
        "function": function,
        "functionResponse": {"responseBody": responseBody},
    }

    function_response = {
        "response": action_response,
        "messageVersion": event.get("messageVersion", "1.0"),
    }

    logger.debug(f"lambda_handler: {function_response=}")

    return function_response