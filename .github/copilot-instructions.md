Always use the latest documentation for imports and packages.  

Use fetch tool if you know the url of the docs.

Use Tavily MCP Search and Extract to research documentation and examples when trying to make things work.

For how to write an mcp server in Python see https://github.com/modelcontextprotocol/python-sdk

For python projects always use astral uv; e.g. 'uv run', 'uv add', 'uv sync' etc.  DO NOT USE `python` or `python3` commands directly.

# cli interface - GA4query3.py and NewDownloads.py

The CLI interface for `GA4query3.py` and `NewDownloads.py` is designed to allow users to interact with the analytics functionality from the command line. This interface typically includes commands for running queries, generating reports, and retrieving data from Google Analytics 4 (GA4) and Google Search Console (GSC).

# Webapp

There is a web app in the `webapp` directory.

It provides a back end that can respond to the front end to do quries.  The queries are ultimately handled by the same GA4query3.py and NewDownloads.py that everything else uses, only imported and called as functions instead of as cli.


The overall architecture is a Python-based web application with a clear separation between the frontend and backend. The backend is responsible for handling API requests, authentication, and data processing using Google Analytics 4 (GA4) and Google Search Console (GSC) data. The backend exposes endpoints that the frontend can call to perform analytics queries. The frontend is a web interface (likely using a lightweight framework or plain HTML/JS) that interacts with the backend via HTTP requests. Core analytics logic is shared between the CLI and webapp by importing and calling functions from `GA4query3.py` and `NewDownloads.py`.


The communication between front and back end is done via HTTP requests (typically RESTful API calls). The frontend sends requests to the backend endpoints, which process the request, run the appropriate analytics queries, and return JSON responses. This allows the frontend to dynamically display analytics results and reports to the user.

The backend is built using FastAPI, a modern web framework for building APIs with Python. FastAPI provides features like automatic request validation, serialization, and documentation generation, making it easier to develop and maintain the API.

The backend responds to calls that can be simulated using curl like this:

```sh
curl -X POST \
	-H "Content-Type: application/json" \
	-d '{"start_date": "2024-08-01", "end_date": "2024-08-10", "property_id": "YOUR_GA4_PROPERTY_ID"}' \
	http://localhost:8000/api/ga4/query
```

Replace the endpoint and payload as needed for different analytics queries. The backend will return a JSON response with the requested analytics data.
