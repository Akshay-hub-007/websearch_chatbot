# WebSearch Chatbot

A FastAPI-based chatbot that uses LangChain, LangGraph, and Tavily Search to answer questions with real-time web search results. The backend streams responses using Server-Sent Events (SSE).

## Features
- Gemini 1.5 Flash LLM integration
- Tavily web search tool
- Streaming chat responses via SSE
- Conversation checkpointing for session continuity
- Docker-ready and deployable to cloud platforms

## API Endpoints
### Chat Stream
- `GET /chat_stream/{message}`
  - Streams chat responses for the given message.
  - Optional query param: `checkpoint_id` to continue a previous conversation.

**Example:**
```
GET https://websearch-latest.onrender.com/chat_stream/pm%20of%20japan%20?
GET https://websearch-latest.onrender.com/chat_stream/prompt?checkpoint_id=<your_checkpoint_id>
```

## Environment Variables
Set these in your `.env` file or as Docker environment variables:
```
GOOGLE_API_KEY=your-google-api-key
TAVILY_API_KEY=your-tavily-api-key
```

## Running Locally
1. Clone the repo:
   ```
   git clone https://github.com/Akshay-hub-007/websearch_chatbot.git
   cd websearch_chatbot
   ```
2. Create and activate a Python virtual environment:
   ```
   python -m venv venv
   .\venv\Scripts\activate  # On Windows
   source venv/bin/activate  # On Linux/Mac
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Set up your `.env` file with API keys.
5. Run the server:
   ```
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```

## Docker Usage
Build and run the Docker container:
```
docker build -t websearch:latest .
docker run -d -p 8000:8000 --env GOOGLE_API_KEY=your-google-api-key --env TAVILY_API_KEY=your-tavily-api-key --name websearch-container websearch:latest
```

## Deployment
You can deploy to Render, Heroku, or any cloud platform supporting Docker and FastAPI.

## Checkpoint Usage
- The API returns a `checkpoint_id` in the first response.
- Use this `checkpoint_id` in subsequent requests to continue the same conversation:
  ```
  GET /chat_stream/{message}?checkpoint_id=<your_checkpoint_id>
  ```

## License
MIT
